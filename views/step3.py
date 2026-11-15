import pandas as pd
import streamlit as st
from core import pubmed
from core.demo import load_raw
from core.state import new_paper, unlock_and_go
from core.ui import header, warn
from views import step3_ai

REASONS = "메타분석 아님 · 결과 불일치 · 대상 불일치 · 중재 불일치 · 동물 연구 · 중복 출판 · umbrella review/overview"


def source_label() -> str:
    s, ps = st.session_state.search, st.session_state.papers
    added = sum(p.get("source") != "search" for p in ps)
    if st.session_state.mode == "demo":
        return "데모 목록 (예시 논문, 실제 검색 아님)" + (f" + 직접 추가 {added}편" if added else "")
    return f"내 목록: PubMed 검색 {sum(p.get('source') == 'search' for p in ps)}편" + (f" + 직접 추가 {added}편" if added else "")


def _set_all(included: bool):
    for p in st.session_state.papers:
        p["included"] = included
        if included:
            p["exclude_reason"] = None
    _bump()


def _bump():
    st.session_state["screen_ver"] = st.session_state.get("screen_ver", 0) + 1


def _add(meta: dict, source: str):
    papers, s = st.session_state.papers, st.session_state.search
    doi = (meta.get("doi") or "").lower()
    if any((doi and (p.get("doi") or "").lower() == doi) or (meta.get("pmid") and p.get("pmid") == meta["pmid"]) for p in papers):
        s["duplicates_removed"] += 1
        s["other_sources"] += 1
        st.session_state.add_msg = ("warning", "이미 목록에 있는 논문입니다. 중복으로 집계했습니다.")
        return
    p = new_paper(source=source, **meta)
    if any(x["uid"] == p["uid"] for x in papers):
        p["uid"] += f"-{len(papers)}"
    papers.append(p)
    s["other_sources"] += 1
    _bump()
    st.session_state.add_msg = ("success", f"추가했습니다: {meta['title'][:70]} (초록은 PubMed에서 자동으로 가져옵니다)")


def _add_doi():
    d = st.session_state.get("add_doi", "").strip()
    if not d:
        return
    if st.session_state.mode == "demo":
        meta = load_raw()["doi_lookup"].get(d)
        if not meta:
            st.session_state.add_msg = ("error", "데모에서는 예시 DOI만 조회됩니다. 실제 버전은 PubMed에서 찾습니다.")
            return
        return _add({**meta, "doi": d}, "doi")
    try:
        pmid = pubmed.doi_to_pmid(d)
        if not pmid:
            st.session_state.add_msg = ("error", "PubMed에서 이 DOI를 찾지 못했습니다. ‘직접 입력’으로 추가해 주세요.")
            return
        meta = pubmed.fetch_summaries([pmid]).get(pmid, {})
        _add({**meta, "pmid": pmid, "doi": meta.get("doi") or d}, "doi")
    except Exception as e:
        st.session_state.add_msg = ("error", f"PubMed에 연결하지 못했습니다 ({type(e).__name__}).")


def _add_manual():
    g = lambda k: st.session_state.get(k, "").strip() if isinstance(st.session_state.get(k), str) else st.session_state.get(k)
    title, author, year = g("m_title"), g("m_author"), g("m_year")
    if not title or not author or not year:
        st.session_state.add_msg = ("error", "제목, 1저자, 연도는 꼭 입력해 주세요.")
        return
    _add({"title": title, "first_author": author, "year": int(year), "journal": g("m_journal") or "",
          "doi": g("m_doi") or None, "pmid": g("m_pmid") or None}, "manual")


def _remove():
    uid = st.session_state.get("rm_sel")
    papers = st.session_state.papers
    p = next((x for x in papers if x["uid"] == uid), None)
    if not p:
        return
    papers.remove(p)
    s = st.session_state.search   # 완전히 제거: 집계에서도 빠지도록 원래 출처 건수에서 뺀다
    if p.get("source") == "search":
        s["records_identified"] = max(0, s["records_identified"] - 1)
    else:
        s["other_sources"] = max(0, s["other_sources"] - 1)
    for k in ("pdfs", "supp", "ext"):
        st.session_state[k].pop(uid, None)
    _bump()
    st.session_state.add_msg = ("success", f"제거했습니다: {p['title'][:70]}")


