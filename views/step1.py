import streamlit as st
from core.demo import load_raw
from core.providers import suggest_query
from core.query_check import check_query
from core.state import unlock_and_go
from core.ui import header

FIELDS = [("question", "연구 질문"), ("P", "P · 대상"), ("I", "I · 노출/중재"), ("C", "C · 비교"), ("O", "O · 결과")]
HELP = {"P": "P (Population, 대상): 누구를 대상으로 연구하는가?",
        "I": "I (Intervention/Exposure, 중재·노출): 어떤 치료, 중재 또는 요인을 분석하는가?",
        "C": "C (Comparison, 비교): 무엇과 비교하는가?",
        "O": "O (Outcome, 결과): 어떤 효과나 결과를 확인하고자 하는가?"}


def _ai():
    pico = st.session_state.pico
    st.session_state.pop("ai_error", None)
    if st.session_state.mode == "demo":
        st.session_state.q_input = load_raw()["demo_query"]
        st.session_state.ai_note = "데모: 미리 만든 추천 검색식을 넣었습니다."
        return
    try:
        st.session_state.q_input = suggest_query(pico)
        st.session_state.ai_note = "AI가 작성한 검색식입니다. 필요하면 고쳐 주세요."
    except Exception as e:
        from core.providers import error_text
        st.session_state.ai_error = f"검색식을 받지 못했습니다: {error_text(e)} 직접 입력해도 됩니다."


def _next():
    st.session_state.search["query"] = st.session_state.pico["query"]
    unlock_and_go(2)


def render():
    header("1단계", "연구 질문 · PICO",
           "질문이 흐리면 검색도 흐려집니다. PICO(대상·노출/중재·비교·결과)로 나눠 두면 어떤 메타분석을 넣고 뺄지 "
           "기준이 분명해지고, 5단계에서 LLM이 주 결과를 고르는 기준도 됩니다.")
    pico = st.session_state.pico
    for k, _ in FIELDS:
        st.session_state.setdefault(f"in_{k}", pico[k])
    st.session_state.setdefault("q_input", pico["query"])
    if st.session_state.mode == "demo":
        st.info("데모 모드는 예시 주제(운동과 아동·청소년 우울)로 미리 준비된 논문 21편을 씁니다. 여기에 다른 주제를 넣어도 "
                "목록은 바뀌지 않습니다. 내 주제로 실제 PubMed 검색을 하려면 왼쪽 ‘처음부터 다시’ → AI와 API 키로 시작하세요.")
    with st.container(border=True):
        pico["question"] = st.text_input("연구 질문", key="in_question")
        c1, c2 = st.columns(2)
        for col, (k, lab) in zip([c1, c2, c1, c2], FIELDS[1:]):
            pico[k] = col.text_input(lab, key=f"in_{k}", help=HELP[k])
        a, b = st.columns([4, 1])
        a.markdown("**PubMed 검색식**")
        b.button("AI 추천", on_click=_ai, width="stretch", disabled=not (pico["P"].strip() and pico["I"].strip() and pico["O"].strip()),
                 help="P · I · O를 채우면 누를 수 있습니다")
        pico["query"] = st.text_area("PubMed 검색식", key="q_input", height=150, label_visibility="collapsed",
                                     placeholder="‘AI 추천’을 누르거나 직접 입력하세요")
        if st.session_state.get("ai_error"):
            st.error(st.session_state.ai_error)
        elif st.session_state.get("ai_note"):
            st.caption(st.session_state.ai_note)
        errs = check_query(pico["query"])
        if not pico["query"].strip():
            st.caption("P · I · O를 채우고 ‘AI 추천’을 누르면 검색식이 작성됩니다. 언제든 직접 고칠 수 있습니다.")
        elif errs:
            st.error("✗ 고칠 부분이 있습니다\n\n" + "\n".join(f"- {e}" for e in errs))
        else:
            st.success("✓ 검색식 형식이 올바릅니다.")
        st.caption("칸 밖을 누르거나 Ctrl+Enter를 누르면 형식(괄호, 따옴표, 연산자, 필드 태그)을 검사합니다. "
                   "실제 결과 수는 2단계에서 확인합니다.")
    st.button("다음: PubMed 검색", type="primary", disabled=bool(errs), on_click=_next)
