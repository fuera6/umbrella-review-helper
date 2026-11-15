"""Umbrella Review 도우미 — 진입점. 실행: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Umbrella Review 도우미", page_icon="☂️", layout="wide")

from core.state import init_state  # noqa: E402
from core.ui import inject_css, leave_guard, sidebar  # noqa: E402
from views import start, step1, step2, step3, step4, step5, step6, step7, step8  # noqa: E402

init_state()
inject_css()
PAGES = {"step1": step1.render, "step2": step2.render, "step3": step3.render, "step4": step4.render,
         "step5": step5.render, "step6": step6.render, "step7": step7.render, "step8": step8.render}

if st.session_state.mode is None:
    start.render()
else:
    page = st.session_state.page
    if page.startswith("step") and int(page[4:]) > st.session_state.reach:   # 잠긴 단계로 못 가게
        page = st.session_state.page = f"step{st.session_state.reach}"
    sidebar()
    leave_guard()          # 작업 중에는 새로 고침·탭 닫기 전에 확인 창
    PAGES[page]()
