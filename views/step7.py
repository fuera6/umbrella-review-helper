"""7단계: characteristics table, PRISMA 흐름도(디자인 4종), forest plot(지표별, 전체 효과·이질성 포함)."""
import html
import streamlit as st
from core.figures import PRISMA_DESIGNS
from core.prisma import counts
from core.results import CHAR_COLS, SORTS, characteristics_rows, forest_rows, is_num, measures_present, reviewed, sort_rows
from core.state import unlock_and_go
from core.ui import header, warn
from views.figcache import forest_png, key, prisma_png, titles
from views import source_check

NOTE = ("AMSTAR 2 = A MeaSurement Tool to Assess systematic Reviews 2; RCT = randomized controlled trial; RR = risk ratio; "
        "OR = odds ratio; HR = hazard ratio; SMD = standardized mean difference; MD = mean difference.")


def table_html(rows, caption=True, limit=None):
    if not rows:
        return "<p>검토를 마친 논문이 없습니다.</p>"
    num = {"No. of studies", "Total sample"}
    cell = lambda c, v: html.escape(f"{int(v):,}" if c in num and is_num(v) else ("" if v is None else str(v)))
    head = "".join(f'<th class="{"num" if c in num else ""}">{c}</th>' for c in CHAR_COLS)
    body = "".join("<tr>" + "".join(f'<td class="{"num" if c in num else ""}">{cell(c, r[c])}</td>' for c in CHAR_COLS) + "</tr>"
                   for r in rows[:limit])
    cap = "<caption>Table 1. Characteristics of included systematic reviews and meta-analyses</caption>" if caption else ""
    return f'<div style="overflow-x:auto"><table class="journal">{cap}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render():
    header("7단계", "표 · 그림", "검토를 마친 값으로 characteristics table, PRISMA 흐름도, forest plot을 만듭니다.")
    papers = st.session_state.papers
    all_rows = forest_rows(papers)
    tt = titles(st.session_state.pico, measures_present(all_rows))
    t1, t2, t3 = st.tabs(["Characteristics table", "PRISMA 흐름도", "Forest plot"])
    with t1:
        st.markdown(table_html(characteristics_rows(papers)) + f'<div class="ur-tnote">{NOTE}</div>', unsafe_allow_html=True)
        if reviewed(papers):
            source_check.table_panel(reviewed(papers))
    with t2:
        st.session_state.prisma_design = st.radio("디자인", PRISMA_DESIGNS, horizontal=True,
                                                  index=PRISMA_DESIGNS.index(st.session_state.prisma_design))
        tt["prisma"] = st.text_input("그림 제목", tt["prisma"], key="title_prisma")
        c = counts(st.session_state.search, papers)
        for m in c["mismatch"]:
            warn(f"⚠ {m}")
        st.image(prisma_png(key(c), st.session_state.prisma_design, 150, tt["prisma"]), width=680)
        st.caption("숫자는 2~4단계 기록에서 자동으로 셉니다. 용어는 PRISMA 2020 서식(CC BY 4.0)을 umbrella review에 맞게 "
                   "records → reviews로 바꿨습니다.")
    with t3:
        st.session_state.forest_sort = st.selectbox("행 정렬", SORTS, index=SORTS.index(st.session_state.forest_sort),
                                                    help="8단계에서 내보내는 그림에도 같은 순서가 쓰입니다.")
        rows = sort_rows(forest_rows(papers), st.session_state.forest_sort)
        ms = measures_present(rows)
        if not ms:
            st.info("그릴 값이 없습니다. 6단계에서 효과 지표와 추정치 · 신뢰구간을 확인해 주세요.")
        for m in ms:
            if len(ms) > 1:
                st.markdown(f"#### {m}")
            tt[f"forest_{m}"] = st.text_input("그림 제목", tt[f"forest_{m}"], key=f"title_forest_{m}",
                                              help="기본 제목은 1단계 PICO의 중재·노출(I)과 결과(O)로 만들었습니다. 영어로 고쳐 쓰면 논문용으로 좋습니다.")
            sub_rows = [r for r in rows if r["measure"] == m]
            st.image(forest_png(key(sub_rows), m, 150, tt[f"forest_{m}"]), width="stretch")
            source_check.forest_panel(sub_rows, papers)
        st.caption("전체 효과(초록 마름모)와 이질성은 포함된 메타분석들의 요약값을 무작위 효과 모형(REML)으로 다시 합성한 결과입니다. "
                   "서로 다른 효과 지표는 섞지 않습니다.")
    st.button("다음: 내보내기", type="primary", on_click=unlock_and_go, args=(8,))
