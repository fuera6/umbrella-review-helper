"""시작 화면: AI(Claude / Gemini)와 API 키를 넣거나, 키 없이 데모로 시작."""
import streamlit as st
from core.demo import load_demo_into_state
from core.providers import PROVIDERS, check_key
from core.state import reset_state


def _start_demo():
    reset_state()                       # 이전에 남은 목록·파일·입력값을 모두 지우고 시작
    load_demo_into_state()
    st.session_state.mode, st.session_state.api_key, st.session_state.page = "demo", None, "step1"


def _start_api(key, provider, model, models):
    reset_state()                       # 데모 목록이 남아 있지 않도록 깨끗한 상태에서 시작
    st.session_state.update(api_key=key, provider=provider, mode="api", page="step1",
                            gemini_model=model, gemini_models=models)


def render():
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="ur-eyebrow" style="text-align:center">생물정보학 및 소프트웨어 코딩 · 팀프로젝트</div>',
                    unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center'>Umbrella Review 도우미</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#5B6475'>PubMed 검색부터 Characteristics table · PRISMA 흐름도 · forest plot까지 한 번에.</p>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            provider = st.radio("사용할 AI", list(PROVIDERS), format_func=PROVIDERS.get, horizontal=True, key="provider_choice")
            if provider == "gemini":
                key = st.text_input("Gemini API 키", type="password", placeholder="Google AI Studio에서 받은 키", key="key_gemini")
                st.caption("키는 이 탭에서만 쓰이고 저장되지 않습니다. 무료 등급은 분당·일일 요청 수 제한이 있고, "
                           "Google 약관상 무료 등급 입력은 서비스 개선에 쓰일 수 있으니 공개된 논문만 올리세요.")
            else:
                key = st.text_input("Claude API 키", type="password", placeholder="sk-ant-...", key="key_claude")
                st.caption("키는 이 탭에서만 쓰이고 저장되지 않습니다. 사용 요금은 본인 계정에 청구됩니다.")
            if st.button("키 확인", type="primary", width="stretch"):
                with st.spinner("키를 확인하는 중..."):
                    ok, msg, models = check_key(provider, key.strip())
                st.session_state.key_check = {"ok": ok, "msg": msg, "models": models, "provider": provider, "key": key.strip()}
            kc = st.session_state.get("key_check")
            if kc and kc["provider"] == provider:
                if not kc["ok"]:
                    st.error(kc["msg"])
                else:
                    st.success(kc["msg"])
                    if provider == "gemini":
                        st.selectbox("Gemini 모델", kc["models"], key="gemini_model_choice",
                                     help="보통 이름에 flash가 들어간 모델이 무료 한도가 넉넉하고 빠릅니다.")
                    if st.button("이 키로 시작", type="primary", width="stretch"):
                        chosen = st.session_state.get("gemini_model_choice")
                        if provider == "gemini":     # 고른 모델이 실제로 되는지 짧게 확인, 안 되면 다음 모델로
                            from core.gemini import error_message, pick_working_model
                            try:
                                with st.spinner("모델을 확인하는 중..."):
                                    working = pick_working_model(kc["key"], kc["models"], chosen)
                            except Exception as e:
                                st.error(error_message(e, kc["key"]))
                                st.stop()
                            notice = f"{chosen} 모델은 지금 쓸 수 없어 {working}(으)로 바꿨습니다." if working != chosen else None
                            chosen = working
                        else:
                            notice = None
                        _start_api(kc["key"], provider, chosen, kc["models"])
                        if notice:
                            st.session_state.model_notice = notice
                        st.rerun()
            st.markdown("<p style='text-align:center;color:#8A93A3'>또는</p>", unsafe_allow_html=True)
            st.button("키 없이 데모로 시작 — 예시 주제(운동과 아동·청소년 우울)로 1~8단계 체험", width="stretch",
                      on_click=_start_demo)
        st.markdown('<p class="ur-foot">교육용 프로토타입입니다. 진단 · 치료 · 처방 도구가 아닙니다.<br>'
                    f'출판된 논문만 분석합니다. 환자 정보를 올리지 마세요.</p>', unsafe_allow_html=True)
