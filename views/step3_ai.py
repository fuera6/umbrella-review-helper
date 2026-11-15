"""3단계 보조: 초록 불러오기, AI 포함/제외/보류 추천, 초록 보기 창."""
import streamlit as st
from core import pubmed
from core.screening import BADGE, demo_recommendation
from core.state import label


def need_abstract(p):
    return not p.get("abstract") and not p.get("abstract_tried") and (p.get("pmid") or p.get("doi"))


def load_abstracts():
    """초록이 없는 논문의 초록을 PubMed에서 자동으로 가져온다 (3단계에 들어오거나 논문을 추가했을 때).
    실패해도 같은 논문을 계속 다시 시도하지 않도록 '시도함'으로 표시한다."""
    papers = [p for p in st.session_state.papers if need_abstract(p)]
    if not papers:
        return
    bar = st.progress(0.0, text="PubMed에서 초록을 불러오는 중...")
    try:
        for i, p in enumerate(papers):
            if not p.get("pmid") and p.get("doi"):
                p["pmid"] = pubmed.doi_to_pmid(p["doi"])
            bar.progress((i + 1) / (len(papers) * 2), text=f"PMID 확인 중 {i + 1}/{len(papers)}")
        pmids = [p["pmid"] for p in papers if p.get("pmid")]
        abstracts = pubmed.fetch_abstracts(pmids) if pmids else {}
        for p in papers:
            p["abstract"], p["abstract_tried"] = abstracts.get(p.get("pmid")), True
        bar.progress(1.0, text="완료")
    except Exception as e:
        for p in papers:
            p["abstract_tried"] = True
        st.session_state.add_msg = ("warning", f"초록 {len(papers)}편을 PubMed에서 불러오지 못했습니다 ({type(e).__name__}). "
                                               "이 논문들은 ‘초록 없음’으로 두고, AI는 ‘보류’로 추천합니다.")
    st.rerun()


def run_ai():
    papers = st.session_state.papers
    todo = [p for p in papers if not p.get("ai_rec")]
    if st.session_state.mode == "demo":
        for p in todo:
            p["ai_rec"] = demo_recommendation(p)
        return
    for p in todo:
        if not p.get("abstract"):
            p["ai_rec"] = {"decision": "보류", "reason": "초록 없음 — 제목만으로는 판단하기 어렵습니다"}
    items = [{"id": p["uid"], "title": p["title"], "abstract": p["abstract"]} for p in todo if p.get("abstract")]
    if not items:
        return
    from core.providers import error_text, screen
    with st.spinner(f"AI가 초록 {len(items)}편을 검토하는 중..."):
        try:
            res = screen(st.session_state.pico, items)
        except Exception as e:
            st.error(f"AI 추천을 받지 못했습니다: {error_text(e)}")
            return
    for p in todo:
        if p["uid"] in res:
            p["ai_rec"] = res[p["uid"]]
        elif p.get("abstract"):
            p["ai_rec"] = {"decision": "보류", "reason": "AI 응답에 빠져 있어 다시 추천이 필요합니다"}
    st.rerun()


def apply_ai():
    """포함 추천 → 체크, 제외 추천 → 체크 해제 + 사유, 보류 → 그대로."""
    for p in st.session_state.papers:
        rec = p.get("ai_rec")
        if not rec:
            continue
        if rec["decision"] == "포함":
            p["included"], p["exclude_reason"] = True, None
        elif rec["decision"] == "제외":
            p["included"], p["exclude_reason"] = False, f"AI 추천: {rec['reason']}"[:120]
    st.session_state["screen_ver"] = st.session_state.get("screen_ver", 0) + 1


def badge(p):
    rec = p.get("ai_rec")
    return BADGE[rec["decision"]] if rec else ""


@st.dialog("초록 보기", width="large")
def abstract_dialog(uid):
    p = next(x for x in st.session_state.papers if x["uid"] == uid)
    st.markdown(f"**{p['title']}**")
    st.caption(f"{label(p)} · {p['journal']}" + (f" · PMID {p['pmid']}" if p.get("pmid") else ""))
    rec = p.get("ai_rec")
    if rec:
        st.markdown(f"**AI 추천:** {BADGE[rec['decision']]} — {rec['reason']}")
    st.markdown(f"**현재 상태:** {'포함' if p['included'] else '제외'}")
    st.divider()
    st.write(p["abstract"])
    st.divider()
    a, b, c = st.columns(3)
    if a.button("포함으로 표시", type="primary", width="stretch"):
        p["included"], p["exclude_reason"] = True, None
        st.session_state["screen_ver"] = st.session_state.get("screen_ver", 0) + 1
        st.rerun()
    reason = st.text_input("제외 사유", value=p.get("exclude_reason") or (rec["reason"] if rec and rec["decision"] == "제외" else ""))
    if b.button("제외로 표시", width="stretch"):
        p["included"], p["exclude_reason"] = False, reason.strip() or "초록 검토 후 제외"
        st.session_state["screen_ver"] = st.session_state.get("screen_ver", 0) + 1
        st.rerun()
    if c.button("닫기", width="stretch"):
        st.rerun()