@st.dialog("최종 논문 목록 확인", width="large")
def final_dialog():
    inc = [p for p in st.session_state.papers if p["included"]]
    st.caption(source_label())
    st.markdown(f"포함 **{len(inc)}편** · 제외 {len(st.session_state.papers) - len(inc)}편. 이 목록으로 전문 확보 단계를 진행합니다.")
    no_reason = [p for p in st.session_state.papers if not p["included"] and not p["exclude_reason"]]
    if no_reason:
        warn(f"⚠ 제외 사유가 없는 논문이 {len(no_reason)}편 있습니다.")
    df = pd.DataFrame([{"#": i + 1, "Title": p["title"], "First author": p["first_author"], "Year": p["year"],
                        "Journal": p["journal"], "DOI": p.get("doi") or "", "PMID": p.get("pmid") or ""}
                       for i, p in enumerate(inc)])
    st.dataframe(df, hide_index=True, height=min(42 + 35 * len(df), 380))
    c1, c2, c3 = st.columns(3)
    if c1.button("돌아가서 고치기", width="stretch"):
        st.rerun()
    c2.download_button("CSV 저장", df.to_csv(index=False).encode("utf-8-sig"), "final_review_list.csv", "text/csv",
                       width="stretch")
    if c3.button("확인하고 다음 단계로", type="primary", width="stretch"):
        unlock_and_go(4)
        st.rerun()


