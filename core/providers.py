"""AI 제공자 선택(Claude / Gemini)을 한곳에서 나눈다. 화면은 이 함수들만 부른다."""
import streamlit as st

PROVIDERS = {"claude": "Claude API (유료)", "gemini": "Google Gemini API (무료 등급 가능)"}


def _ss():
    return st.session_state


def check_key(provider, key):
    if provider == "gemini":
        from core import gemini
        return gemini.check_key(key)
    from core.llm import check_key as claude_check
    ok, msg = claude_check(key)
    return ok, msg, []


def model_name() -> str:
    if _ss().get("provider") == "gemini":
        from core.gemini import DEFAULT_MODEL
        return _ss().get("gemini_model") or DEFAULT_MODEL
    from core.llm import MODEL_JUDGE
    return MODEL_JUDGE


def _gemini_with_fallback(call):
    """모델이 막혀 있으면(404) 키 확인 때 받은 다른 모델로 바꿔 다시 시도한다."""
    from core import gemini
    tried = []
    while True:
        model = model_name()
        try:
            return call(model)
        except Exception as e:
            tried.append(model)
            others = [m for m in _ss().get("gemini_models", []) if m not in tried]
            if not gemini.unavailable(e) or not others:
                raise
            _ss().gemini_model = others[0]
            _ss().model_notice = f"{model} 모델을 쓸 수 없어 {others[0]}(으)로 바꿨습니다."


def suggest_query(pico) -> str:
    if _ss().get("provider") == "gemini":
        from core import gemini
        return _gemini_with_fallback(lambda m: gemini.suggest_query(_ss().api_key, pico, m))
    from core.llm import suggest_query as claude_query
    return claude_query(_ss().api_key, pico)


def extract_one(main_pdf, pico, supp_pdfs=()):
    if _ss().get("provider") == "gemini":
        from core import gemini
        return _gemini_with_fallback(lambda m: gemini.extract_one(_ss().api_key, main_pdf, pico, supp_pdfs, m))
    from core.extract import extract_one as claude_extract
    return claude_extract(_ss().api_key, main_pdf, pico, supp_pdfs)


def error_text(e) -> str:
    if _ss().get("provider") == "gemini":
        from core.gemini import error_message
        return error_message(e, _ss().get("api_key"))
    return f"추출 실패 ({type(e).__name__})"


def screen(pico, items) -> dict:
    """items: [{id, title, abstract}] → {id: {decision, reason}} (15편씩 나눠 보냄)."""
    from core import screening
    out = {}
    for i in range(0, len(items), screening.BATCH):
        chunk = items[i:i + screening.BATCH]
        if _ss().get("provider") == "gemini":
            res = _gemini_with_fallback(lambda m: screening.gemini_batch(_ss().api_key, pico, chunk, m))
        else:
            res = screening.claude_batch(_ss().api_key, pico, chunk)
        out.update(res)
    return out
