"""6단계: LLM이 뽑은 값을 원문(본문 PDF)·근거와 함께 보고 저자가 확인·수정한다."""
import streamlit as st
from core.amstar import CRITICAL_ITEMS, ITEMS, answers_for
from core.results import DESIGNS, MEASURES, MODELS, amstar_of, targets
from core.state import label, unlock_and_go
from core.ui import evidence, header, warn


def _list():
    return [p for p in targets(st.session_state.papers) if st.session_state.ext.get(p["uid"], {}).get("status") in ("ok", "fail")]


def _set_cur(i):
    st.session_state.current_paper = i


@st.cache_data(max_entries=256, show_spinner=False)
def locate(pdf: bytes, evidence: str, page: int | None):
    from core.pdfview import find_evidence
    return find_evidence(pdf, evidence, page)


def _goto_page(uid, page, evidence=None):
    """근거 문장을 원문에서 찾아 그 쪽으로 이동하고, 위치를 노란색으로 강조한다."""
    pdf = st.session_state.pdfs.get(uid)
    rects = []
    if pdf and evidence:
        found, rects = locate(pdf, evidence, page)
        page = found or page
    st.session_state[f"pg_{uid}"] = page
    st.session_state[f"hl_{uid}"] = (page, rects)


def _done(n):
    ps = _list()
    ps[st.session_state.current_paper]["reviewed"] = True
    nxt = next((i for i, p in enumerate(ps) if not p["reviewed"]), st.session_state.current_paper)
    _set_cur(nxt)


@st.cache_data(max_entries=64)
def _cached_page(pdf: bytes, page: int, rects: tuple, version: int):
    from core.pdfview import render
    return render(pdf, page, rects)


def _page_img(pdf: bytes, page: int, rects: tuple = ()):
    """캐시 열쇠에 그리기 방식 번호를 넣어, 코드가 바뀌면 예전 그림(불투명 형광펜)이 다시 나오지 않게 한다."""
    from core.pdfview import RENDER_VERSION
    return _cached_page(pdf, page, rects, RENDER_VERSION)


def _ev(f, key, has_pdf, uid=None):
    evidence(f)
    if has_pdf and f.get("page"):   # 누르면 왼쪽 원문이 그 쪽으로 이동
        st.button(f"원문 p. {f['page']} 보기", key=f"go_{key}", on_click=_goto_page,
                  args=(uid or st.session_state.get("_cur_uid"), f["page"], f.get("evidence")))


def _num(lab, f, key, fmt="%.2f", integer=False, **kw):
    v = f["value"]
    if integer:
        f["value"] = st.number_input(lab, value=None if v is None else int(v), step=1, key=key)
    else:
        f["value"] = st.number_input(lab, value=None if v is None else float(v), format=fmt, key=key, **kw)


def _select(lab, f, options, key, **kw):
    v = f["value"]
    f["value"] = st.selectbox(lab, options, index=options.index(v) if v in options else None,
                              placeholder="선택하세요", key=key, **kw)


