"""그림을 같은 입력에 대해 한 번만 그리도록 캐시한다 (화면 · 썸네일 · 내보내기 공통)."""
import json
import matplotlib.pyplot as plt
import streamlit as st
from core.export import all_formats, fig_bytes
from core.figures import forest_plot, prisma


@st.cache_data(max_entries=32, show_spinner=False)
def prisma_png(counts_json: str, design: str, dpi: int = 150, title: str = "") -> bytes:
    fig = prisma(json.loads(counts_json), design, title or None)
    b = fig_bytes(fig, "png", dpi)
    plt.close(fig)
    return b


@st.cache_data(max_entries=32, show_spinner=False)
def forest_png(rows_json: str, measure: str, dpi: int = 150, title: str = "") -> bytes:
    fig = forest_plot(json.loads(rows_json), measure, title or None)
    b = fig_bytes(fig, "png", dpi)
    plt.close(fig)
    return b


@st.cache_data(max_entries=16, show_spinner="파일을 만드는 중...")
def prisma_files(counts_json: str, design: str, dpi: int, title: str = "") -> dict:
    return all_formats(lambda: prisma(json.loads(counts_json), design, title or None), dpi)


@st.cache_data(max_entries=16, show_spinner="파일을 만드는 중...")
def forest_files(rows_json: str, measure: str, dpi: int, title: str = "") -> dict:
    return all_formats(lambda: forest_plot(json.loads(rows_json), measure, title or None), dpi)


def key(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def default_titles(pico: dict, measures: list[str]) -> dict:
    """그림 제목 기본값: PICO의 중재·노출(I)과 결과(O)를 넣는다. 7단계에서 고칠 수 있다."""
    i = (pico.get("I") or "the intervention").strip()
    o = (pico.get("O") or "the outcome").strip()
    out = {"prisma": "Figure 1. PRISMA flow diagram of the selection of systematic reviews and meta-analyses"}
    for n, m in enumerate(measures, 2):
        out[f"forest_{m}"] = f"Figure {n}. Effect of {i} on {o}: pooled {m}s of included meta-analyses"
    return out


def titles(pico: dict, measures: list[str]) -> dict:
    import streamlit as st
    t = st.session_state.setdefault("fig_titles", {})
    for k, v in default_titles(pico, measures).items():
        t.setdefault(k, v)
    return t
