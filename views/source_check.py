"""7단계 '원문 대조': 표·그림의 숫자를 누르면 원문 PDF의 해당 쪽을 근거 문장 위치에 노란색 강조로 보여 준다."""
import html
import streamlit as st
from core.results import is_num
from core.state import label

FIELDS_TABLE = [("k", "No. of studies"), ("n", "Total sample"), ("population", "Population"),
                ("design", "Study design"), ("characteristics", "Characteristics"), ("outcome", "Outcome")]


def _fmt(v):
    if is_num(v):
        f = float(v)
        return f"{int(f):,}" if f == int(f) else f"{f:.2f}".replace("-", "−")
    return str(v) if v not in (None, "") else "–"


@st.dialog("원문 대조", width="large")
def source_dialog(uid, field_label, value, f):
    p = next(x for x in st.session_state.papers if x["uid"] == uid)
    st.markdown(f"**{label(p)}** · {field_label}: **{value}**")
    ev = f.get("evidence")
    if ev:
        st.markdown(f"근거 문장{' (p. ' + str(f['page']) + ')' if f.get('page') else ''}: “{html.escape(ev)}”")
    else:
        st.warning("이 값에는 근거 문장이 없습니다. 저자가 직접 입력했거나 원문에서 찾지 못한 값입니다.")
    pdf = st.session_state.pdfs.get(uid)
    if not pdf:
        st.info("이 논문의 원문 PDF가 이 세션에 없습니다. (데모 예시 논문에는 PDF가 없습니다.)")
        return
    from views.step6 import _page_img, locate
    page, rects = (f.get("page") or 1), []
    if ev:
        found, rects = locate(pdf, ev, f.get("page"))
        page = found or page
    img, n = _page_img(pdf, page, tuple(tuple(r) for r in rects))
    st.image(img, caption=f"p. {page} / {n} — " + ("노란색이 근거 문장 위치입니다" if rects
                                                   else "근거 문장의 정확한 위치를 찾지 못해 적힌 쪽을 보여 줍니다"), width="stretch")


def table_panel(papers):
    with st.expander("숫자를 눌러 원문과 대조하기 (Characteristics table)"):
        for p in papers:
            ex = p["extraction"]
            st.markdown(f"**{label(p)}**")
            cols = st.columns(len(FIELDS_TABLE))
            for col, (k, lab) in zip(cols, FIELDS_TABLE):
                v = _fmt(ex[k]["value"])
                short = v if len(v) <= 18 else v[:17] + "…"
                if col.button(f"{lab}: {short}", key=f"src_t_{p['uid']}_{k}", width="stretch",
                              help=ex[k].get("evidence") or "근거 문장 없음"):
                    source_dialog(p["uid"], lab, v, ex[k])


def forest_panel(rows, papers):
    by_uid = {p["uid"]: p for p in papers}
    with st.expander("숫자를 눌러 원문과 대조하기 (Forest plot)"):
        for r in rows:
            ex = by_uid[r["uid"]]["extraction"]
            raw = f"{_fmt(ex['estimate']['value'])} [{_fmt(ex['ci_low']['value'])}, {_fmt(ex['ci_high']['value'])}]"
            c1, c2, c3 = st.columns([2, 3, 2])
            c1.markdown(f"**{r['label']}**" + (" †" if r["flipped"] else ""))
            if c2.button(f"{r['measure']} {raw}", key=f"src_f_{r['uid']}", width="stretch", help=ex["estimate"].get("evidence")):
                source_dialog(r["uid"], f"{r['measure']} (95% CI)", raw, ex["estimate"])
            if c3.button(f"I² {_fmt(ex['i2']['value'])}%", key=f"src_i_{r['uid']}", width="stretch", help=ex["i2"].get("evidence")):
                source_dialog(r["uid"], "I²", _fmt(ex["i2"]["value"]), ex["i2"])
        st.caption("† 그림에서는 효과 방향을 맞추려고 부호를 바꿔 표시했습니다. 버튼의 숫자는 원문에 적힌 그대로입니다.")
