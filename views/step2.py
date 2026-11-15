import pandas as pd
import streamlit as st
from core import pubmed
from core.state import new_paper, unlock_and_go
from core.ui import header

MAX_LOAD = 500


def pubmed_url(p):
    if p.get("pmid"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"
    if p.get("doi"):
        return f"https://pubmed.ncbi.nlm.nih.gov/?term={p['doi']}%5Bdoi%5D"
    return None


def _search(q):
    count, ids = pubmed.search(q, retmax=MAX_LOAD)
    if count > MAX_LOAD:
        st.warning(f"검색 결과가 {count:,}건입니다. {MAX_LOAD}건 이하가 되도록 1단계에서 검색식을 좁혀 주세요.")
        return
    meta = pubmed.fetch_summaries(ids) if ids else {}
    try:
        abstracts = pubmed.fetch_abstracts(ids) if ids else {}
    except Exception:
        abstracts = {}            # 초록을 못 받아도 검색 결과는 쓴다 (3단계에서 다시 시도 가능)
    st.session_state.papers = []
    for i in ids:
        p = new_paper(pmid=i, **meta.get(i, {}))
        p["abstract"], p["abstract_tried"] = abstracts.get(i), True
        st.session_state.papers.append(p)
    st.session_state.search.update({"query": q, "searched_query": q, "records_identified": count,
                                    "duplicates_removed": 0, "other_sources": 0})
    for k in ("pdfs", "supp", "ext"):
        st.session_state[k] = {}


def render():
    header("2단계", "PubMed 검색",
           "umbrella review는 같은 주제의 메타분석을 빠짐없이 모아야 합니다. 1단계에서 확정한 검색식을 그대로 실행하고, "
           "결과 수는 PRISMA 흐름도에 자동으로 들어갑니다.")
    s, q = st.session_state.search, st.session_state.pico["query"]
    st.markdown("**확정된 검색식**")
    st.code(q, language=None, wrap_lines=True)
    if st.session_state.mode == "demo":
        st.info(s["note"])
    else:
        if st.button("검색 실행", type="primary"):
            with st.spinner("PubMed 검색 중..."):
                try:
                    _search(q)
                except Exception as e:
                    st.error(f"검색에 실패했습니다 ({type(e).__name__}).")
        if s.get("searched_query") and s["searched_query"] != q:
            st.warning("1단계에서 검색식이 바뀌었습니다. ‘검색 실행’을 다시 눌러 주세요.")
    ps = [p for p in st.session_state.papers if p.get("source") == "search"]
    if st.session_state.mode == "api" and not s.get("searched_query"):
        ps = []
        st.caption("‘검색 실행’을 누르면 위 검색식으로 PubMed를 검색해 결과를 보여 줍니다.")
    elif st.session_state.mode == "api":
        st.caption(f"내 검색 결과: PubMed {s['records_identified']:,}건 · 중복 제거 {s['duplicates_removed']}건")
    else:
        st.caption(f"데모 목록: 예시 {s['records_identified']:,}건 (실제 검색 아님)")
    if ps:
        df = pd.DataFrame([{"#": i + 1, "제목": p["title"], "1저자": p["first_author"], "연도": p["year"],
                            "저널": p["journal"], "PubMed": pubmed_url(p)} for i, p in enumerate(ps)])
        st.dataframe(df, hide_index=True, width="stretch", height=min(42 + 35 * len(df), 520),
                     column_config={"PubMed": st.column_config.LinkColumn("PubMed", display_text="열기 ↗"),
                                    "제목": st.column_config.TextColumn(width="large"),
                                    "연도": st.column_config.NumberColumn(format="%d")})
    st.button("다음: 스크리닝", type="primary", disabled=not st.session_state.papers, on_click=unlock_and_go, args=(3,))
