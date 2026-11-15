"""이번에 추가한 기능: 초록, AI 스크리닝 추천, 공개 원문 자동 받기, 근거 위치 강조, 그림 제목, 원문 대조."""
import json
import types as pytypes
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.test_app_flow import APP, PDF, btn, ok

XML = """<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article><Abstract>
<AbstractText Label="BACKGROUND">Exercise may help.</AbstractText><AbstractText Label="RESULTS">SMD -0.47.</AbstractText>
</Abstract></Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>222</PMID><Article></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


def test_parse_abstracts_structured_and_missing():
    from core.pubmed import parse_abstracts
    out = parse_abstracts(XML)
    assert out == {"111": "BACKGROUND: Exercise may help.\n\nRESULTS: SMD -0.47."}       # 222는 초록 없음


def test_screening_parse_and_batches(monkeypatch):
    import streamlit as st
    import core.gemini as gm
    import core.providers as pv
    from core import screening
    calls = []
    def fake_gen(key, model, contents, system):
        recs = json.loads(contents[0].split("Records\n", 1)[1])
        calls.append(len(recs))
        return json.dumps({"results": [{"id": r["id"], "decision": "include" if "exercise" in r["title"] else "exclude",
                                        "reason": "이유"} for r in recs] + [{"id": "zzz", "decision": "include", "reason": "x"}]})
    monkeypatch.setattr(gm, "_generate", fake_gen)
    st.session_state.clear()
    st.session_state.update(provider="gemini", api_key="k", gemini_model="m", gemini_models=["m"])
    items = [{"id": str(i), "title": "exercise review" if i % 2 else "drug review", "abstract": "a"} for i in range(20)]
    res = pv.screen({"O": "depression"}, items)
    assert calls == [15, 5] and len(res) == 20 and "zzz" not in res
    assert res["1"]["decision"] == "포함" and res["0"]["decision"] == "제외"


def test_find_evidence_and_highlight():
    from core.pdfview import find_evidence, render
    page, rects = find_evidence(PDF, "…Sample  page 3…", 1)
    assert page == 3 and rects
    img, n = render(PDF, page, rects)
    assert n == 3 and img.getpixel((int(rects[0][0] * 1.6) + 3, int((576 - rects[0][3]) * 1.6) + 3)) != (255, 255, 255)
    assert find_evidence(PDF, "없는 문장입니다", 2) == (2, [])


class _R:
    def __init__(self, status=200, js=None, content=b"", text=""):
        self.status_code, self._js, self.content, self.text = status, js, content, text
    def json(self): return self._js
    def raise_for_status(self): pass


def _epmc(pmcid="PMC123", oa="Y", urls=()):
    return {"resultList": {"result": [{"isOpenAccess": oa, "pmcid": pmcid, "fullTextUrlList": {"fullTextUrl": [
        {"documentStyle": "pdf", "url": u} for u in urls]}}]}}


def test_oa_pmc_cloud_first(monkeypatch):
    import core.oa as oa
    monkeypatch.setattr(oa.time, "sleep", lambda s: None)
    listing = "<ListBucketResult><Contents><Key>PMC123.1/PMC123.1.pdf</Key></Contents><Contents><Key>PMC123.2/PMC123.2.pdf</Key></Contents><Contents><Key>PMC123.2/PMC123.2.xml</Key></Contents></ListBucketResult>"
    seen = []
    def get(url, **k):
        seen.append(url)
        if "rest/search" in url: return _R(js=_epmc())
        if url == oa.PMC_CLOUD: return _R(text=listing)
        if url.endswith("PMC123.2/PMC123.2.pdf"): return _R(content=b"%PDF-1.7 v2")
        return _R(status=404)
    monkeypatch.setattr(oa.requests, "get", get)
    pdf, note = oa.fetch_open_access(pmid="1")
    assert pdf == b"%PDF-1.7 v2" and "PMC Cloud" in note                       # 최신 버전(2) PDF


def test_oa_falls_back_to_europe_pmc_render(monkeypatch):
    import core.oa as oa
    monkeypatch.setattr(oa.time, "sleep", lambda s: None)
    def get(url, **k):
        if "rest/search" in url: return _R(js=_epmc())
        if url == oa.PMC_CLOUD: return _R(status=403, text="")
        if url.startswith(oa.EPMC_RENDER): return _R(content=b"%PDF-1.4 epmc")
        return _R(status=404)
    monkeypatch.setattr(oa.requests, "get", get)
    pdf, note = oa.fetch_open_access(doi="10.1/x")
    assert pdf == b"%PDF-1.4 epmc" and "Europe PMC" in note


def test_oa_failure_reasons(monkeypatch):
    import core.oa as oa
    monkeypatch.setattr(oa.time, "sleep", lambda s: None)
    monkeypatch.setattr(oa.requests, "get", lambda url, **k: _R(js={"resultList": {"result": []}}) if "rest/search" in url
                        else _R(js={"records": [{}]}) if "idconv" in url else _R(status=404))
    assert oa.fetch_open_access(doi="10.1/x") == (None, "자동으로 받지 못함: PubMed Central에 등록되지 않은 논문")
    def get(url, **k):
        if "rest/search" in url: return _R(js=_epmc(urls=["https://publisher/x.pdf"]))
        if url == oa.PMC_CLOUD: return _R(text="<ListBucketResult></ListBucketResult>")
        if url.startswith(oa.EPMC_RENDER): return _R(status=403)
        if "publisher" in url: return _R(content=b"<html>blocked")
        return _R(status=404)
    monkeypatch.setattr(oa.requests, "get", get)
    pdf, note = oa.fetch_open_access(pmid="1")
    assert pdf is None and "PMC Cloud 404" in note and "Europe PMC 403" in note and "출판사 PDF 아님" in note


def test_figure_titles_drawn():
    import matplotlib.pyplot as plt
    from core.figures import forest_plot, prisma
    from tests.test_logic import paper
    from core.results import forest_rows
    from views.figcache import default_titles
    t = default_titles({"I": "Exercise", "O": "depressive symptoms"}, ["SMD"])
    assert "Effect of Exercise on depressive symptoms" in t["forest_SMD"] and t["prisma"].startswith("Figure 1.")
    fig = forest_plot(forest_rows([paper("SMD", -0.5, -0.8, -0.2)]), "SMD", t["forest_SMD"])
    assert any("Effect of Exercise" in x.get_text() for x in fig.texts); plt.close(fig)
    c = {"identified": 3, "other": 0, "dup": 0, "screened": 3, "excluded": 1, "sought": 2, "not_retrieved": 0, "assessed": 2, "final": 2}
    for d in ["미니멀 흑백", "세로 캡슐"]:
        fig = prisma(c, d, "Figure 1. Test"); assert any(x.get_text() == "Figure 1. Test" for x in fig.texts); plt.close(fig)


def test_demo_ai_screening_flow(monkeypatch):
    import core.pubmed
    monkeypatch.setattr(core.pubmed, "doi_to_pmid", lambda doi: str(abs(hash(doi)) % 10**7))
    monkeypatch.setattr(core.pubmed, "fetch_abstracts", lambda ids: {i: f"Abstract of {i}" for i in ids[:-3]})   # 3편은 초록 없음
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); btn(at, "AI 추천").click().run()
    btn(at, "다음: PubMed").click().run(); btn(at, "다음: 스크리닝").click().run(); ok(at)   # 들어오면 초록 자동 불러오기
    assert sum(bool(p.get("abstract")) for p in at.session_state.papers) == 18
    assert not any(b.label.startswith("초록 불러오기") for b in at.button)
    btn(at, "AI 추천 받기").click().run(); ok(at)
    recs = [p["ai_rec"]["decision"] for p in at.session_state.papers]
    assert recs.count("포함") == 19 and recs.count("제외") == 2
    btn(at, "모두 선택").click().run()
    btn(at, "AI 추천대로 체크하기").click().run(); ok(at)
    assert sum(not p["included"] for p in at.session_state.papers) == 2
    assert all(p["exclude_reason"].startswith("AI 추천") for p in at.session_state.papers if not p["included"])
    assert any("초록이 없는 논문 3편" in c.value for c in at.caption)


def test_api_screening_no_abstract_is_maybe(monkeypatch):
    import streamlit as st
    import views.step3_ai as ai
    st.session_state.clear()
    st.session_state.update(mode="api", provider="gemini", api_key="k", pico={},
                            papers=[{"uid": "a", "title": "t", "abstract": None}])
    ai.run_ai()
    assert st.session_state.papers[0]["ai_rec"]["decision"] == "보류"


def test_api_auto_fetch_and_source_check(monkeypatch):
    import core.extract, core.oa, core.pubmed
    import views.step5 as s5
    from tests.test_logic import mock_output
    monkeypatch.setattr(core.pubmed, "search", lambda q, retmax=500: (2, ["1", "2"]))
    monkeypatch.setattr(core.pubmed, "fetch_summaries", lambda ids: {i: {"title": f"T{i}", "first_author": f"A{i}", "year": 2020,
                        "journal": "J", "doi": f"10.1/{i}"} for i in ids})
    monkeypatch.setattr(core.pubmed, "fetch_abstracts", lambda ids: {"1": "abs"})
    monkeypatch.setattr(core.oa, "fetch_open_access", lambda pmid=None, doi=None: (PDF, "PubMed Central 공개 원문 (PMC1)") if pmid == "1" else (None, "공개 원문이 없습니다"))
    def fake_extract(pdf, pico, supp=()):
        out = mock_output()
        out["estimate"] = {"value": -0.5, "evidence": "Sample page 3", "page": 1}
        return core.extract.to_app_format(out)
    monkeypatch.setattr(s5, "extract_one", fake_extract)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["mode"] = "api"; at.session_state["api_key"] = "k"; at.session_state["provider"] = "claude"
    at.session_state["pico"] = {"question": "q", "P": "p", "I": "Exercise", "C": "c", "O": "depression", "query": "x[tiab]"}
    at.session_state["search"] = {"query": "x[tiab]", "records_identified": 0, "duplicates_removed": 0, "other_sources": 0, "note": ""}
    at.session_state["reach"] = 2; at.session_state["page"] = "step2"
    at.run(); btn(at, "검색 실행").click().run(); ok(at)
    assert at.session_state.papers[0]["abstract"] == "abs" and at.session_state.papers[1]["abstract"] is None
    at.session_state.reach = 4; at.session_state.page = "step4"; at.run(); ok(at)
    btn(at, "공개 원문 자동 받기").click().run(); ok(at)
    st_ = {p["pmid"]: p["fulltext"] for p in at.session_state.papers}
    assert st_ == {"1": "saved", "2": "missing"}
    assert any("1쪽 미리보기" in e.label for e in at.expander)
    at.session_state.reach = 5; at.session_state.page = "step5"; at.run()
    btn(at, "추출 시작").click().run(); ok(at)
    btn(at, "다음: 저자").click().run(); ok(at)
    btn(at, "원문 p. 1").click().run(); ok(at)
    assert at.session_state["pg_1"] == 3 and at.session_state["hl_1"][1]            # 적힌 쪽(1)이 아니라 실제 위치(3쪽)로 이동·강조
    btn(at, "이 논문 검토 완료").click().run()
    btn(at, "다음: 표").click().run(); ok(at)
    assert at.session_state.fig_titles["forest_SMD"].startswith("Figure 2. Effect of Exercise on depression")
    btn(at, "SMD −0.50").click().run(); ok(at)                                     # 원문 대조 창
    assert any("노란색" in (getattr(i, "caption", "") or "") for i in at.get("imgs")) or len(at.get("image")) >= 1


def test_added_paper_gets_abstract_and_failure_not_looping(monkeypatch):
    import core.pubmed
    calls = []
    monkeypatch.setattr(core.pubmed, "doi_to_pmid", lambda doi: "999")
    def fake_abs(ids):
        calls.append(list(ids))
        return {"999": "Added paper abstract"}
    monkeypatch.setattr(core.pubmed, "fetch_abstracts", fake_abs)
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); btn(at, "AI 추천").click().run()
    btn(at, "다음: PubMed").click().run(); btn(at, "다음: 스크리닝").click().run(); ok(at)
    n_first = len(calls)
    at.text_input(key="add_doi").set_value("10.1016/j.jaac.2023.04.017"); btn(at, "메타데이터 가져와").click().run(); ok(at)
    added = at.session_state.papers[-1]
    assert added["first_author"] == "Purgato" and added["abstract"] == "Added paper abstract"   # 추가하자마자 초록
    at.run(); at.run()
    assert len(calls) == n_first + 1                                                            # 같은 논문을 다시 요청하지 않음
    # 실패하면 한 번만 경고하고 반복하지 않음
    monkeypatch.setattr(core.pubmed, "fetch_abstracts", lambda ids: (_ for _ in ()).throw(TimeoutError()))
    at.text_input(key="add_doi").set_value("10.1136/bjsports-2022-106195"); btn(at, "메타데이터 가져와").click().run(); ok(at)
    assert at.session_state.papers[-1]["abstract_tried"] and not at.session_state.papers[-1].get("abstract")
    assert any("불러오지 못했습니다" in w.value for w in at.warning)


def test_highlight_keeps_text_visible():
    """형광펜 아래 글씨가 가려지지 않아야 한다 (검은 글씨는 그대로, 흰 바탕만 노랗게)."""
    from core.pdfview import find_evidence, render
    page, rects = find_evidence(PDF, "Sample page 3", 1)
    img, _ = render(PDF, page, rects)
    l, b, r, t = rects[0]
    px = [img.getpixel((x, y)) for x in range(int(l * 1.6), int(r * 1.6)) for y in range(int((576 - t) * 1.6), int((576 - b) * 1.6))]
    assert min(px, key=sum) == (0, 0, 0)                      # 글씨가 검게 보임
    assert (255, 236, 110) in px                              # 바탕은 노란색


def test_page_cache_follows_render_version(monkeypatch):
    """그리기 방식 번호가 바뀌면 캐시된 예전 그림을 쓰지 않고 다시 그린다."""
    import core.pdfview as pv
    import views.step6 as s6
    s6._cached_page.clear()
    calls = []
    real = pv.render
    monkeypatch.setattr(pv, "render", lambda *a: (calls.append(1), real(*a))[1])
    s6._page_img(PDF, 1); s6._page_img(PDF, 1)
    assert len(calls) == 1                                    # 같은 방식이면 캐시 사용
    monkeypatch.setattr(pv, "RENDER_VERSION", 99)
    s6._page_img(PDF, 1)
    assert len(calls) == 2                                    # 방식이 바뀌면 새로 그림