def render():
    header("3단계", "스크리닝 · 목록 관리",
           "AI가 초록을 읽고 포함 · 제외 · 보류를 추천하면, 저자가 초록을 직접 보고 최종 포함 여부를 정합니다. "
           "포함을 해제한 논문은 PRISMA에서 ‘제외’로 집계되므로 제외 사유를 남겨 주세요.")
    papers = st.session_state.papers
    n_in = sum(p["included"] for p in papers)
    st.caption(f"{source_label()} · 전체 {len(papers)} · 포함 {n_in} · 제외 {len(papers) - n_in}")
    if papers:
        step3_ai.load_abstracts()          # 초록이 없는 논문은 들어오자마자 자동으로 가져옴 (추가한 논문 포함)
        with st.container(border=True):
            n_abs = sum(bool(p.get("abstract")) for p in papers)
            n_rec = sum(bool(p.get("ai_rec")) for p in papers)
            st.markdown(f"**AI 스크리닝 도우미** · 초록 {n_abs}/{len(papers)}편 · AI 추천 {n_rec}/{len(papers)}편")
            y, z = st.columns(2)
            if y.button("AI 추천 받기", type="primary", disabled=n_rec == len(papers), width="stretch"):
                step3_ai.run_ai()
            z.button("AI 추천대로 체크하기", disabled=not n_rec, width="stretch", on_click=step3_ai.apply_ai,
                     help="포함 추천은 체크, 제외 추천은 체크 해제(사유 자동 입력), 보류는 그대로 둡니다. 결과는 표에서 다시 고칠 수 있습니다.")
            if st.session_state.mode == "demo":
                st.caption("데모: AI 추천은 실제 AI 판단이 아니라 참고 논문의 포함 여부를 보여 주는 예시입니다.")
            else:
                st.caption("초록이 없는 논문은 AI에 보내지 않고 ‘보류’로 둡니다. AI 추천은 참고용이며, 최종 결정은 저자가 합니다.")
        a, b, _ = st.columns([1, 1, 6])
        a.button("모두 선택", on_click=_set_all, args=(True,), width="stretch")
        b.button("모두 해제", on_click=_set_all, args=(False,), width="stretch")
        df = pd.DataFrame([{"포함": p["included"], "제목": p["title"], "1저자 · 연도": f"{p['first_author']} ({p['year']})",
                            "초록": "있음" if p.get("abstract") else "없음", "AI 추천": step3_ai.badge(p),
                            "AI 이유": (p.get("ai_rec") or {}).get("reason", ""),
                            "제외 사유": "" if p["included"] else (p["exclude_reason"] or "")}
                           for p in papers], index=[p["uid"] for p in papers])
        edited = st.data_editor(
            df, hide_index=True, width="stretch", disabled=["제목", "1저자 · 연도", "초록", "AI 추천", "AI 이유"],
            key=f"screen_{st.session_state.get('screen_ver', 0)}",
            column_config={"제목": st.column_config.TextColumn(width="large"),
                           "AI 이유": st.column_config.TextColumn(width="medium"),
                           "제외 사유": st.column_config.TextColumn(help=f"포함을 해제한 논문에만 저장됩니다. 직접 쓰거나 예: {REASONS}")})
        changed = False
        for p in papers:
            row = edited.loc[p["uid"]]
            inc = bool(row["포함"])
            reason = None if inc else (str(row["제외 사유"]).strip() or None)
            if inc != p["included"] or reason != p["exclude_reason"]:
                changed = True
            p["included"], p["exclude_reason"] = inc, reason
        if changed and any(bool(edited.loc[p["uid"], "제외 사유"]) and p["included"] for p in papers):
            _bump()          # 포함된 논문에 쓴 사유는 지워서 표를 다시 그린다
            st.rerun()
        missing = [p for p in papers if not p["included"] and not p["exclude_reason"]]
        if missing:
            warn(f"제외 사유가 없는 논문이 {len(missing)}편 있습니다.")
        st.caption(f"제외 사유는 ‘포함’을 해제한 논문에만 입력됩니다. 직접 쓰거나 예시를 참고하세요: {REASONS}")
        with_abs = [p for p in papers if p.get("abstract")]
        c1, c2 = st.columns([4, 1])
        if with_abs:
            sel = c1.selectbox("초록 보기", [p["uid"] for p in with_abs], label_visibility="collapsed",
                               format_func=lambda u: next(f"{p['title']} ({p['first_author']}, {p['year']})" for p in with_abs if p["uid"] == u))
            if c2.button("초록 보기", width="stretch"):
                step3_ai.abstract_dialog(sel)
        no_abs = len(papers) - len(with_abs)
        if no_abs:
            st.caption(f"초록이 없는 논문 {no_abs}편은 초록 보기 목록에 나오지 않습니다.")

    msg = st.session_state.pop("add_msg", None)
    if msg:
        getattr(st, msg[0])(msg[1])
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("#### 논문 추가")
        t1, t2 = st.tabs(["DOI로 자동 입력", "직접 입력"])
        with t1:
            st.text_input("DOI", key="add_doi", placeholder="예: 10.1016/j.jaac.2023.04.017")
            st.button("메타데이터 가져와 추가", type="primary", on_click=_add_doi)
            if st.session_state.mode == "demo":
                st.caption("데모에서 조회되는 예시 DOI: " + " · ".join(load_raw()["doi_lookup"]))
            else:
                st.caption("PubMed에서 제목·1저자·연도·저널을 자동으로 가져옵니다.")
        with t2:
            a, b = st.columns(2)
            a.text_input("제목 *", key="m_title")
            b.text_input("저널", key="m_journal")
            a.text_input("1저자 *", key="m_author")
            b.number_input("연도 *", min_value=1900, max_value=2100, value=None, step=1, key="m_year")
            a.text_input("DOI", key="m_doi")
            b.text_input("PMID", key="m_pmid")
            st.button("행 추가", type="primary", on_click=_add_manual)
            st.caption("PubMed에 없는 논문을 직접 넣을 때 씁니다. * 표시는 필수입니다.")
    with c2, st.container(border=True):
        st.markdown("#### 논문 제거")
        if papers:
            st.selectbox("목록에서 완전히 지울 논문", [p["uid"] for p in papers], key="rm_sel",
                         format_func=lambda u: next(f"{p['title']} ({p['first_author']}, {p['year']})" for p in papers if p["uid"] == u))
            st.button("제거", on_click=_remove)
    if st.button("다음: 전문 확보", type="primary", disabled=not any(p["included"] for p in papers)):
        final_dialog()
