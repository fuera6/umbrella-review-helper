"""8단계(마지막): 그림 PNG·SVG·PDF·PPT, characteristics table XLSX 내보내기."""
import streamlit as st
from core.export import DPI, MIME, table_xlsx
from core.prisma import counts
from core.results import amstar_rows, characteristics_rows, forest_rows, measures_present, sort_rows
from core.state import go
from views.figcache import forest_files, forest_png, key, prisma_files, prisma_png, titles
from views.step7 import table_html

FMTS = [("png", "PNG"), ("svg", "SVG"), ("pdf", "PDF"), ("pptx", "PPT")]


def _card(name, thumb_png, files, base):
    with st.container(border=True):
        a, b = st.columns([1, 2])
        a.image(thumb_png, width="stretch")
        with b:
            st.markdown(f"#### {name}")
            cols = st.columns(4)
            for col, (fmt, lab) in zip(cols, FMTS):
                if col.download_button(lab, files[fmt], f"{base}.{fmt}", MIME[fmt], key=f"dl_{base}_{fmt}", width="stretch"):
                    st.session_state.setdefault("saved", set()).add(f"{base}.{fmt}")
            done = [lab for fmt, lab in FMTS if f"{base}.{fmt}" in st.session_state.get("saved", set())]
            if done:
                st.markdown(f":green[✓ {' · '.join(done)} 저장됨]")


def render():
    st.markdown('<div class="ur-hero"><div class="mark">✓</div><div><div class="ur-eyebrow">8단계 · 마지막 단계</div>'
                '<h2>표와 그림이 완성되었습니다</h2><p>필요한 파일을 내려받으면 umbrella review 작업이 끝납니다.</p></div></div>',
                unsafe_allow_html=True)
    papers = st.session_state.papers
    labels = list(DPI)
    st.session_state.dpi_label = st.selectbox("그림 해상도 (PNG · PDF · PPT에 적용, SVG는 항상 선명)", labels,
                                              index=labels.index(st.session_state.dpi_label))
    dpi = DPI[st.session_state.dpi_label]
    c = counts(st.session_state.search, papers)
    ck, design = key(c), st.session_state.prisma_design
    rows = sort_rows(forest_rows(papers), st.session_state.forest_sort)   # 7단계에서 고른 순서
    ms = measures_present(rows)
    tt = titles(st.session_state.pico, ms)                                # 7단계에서 정한 그림 제목
    _card(f"PRISMA flow diagram ({design})", prisma_png(ck, design, 60, tt["prisma"]),
          prisma_files(ck, design, dpi, tt["prisma"]), "PRISMA_flow_diagram")
    for i, m in enumerate(ms, 1):
        rk = key([r for r in rows if r["measure"] == m])
        name, base = ("Forest plot", "Forest_plot") if len(ms) == 1 else (f"Forest plot ({i})", f"Forest_plot_{i}")
        _card(name, forest_png(rk, m, 60, tt[f"forest_{m}"]), forest_files(rk, m, dpi, tt[f"forest_{m}"]), base)
    with st.container(border=True):
        a, b = st.columns([1, 2])
        a.markdown(f'<div style="font-size:7px;max-height:180px;overflow:hidden">{table_html(characteristics_rows(papers), False, 6)}</div>',
                   unsafe_allow_html=True)
        with b:
            st.markdown("#### Characteristics table")
            st.caption("시트 2개: Characteristics · AMSTAR 2 items (논문별 16문항 답과 종합 등급)")
            if st.download_button("XLSX", table_xlsx(characteristics_rows(papers), amstar_rows(papers)),
                                  "Characteristics_table.xlsx", MIME["xlsx"], type="primary", key="dl_table"):
                st.session_state.setdefault("saved", set()).add("table")
            if "table" in st.session_state.get("saved", set()):
                st.markdown(":green[✓ XLSX 저장됨]")
    st.button("← 표 · 그림으로 돌아가기", on_click=go, args=("step7",))
