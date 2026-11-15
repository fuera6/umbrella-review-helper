"""PubMed 메타데이터(1저자·연도·저널·DOI). LLM을 쓰지 않는다.

NCBI E-utilities esummary 사용. 키 없이 초당 3건 제한 → 요청 사이 0.34초 쉼.

"""
import time
import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "umbrella-review-helper"   # NCBI 권장: 도구 이름과 연락 이메일
CONTACT_EMAIL = ""                     # 팀 이메일을 넣어 주세요 (비밀값 아님)
_last_call = 0.0


def _get(endpoint: str, params: dict) -> dict:
    global _last_call
    wait = 0.34 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    params = {**params, "tool": TOOL_NAME, "retmode": "json"}
    if CONTACT_EMAIL:
        params["email"] = CONTACT_EMAIL
    r = requests.get(f"{EUTILS}/{endpoint}", params=params, timeout=30)
    _last_call = time.time()
    r.raise_for_status()
    return r.json()


def fetch_summaries(pmids: list[str]) -> dict[str, dict]:
    """{pmid: {title, first_author, year, journal, doi}} — 200개씩 나눠 요청."""
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i:i + 200]
        res = _get("esummary.fcgi", {"db": "pubmed", "id": ",".join(chunk)})["result"]
        for uid in res.get("uids", []):
            d = res[uid]
            doi = next((a["value"] for a in d.get("articleids", []) if a.get("idtype") == "doi"), None)
            first = d.get("sortfirstauthor") or (d["authors"][0]["name"] if d.get("authors") else "")
            out[uid] = {
                "title": d.get("title", "").rstrip("."),
                "first_author": first.split(" ")[0] if first else "",
                "year": int(d["pubdate"][:4]) if d.get("pubdate", "")[:4].isdigit() else None,
                "journal": d.get("fulljournalname") or d.get("source", ""),
                "doi": doi,
            }
    return out


def doi_to_pmid(doi: str) -> str | None:
    """DOI로 PubMed를 검색해 PMID 하나를 돌려준다. 없거나 여러 개면 None."""
    ids = _get("esearch.fcgi", {"db": "pubmed", "term": f"{doi}[doi]"})["esearchresult"].get("idlist", [])
    return ids[0] if len(ids) == 1 else None


def search(query: str, retmax: int = 500) -> tuple[int, list[str]]:
    """검색식 실행 → (전체 건수, 앞에서부터 retmax개 PMID)."""
    r = _get("esearch.fcgi", {"db": "pubmed", "term": query, "retmax": retmax})["esearchresult"]
    if r.get("ERROR"):
        raise ValueError(r["ERROR"])
    return int(r.get("count", 0)), r.get("idlist", [])


def fetch_abstracts(pmids: list[str]) -> dict[str, str]:
    """{pmid: 초록}. 초록이 없는 논문은 결과에 없다. efetch(XML)로 200개씩."""
    import xml.etree.ElementTree as ET
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i:i + 200]
        global _last_call
        wait = 0.34 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        params = {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml", "rettype": "abstract", "tool": TOOL_NAME}
        if CONTACT_EMAIL:
            params["email"] = CONTACT_EMAIL
        r = requests.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=60)
        _last_call = time.time()
        r.raise_for_status()
        out.update(parse_abstracts(r.text))
    return out


def parse_abstracts(xml_text: str) -> dict[str, str]:
    import xml.etree.ElementTree as ET
    out = {}
    for art in ET.fromstring(xml_text).iter("PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID")
        parts = []
        for t in art.iter("AbstractText"):
            text = "".join(t.itertext()).strip()
            if text:
                lab = t.get("Label")
                parts.append(f"{lab}: {text}" if lab else text)
        if pmid and parts:
            out[pmid] = "\n\n".join(parts)
    return out
