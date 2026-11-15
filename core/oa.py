"""4단계: PubMed Central 공개(오픈액세스) 원문 PDF를 DOI·PMID로 찾아 자동으로 받는다.

받는 순서 (공식 공개 경로부터):
  1) PMC Cloud Service — NCBI가 AWS에 공개한 PMC 오픈액세스 저장소(pmc-oa-opendata).
     PMCID로 시작하는 폴더(예: PMC1234567.1/)를 찾아 그 안의 PDF를 받는다.
  2) Europe PMC의 PDF 변환 주소 (웹사이트 다운로드 버튼이 쓰는 주소)
  3) Europe PMC가 알려 주는 다른 PDF 주소 (출판사 등)
- PMCID는 Europe PMC 검색으로 찾고, 실패하면 NCBI ID 변환 API로 찾는다.
- 포함 논문만 한 편씩, 요청 사이에 쉬면서 받는다 (대량 수집 아님).
- 실패하면 어느 단계에서 왜 실패했는지 짧게 돌려준다.
- ⚠ 개발 환경에서는 외부 접속이 막혀 실제 호출은 시험하지 못했다.
"""
import re
import time
import requests

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EPMC_RENDER = "https://europepmc.org/backend/ptpmcrender.fcgi"
PMC_CLOUD = "https://pmc-oa-opendata.s3.amazonaws.com"
IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
HEADERS = {"User-Agent": "umbrella-review-helper/1.0 (education project; contact via course)"}
MAX_PDF = 30 * 1024 * 1024


def _get(url, **kw):
    r = requests.get(url, headers=HEADERS, timeout=kw.pop("timeout", 45), **kw)
    time.sleep(0.35)
    return r


def lookup(pmid=None, doi=None) -> dict:
    """Europe PMC에서 PMCID·오픈액세스 여부·PDF 주소를 찾는다."""
    q = f"EXT_ID:{pmid} AND SRC:MED" if pmid else f'DOI:"{doi}"'
    r = _get(EPMC, params={"query": q, "resultType": "core", "format": "json", "pageSize": 1})
    r.raise_for_status()
    res = r.json().get("resultList", {}).get("result", [])
    if not res:
        return {"pmcid": None, "open_access": None, "urls": []}
    d = res[0]
    urls = [u.get("url") for u in d.get("fullTextUrlList", {}).get("fullTextUrl", [])
            if u.get("documentStyle") == "pdf" and u.get("url")]
    return {"pmcid": d.get("pmcid"), "open_access": d.get("isOpenAccess") == "Y", "urls": urls}


def pmcid_from_ncbi(pmid=None, doi=None) -> str | None:
    ident = pmid or doi
    if not ident:
        return None
    r = _get(IDCONV, params={"ids": ident, "format": "json", "tool": "umbrella-review-helper"})
    if r.status_code != 200:
        return None
    recs = r.json().get("records", [])
    return recs[0].get("pmcid") if recs else None


def cloud_pdf_urls(pmcid: str) -> list[str]:
    """PMC Cloud Service에서 이 PMCID의 PDF 주소들 (최신 버전 먼저). 목록을 못 받으면 흔한 경로를 추측한다."""
    r = _get(PMC_CLOUD, params={"list-type": "2", "prefix": f"{pmcid}."})
    keys = re.findall(r"<Key>([^<]+?\.pdf)</Key>", r.text) if r.status_code == 200 else []
    if keys:
        ver = lambda k: int(m.group(1)) if (m := re.search(rf"{pmcid}\.(\d+)/", k)) else 0
        return [f"{PMC_CLOUD}/{k}" for k in sorted(keys, key=ver, reverse=True)]
    return [f"{PMC_CLOUD}/{pmcid}.{v}/{pmcid}.{v}.pdf" for v in (1, 2, 3)]


def _download(url) -> tuple[bytes | None, str]:
    try:
        r = _get(url, timeout=60, allow_redirects=True)
    except requests.RequestException as e:
        return None, type(e).__name__
    if r.status_code != 200:
        return None, str(r.status_code)
    if r.content[:5] != b"%PDF-":
        return None, "PDF 아님"
    if len(r.content) > MAX_PDF:
        return None, "너무 큼"
    return r.content, "ok"


def fetch_open_access(pmid=None, doi=None) -> tuple[bytes | None, str]:
    """(PDF bytes 또는 None, 결과 설명)."""
    try:
        info = lookup(pmid, doi)
    except Exception as e:
        info = {"pmcid": None, "open_access": None, "urls": []}
        epmc_err = type(e).__name__
    else:
        epmc_err = None
    pmcid = info["pmcid"]
    if not pmcid:
        try:
            pmcid = pmcid_from_ncbi(pmid, doi)
        except Exception:
            pmcid = None
    if not pmcid and not info["urls"]:
        why = f"Europe PMC 접속 실패({epmc_err})" if epmc_err else "PubMed Central에 등록되지 않은 논문"
        return None, f"자동으로 받지 못함: {why}"
    tried = []
    if pmcid:
        for url in cloud_pdf_urls(pmcid)[:3]:
            pdf, st = _download(url)
            if pdf:
                return pdf, f"PMC Cloud 공개 원문 ({pmcid})"
            tried.append(f"PMC Cloud {st}")
        pdf, st = _download(f"{EPMC_RENDER}?accid={pmcid}&blobtype=pdf")
        if pdf:
            return pdf, f"Europe PMC 공개 원문 ({pmcid})"
        tried.append(f"Europe PMC {st}")
    for url in info["urls"][:2]:
        pdf, st = _download(url)
        if pdf:
            return pdf, "공개 원문 (출판사 링크)"
        tried.append(f"출판사 {st}")
    if pmcid and info.get("open_access") is False:
        return None, f"자동으로 받지 못함: PMC에 있으나 오픈액세스 아님 ({pmcid})"
    return None, f"자동으로 받지 못함: {' · '.join(dict.fromkeys(tried))}"