def render():
    ps = _list()
    if not ps:
        header("6단계", "저자 검토")
        st.info("5단계에서 추출을 먼저 실행해 주세요.")
        return
    cur = min(st.session_state.current_paper, len(ps) - 1)
    p, ex, k = ps[cur], ps[cur]["extraction"], ps[cur]["uid"]
    has_pdf = k in st.session_state.pdfs
    st.session_state["_cur_uid"] = k
    header(f"6단계 · 논문 {cur + 1} / {len(ps)}", "추출 결과 검토")
    # 논문 고르기: 검토 완료 = 연한 초록, 지금 보는 논문 = 파란 테두리(완료면 진한 초록). 색은 core/ui.py의 CSS
    per_row = 6
    for start in range(0, len(ps), per_row):
        cols = st.columns(per_row)
        for i, col in zip(range(start, min(start + per_row, len(ps))), cols):
            state = ("donecur" if i == cur else "done") if ps[i]["reviewed"] else ("cur" if i == cur else "todo")
            col.button(("✓ " if ps[i]["reviewed"] else "") + label(ps[i]), key=f"rvnav_{state}_{i}", width="stretch",
                       on_click=_set_cur, args=(i,))
    a, b, c = st.columns([1, 1, 2])
    a.button("← 이전", width="stretch", on_click=_set_cur, args=((cur - 1) % len(ps),))
    b.button("다음 →", width="stretch", on_click=_set_cur, args=((cur + 1) % len(ps),))
    if p["reviewed"]:
        c.button("✓ 검토 완료됨", key="rv_main_done", width="stretch", on_click=_done, args=(len(ps),))
    else:
        c.button("이 논문 검토 완료", key="rv_main_todo", type="primary", width="stretch", on_click=_done, args=(len(ps),))
    st.caption(f"{p['title']} · {p['journal']}")
    if p.get("extract_failed"):
        warn("LLM 추출에 실패한 논문입니다. 원문을 보고 직접 입력해 주세요.")
    for w in ex.get("_warnings", []):
        if not w.startswith("LLM 추출에 실패"):
            warn(f"⚠ {w}")

    left, right = st.columns([1, 1.2])
    with left, st.container(border=True):
        st.markdown("**원문 PDF (본문)**")
        if has_pdf:
            st.session_state.setdefault(f"pg_{k}", 1)
            _, n = _page_img(st.session_state.pdfs[k], 1)
            st.session_state[f"pg_{k}"] = max(1, min(st.session_state[f"pg_{k}"], n))
            pg = st.number_input("쪽", min_value=1, max_value=n, step=1, key=f"pg_{k}")
            hl_page, rects = st.session_state.get(f"hl_{k}", (None, []))
            rects = tuple(tuple(r) for r in rects) if hl_page == pg else ()
            img, _ = _page_img(st.session_state.pdfs[k], pg, rects)
            st.image(img, caption=f"p. {pg} / {n} — " + ("노란색이 근거 문장 위치입니다" if rects else "오른쪽 근거 문장과 대조하세요"))
        else:
            st.caption("이 논문의 본문 PDF가 이 세션에 없습니다. (데모 예시 논문에는 PDF가 없습니다.) 보충자료는 여기에 표시하지 않습니다.")

    with right:
        t1, t2, t3 = st.tabs(["Characteristics table", "요약값", "AMSTAR 2"])
        with t1:
            ex["outcome"]["value"] = st.text_input("Outcome", ex["outcome"]["value"] or "", key=f"{k}_out") or None
            _ev(ex["outcome"], f"{k}_out", has_pdf)
            x, y = st.columns(2)
            with x:
                _num("Number of studies", ex["k"], f"{k}_k", integer=True); _ev(ex["k"], f"{k}_k", has_pdf)
            with y:
                _num("Total sample", ex["n"], f"{k}_n", integer=True); _ev(ex["n"], f"{k}_n", has_pdf)
            ex["population"]["value"] = st.text_input("Population or condition", ex["population"]["value"] or "", key=f"{k}_pop") or None
            _ev(ex["population"], f"{k}_pop", has_pdf)
            _select("Primary study design", ex["design"], DESIGNS, f"{k}_des"); _ev(ex["design"], f"{k}_des", has_pdf)
            ex["characteristics"]["value"] = st.text_area("Characteristics", ex["characteristics"]["value"] or "", key=f"{k}_ch",
                                                          placeholder="연령, 국가, 중재 형태·기간 등 저자가 자유롭게 서술") or None
            _ev(ex["characteristics"], f"{k}_ch", has_pdf)
            st.caption("노출(exposure)은 모든 리뷰에서 같다고 가정해 따로 받지 않습니다.")
        with t2:
            if ex["effect_measure"]["value"] not in MEASURES or any(ex[f]["value"] is None for f in ("estimate", "ci_low", "ci_high")):
                warn("효과 지표와 추정치 · 신뢰구간이 모두 있어야 forest plot에 들어갑니다.")
            _select("효과 지표", ex["effect_measure"], MEASURES, f"{k}_m"); _ev(ex["effect_measure"], f"{k}_m", has_pdf)
            x, y, z = st.columns(3)
            with x: _num("요약 추정치", ex["estimate"], f"{k}_est")
            with y: _num("95% CI 하한", ex["ci_low"], f"{k}_lo")
            with z: _num("95% CI 상한", ex["ci_high"], f"{k}_hi")
            _ev(ex["estimate"], f"{k}_est", has_pdf)
            opts = {True: "기준선 아래(SMD · MD < 0, 비율 < 1)가 중재 유리", False: "기준선 위가 중재 유리 (그림에서는 방향을 맞춰 뒤집어 표시)"}
            ex["lower_favours_intervention"] = st.radio("효과 방향", list(opts), format_func=opts.get, key=f"{k}_dir",
                                                        index=0 if ex.get("lower_favours_intervention", True) else 1)
            x, y = st.columns(2)
            with x:
                _num("I² (%)", ex["i2"], f"{k}_i2", fmt="%.1f", min_value=0.0, max_value=100.0); _ev(ex["i2"], f"{k}_i2", has_pdf)
            with y:
                _num("이질성 p", ex["p_het"], f"{k}_p", fmt="%.3f"); _ev(ex["p_het"], f"{k}_p", has_pdf)
            x, y = st.columns(2)
            with x:
                _select("합성 모형", ex["model"], MODELS, f"{k}_mod"); _ev(ex["model"], f"{k}_mod", has_pdf)
            with y:
                _num("Egger 검정 p (작은 연구 효과)", ex["egger_p"], f"{k}_eg", fmt="%.3f"); _ev(ex["egger_p"], f"{k}_eg", has_pdf)
        with t3:
            for i in range(1, 17):
                item = ex["amstar"][str(i)]
                opts = answers_for(i)
                item["answer"] = st.selectbox(f"{i}. {ITEMS[i][0]}" + (" · 핵심" if i in CRITICAL_ITEMS else ""), opts,
                                              index=opts.index(item["answer"]) if item["answer"] in opts else None,
                                              placeholder="선택하세요", help=ITEMS[i][1], key=f"{k}_am{i}")
                _ev(item, f"{k}_am{i}", has_pdf)
            g = amstar_of(ex)
            with st.container(border=True):
                st.markdown(f"**AMSTAR 2 종합 등급: {g['rating']}**" + (" (잠정)" if g["provisional"] else ""))
                st.caption(f"핵심 결함 문항: {g['critical_flaws'] or '없음'} · 비핵심 약점 문항: {g['weaknesses'] or '없음'}")
                if g["missing"]:
                    warn(f"아직 답하지 않은 문항: {g['missing']}")

    done = sum(x["reviewed"] for x in ps)
    all_done = done == len(ps) and not any(st.session_state.ext.get(x["uid"], {}).get("status") is None
                                           for x in targets(st.session_state.papers))
    st.button("다음: 표 · 그림", type="primary", disabled=not all_done, on_click=unlock_and_go, args=(7,))
    st.caption(f"검토 완료 {done} / {len(ps)}" + ("" if all_done else " — 모든 논문을 검토하면 넘어갈 수 있습니다."))
