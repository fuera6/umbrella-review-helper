"""5단계: 논문마다 차례로 LLM 추출. 진행 막대·예상 시간·성공(✓)/실패(✗), 실패한 논문만 다시 추출."""
import copy
import time
import streamlit as st
from core.demo import load_raw
from core.extract import PROMPT_VERSION
from core.providers import error_text, extract_one, model_name
from core.results import blank_extraction, targets
from core.state import label, unlock_and_go
from core.ui import header

SEC_PER_PAPER = {"demo": 0.8, "api": 45.0}   # 실제 걸린 시간이 쌓이면 그 평균으로 바뀐다


def _status(uid):
    return st.session_state.ext.get(uid, {}).get("status", "pending")


def _line(p):
    s = st.session_state.ext.get(p["uid"], {})
    badge = {"ok": ":green-background[✓ 성공]", "fail": ":red-background[✗ 실패]", "running": ":blue-background[추출 중…]"}.get(
        s.get("status"), ":gray-background[대기]")
    reason = f"  \n:red[{s['reason']}]" if s.get("status") == "fail" else ""
    return f"{badge} &nbsp; {label(p)} — {p['title']}{reason}"


def _extract(p):
    if st.session_state.mode == "demo":
        time.sleep(0.6)
        stored = p.get("stored")
        if not stored:
            raise RuntimeError("데모: 미리 분석해 둔 결과가 없는 논문입니다")
        if stored.get("_mock_fail_once") and not st.session_state.mock_failed.get(p["uid"]):
            st.session_state.mock_failed[p["uid"]] = True
            raise RuntimeError("응답 시간 초과 (데모용 모의 실패)")
        ex = copy.deepcopy(stored)
        ex.pop("_mock_fail_once", None)
        return ex
    supp = [b for name, b in st.session_state.supp.get(p["uid"], []) if name.lower().endswith(".pdf")]
    return extract_one(st.session_state.pdfs[p["uid"]], st.session_state.pico, supp)


def _run(todo):
    ts = targets(st.session_state.papers)
    bar, eta, box = st.progress(0.0), st.empty(), st.empty()
    for p in todo:
        st.session_state.ext[p["uid"]] = {"status": "pending"}
    for i, p in enumerate(todo):
        st.session_state.ext[p["uid"]] = {"status": "running"}
        durs = st.session_state.durations
        avg = sum(durs) / len(durs) if durs else SEC_PER_PAPER[st.session_state.mode]
        eta.markdown(f"**{i + 1} / {len(todo)}** 추출 중 · 남은 예상 시간 약 {round(avg * (len(todo) - i))}초")
        box.markdown("  \n".join(_line(x) for x in ts))
        t0 = time.time()
        try:
            p["extraction"], p["extract_failed"] = _extract(p), False
            st.session_state.ext[p["uid"]] = {"status": "ok"}
        except Exception as e:
            reason = str(e) if st.session_state.mode == "demo" else error_text(e)
            p["extraction"], p["extract_failed"] = blank_extraction(), True
            p["extraction"]["_warnings"] = ["LLM 추출에 실패해 빈 칸으로 시작합니다. 원문을 보고 직접 입력해 주세요."]
            st.session_state.ext[p["uid"]] = {"status": "fail", "reason": reason}
        p["reviewed"] = False
        durs.append(time.time() - t0)
        bar.progress((i + 1) / len(todo))
    st.session_state.ask_retry = any(_status(x["uid"]) == "fail" for x in ts)
    st.rerun()


def render():
    header("5단계", "LLM 추출",
           "논문 한 편당 한 번 호출해서 Characteristics table 항목, 요약값(효과 · CI · I²), AMSTAR 2 16문항을 근거 문장 · 쪽수와 함께 받습니다. "
           "실패한 논문도 6단계에서 저자가 직접 입력할 수 있습니다.")
    ts = targets(st.session_state.papers)
    if st.session_state.mode == "demo":
        st.info("데모: 결과는 참고 umbrella review(Singh 2026)에서 옮긴 기준값이고, 진행 속도는 줄여서 보여 줍니다. "
                "실제 버전은 논문당 30초~1분 정도 걸립니다. Zang 2023은 재시도 흐름을 보여 주려고 첫 시도에서 일부러 실패하게 했습니다.")
    else:
        free = st.session_state.provider == "gemini"
        st.caption(f"모델: {model_name()} · 프롬프트: {PROMPT_VERSION} · "
                   + ("무료 한도를 넘으면 잠시 기다렸다 자동으로 다시 시도합니다." if free else "요금은 입력한 키의 계정에 청구됩니다."))
    done = [p for p in ts if _status(p["uid"]) in ("ok", "fail")]
    pending = [p for p in ts if _status(p["uid"]) == "pending"]
    fails = [p for p in ts if _status(p["uid"]) == "fail"]
    with st.container(border=True):
        st.markdown(f"**진행 상황 {len(done)} / {len(ts)}**")
        if pending and st.button(f"추출 시작 ({len(pending)}편)", type="primary"):
            _run(pending)
        st.progress(len(done) / len(ts) if ts else 0.0)
        st.markdown("  \n".join(_line(p) for p in ts))
        if st.session_state.ask_retry and fails:
            st.error(f"**추출에 실패한 논문이 {len(fails)}편 있습니다. 실패한 논문만 다시 추출할까요?**")
            a, b = st.columns(2)
            if a.button("다시 추출", type="primary", width="stretch"):
                _run(fails)
            if b.button("그냥 넘어가기 (6단계에서 직접 입력)", width="stretch"):
                st.session_state.ask_retry = False
                st.rerun()
    st.button("다음: 저자 검토", type="primary", disabled=bool(pending) or st.session_state.ask_retry or not ts,
              on_click=unlock_and_go, args=(6,))
