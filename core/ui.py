"""공통 화면 요소: 글꼴·색, 왼쪽 메뉴(단계 잠금), '이 단계는 왜?' 상자, 근거 표시."""
import html
import streamlit as st
from core.state import STEPS, go, reset_state

NAVY, BLUE = "#10213D", "#2457D6"
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, textarea, select {{
  font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; }}
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #E6EAF2; }}
[data-testid="stSidebar"] .stButton button {{ width: 100%; justify-content: flex-start; text-align: left;
  background: transparent; border: none; color: #C9D1E0; }}
[data-testid="stSidebar"] .stButton button[kind="primary"] {{ background: {BLUE}; color: #fff; font-weight: 700; }}
[data-testid="stSidebar"] .stButton button:disabled {{ color: #6F7C96; opacity: 1; }}
[data-testid="stSidebar"] .stButton button:hover:enabled {{ background: rgba(255,255,255,.08); }}
.ur-badge {{ background: #1B2D4F; border-radius: 8px; padding: 9px 13px; font-size: 13.5px; margin: 4px 0 16px; }}
.ur-eyebrow {{ color: {BLUE}; font-weight: 700; font-size: 14px; margin-bottom: -8px; }}
.ur-why {{ background: #E7EDFB; color: {NAVY}; border-radius: 10px; padding: 13px 18px; margin: 4px 0 20px; line-height: 1.6; }}
.ur-warn {{ color: #C62828; font-size: 14px; margin: 2px 0 6px; }}
.ur-ev {{ color: {BLUE}; font-size: 13px; margin: -6px 0 10px; }}
.ur-foot {{ color: #5B6475; font-size: 13px; text-align: center; line-height: 1.8; }}
.ur-hero {{ display: flex; gap: 18px; align-items: center; background: #E6F4EA; border-radius: 14px; padding: 20px 24px; margin-bottom: 18px; }}
.ur-hero .mark {{ flex: none; width: 52px; height: 52px; border-radius: 50%; background: #1B7F3B; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; }}
.ur-hero h2 {{ margin: 0; color: {NAVY}; }} .ur-hero p {{ margin: 4px 0 0; color: {NAVY}; }}
table.journal {{ border-collapse: collapse; background: #fff; color: {NAVY}; font-size: 13.5px; width: 100%; }}
table.journal caption {{ text-align: left; font-weight: 700; padding: 0 0 8px; color: {NAVY}; }}
table.journal th {{ text-align: left; border-top: 2px solid {NAVY}; border-bottom: 1px solid {NAVY}; padding: 7px 9px; vertical-align: bottom; }}
table.journal td {{ border-bottom: 1px solid #E3E6EC; padding: 7px 9px; vertical-align: top; }}
table.journal tr:last-child td {{ border-bottom: 2px solid {NAVY}; }}
table.journal td.num, table.journal th.num {{ text-align: right; }}
.ur-tnote {{ font-size: 12px; color: #5B6475; padding-top: 6px; }}
/* 6단계 검토 상태 색: 완료 = 초록, 지금 보는 논문 = 파란 테두리 */
[class*="st-key-rvnav_done_"] button {{ background: #E6F4EA; color: #1B7F3B; border: 1px solid #9FD3AE; }}
[class*="st-key-rvnav_donecur_"] button {{ background: #1B7F3B; color: #fff; border: 1px solid #1B7F3B; font-weight: 700; }}
[class*="st-key-rvnav_cur_"] button {{ border: 2px solid {BLUE}; color: {BLUE}; font-weight: 700; }}
[class*="st-key-rv_main_done"] button {{ background: #1B7F3B; color: #fff; border: 1px solid #1B7F3B; font-weight: 700; }}
[class*="st-key-rv_main_done"] button:hover {{ background: #166A31; color: #fff; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


LEAVE_GUARD = """
<script>
// 새로 고침·탭 닫기 전에 브라우저 확인 창을 띄운다 (문구는 브라우저가 정함)
try {
  const w = window.parent;
  if (!w.__urGuard) {
    w.addEventListener("beforeunload", function (e) { e.preventDefault(); e.returnValue = ""; return ""; });
    w.__urGuard = true;
  }
} catch (err) {}
</script>
"""


def leave_guard():
    import streamlit.components.v1 as components
    components.html(LEAVE_GUARD, height=0)


def sidebar():
    with st.sidebar:
        st.markdown("### Umbrella Review 도우미")
        if st.session_state.mode == "api":
            from core.providers import model_name
            label = f"{'Gemini' if st.session_state.provider == 'gemini' else 'Claude'} 연결됨 · {model_name()}"
        else:
            label = "데모 모드 · 기준값 데이터"
        st.markdown(f'<div class="ur-badge">{label}</div>', unsafe_allow_html=True)
        if st.session_state.get("model_notice"):
            st.caption("ℹ️ " + st.session_state.model_notice)
        st.markdown('<div class="ur-badge" style="background:#5C2A1E;color:#FFE4D6">⚠ 새로 고치거나 탭을 닫으면 '
                    '입력한 내용, 올린 PDF, 추출 결과가 모두 사라집니다.</div>', unsafe_allow_html=True)
        for num, name in STEPS:
            page = f"step{num}"
            st.button(f"{num}. {name}", key=f"nav_{num}", type="primary" if st.session_state.page == page else "secondary",
                      disabled=num > st.session_state.reach, on_click=go, args=(page,),
                      help=None if num <= st.session_state.reach else "앞 단계를 먼저 마쳐 주세요")
        st.divider()
        st.button("처음부터 다시", key="nav_reset", on_click=reset_state)


def header(eyebrow: str, title: str, why: str | None = None):
    st.markdown(f'<div class="ur-eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    if why:
        st.markdown(f'<div class="ur-why"><b>이 단계는 왜?</b> {why}</div>', unsafe_allow_html=True)


def warn(text: str):
    st.markdown(f'<p class="ur-warn">{html.escape(text)}</p>', unsafe_allow_html=True)


def evidence(f: dict):
    ev, pg = f.get("evidence"), f.get("page")
    if not ev:
        warn("근거를 찾지 못했습니다. 원문에서 직접 확인해 주세요.")
        return
    st.markdown(f'<p class="ur-ev">{"p. " + str(pg) + " · " if pg else ""}“{html.escape(ev)}”</p>', unsafe_allow_html=True)
