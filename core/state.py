"""앱 전체가 공유하는 상태(session_state). 탭(세션)마다 따로 생기고, API 키와 PDF도 서버 메모리에만 둔다."""
import copy
import streamlit as st

APP_VERSION = "v23"      # 코드 안에만 두는 버전 번호 (화면에는 표시하지 않음)

STEPS = [(1, "연구 질문 · PICO"), (2, "PubMed 검색"), (3, "스크리닝 · 목록"), (4, "전문 확보"),
         (5, "LLM 추출"), (6, "저자 검토"), (7, "표 · 그림"), (8, "내보내기")]

DEFAULTS = {
    "mode": None,            # None(시작 화면) / "demo" / "api"
    "api_key": None,
    "provider": None,        # "claude" / "gemini"
    "gemini_model": None,
    "page": "step1",         # step1..step8, check
    "reach": 1,              # 열린 단계 (앞 단계를 마쳐야 다음 단계가 열림)
    "pico": {"question": "", "P": "", "I": "", "C": "", "O": "", "query": ""},
    "search": {"query": "", "records_identified": 0, "duplicates_removed": 0, "other_sources": 0, "note": ""},
    "papers": [],
    "pdfs": {},              # {uid: 본문 PDF bytes}
    "supp": {},              # {uid: [(파일 이름, bytes), ...]}
    "ext": {},               # {uid: {"status": ok/fail, "reason": ...}}
    "mock_failed": {},
    "ask_retry": False,
    "durations": [],
    "current_paper": 0,
    "prisma_design": "미니멀 흑백",
    "forest_sort": "효과 크기순 (중재 유리한 것부터)",
    "fig_titles": {},
    "dpi_label": "인쇄용 (300 dpi)",
}


def init_state():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def reset_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()


def go(page: str):
    st.session_state.page = page


def unlock_and_go(step: int):
    st.session_state.reach = max(st.session_state.reach, step)
    st.session_state.page = f"step{step}"


def new_paper(pmid=None, title="", first_author="", year=None, journal="", doi=None, source="search"):
    return {"uid": str(pmid or doi or f"manual-{title[:20]}-{year}"), "pmid": pmid, "doi": doi, "title": title,
            "first_author": first_author, "year": year, "journal": journal, "source": source,
            "included": True, "exclude_reason": None, "fulltext": "missing",
            "stored": None, "extraction": None, "reviewed": False}


def label(p) -> str:
    return f"{p['first_author']} {p['year']}"
