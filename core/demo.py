"""데모 모드: 데모 데이터를 불러와 session_state를 채운다."""
import copy
import json
from pathlib import Path
import streamlit as st
from core.state import DEFAULTS

DEMO_PATH = Path(__file__).resolve().parent.parent / "data" / "demo" / "demo_results.json"


@st.cache_data
def load_raw():
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def load_demo_into_state():
    raw = copy.deepcopy(load_raw())
    st.session_state.pico = {**DEFAULTS["pico"], **raw.get("pico", {})}
    st.session_state.search = {**DEFAULTS["search"], **raw.get("search", {})}
    st.session_state.papers = raw["papers"]
