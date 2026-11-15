import hashlib
import streamlit as st
from core.export import MIME, fulltext_zip
from core.state import label, unlock_and_go
from core.ui import header
from datetime import date


def _reset_extraction(p):
    """본문이 바뀌면 예전 추출값은 옛 파일 기준이므로 5단계에서 다시 추출하게 되돌린다."""
    had = st.session_state.ext.pop(p["uid"], None) is not None
    p["extraction"], p["reviewed"], p["extract_failed"] = None, False, False
    return had


def _save_main(p, f):
    data = f.getvalue()
    digest = hashlib.sha1(data).hexdigest()
    if p.get("main_hash") == digest:      # 같은 파일이 다시 들어온 것(화면 새로 그리기)이면 무시
        return
    replaced = p["fulltext"] == "saved"
    st.session_state.pdfs[p["uid"]] = data
    p["fulltext"], p["main_file"], p["main_hash"] = "saved", f.name, digest
    if replaced and _reset_extraction(p):
        st.session_state.step4_msg = f"{label(p)}: 본문을 바꿨습니다. 이 논문은 5단계에서 다시 추출해 주세요."
    elif replaced:
        st.session_state.step4_msg = f"{label(p)}: 본문을 {f.name}(으)로 바꿨습니다."
    st.rerun()


def _delete_main(uid):
    p = next(x for x in st.session_state.papers if x["uid"] == uid)
    st.session_state.pdfs.pop(uid, None)
    p["fulltext"], p["main_file"], p["main_hash"] = "missing", None, None
    p["main_ver"] = p.get("main_ver", 0) + 1
    st.session_state.pop(f"replace_{uid}", None)
    _reset_extraction(p)
    st.session_state.step4_msg = f"{label(p)}: 본문을 지웠습니다. 새 PDF를 올려 주세요."


def _delete_supp(uid):
    st.session_state.supp.pop(uid, None)
    st.session_state[f"supp_ver_{uid}"] = st.session_state.get(f"supp_ver_{uid}", 0) + 1


@st.cache_data(max_entries=64, show_spinner=False)
def _first_page(pdf: bytes, version: int = 2):
    from core.pdfview import render
    img, n = render(pdf, 1)
    return img, n


def _auto_fetch(todo):
    from core.oa import fetch_open_access
    bar, ok = st.progress(0.0), 0
    for i, p in enumerate(todo):
        bar.progress(i / len(todo), text=f"{label(p)} 공개 원문 찾는 중... ({i + 1}/{len(todo)})")
        try:
            pdf, note = fetch_open_access(p.get("pmid"), p.get("doi"))
        except Exception as e:
            pdf, note = None, f"찾지 못했습니다 ({type(e).__name__})"
        p["auto_tried"], p["auto_note"] = True, note
        if pdf:
            st.session_state.pdfs[p["uid"]] = pdf
            p["fulltext"], p["main_file"], p["main_hash"] = "saved", note, hashlib.sha1(pdf).hexdigest()
            ok += 1
    st.session_state.step4_msg = f"공개 원문 {ok}편을 자동으로 받았습니다. 나머지 {len(todo) - ok}편은 직접 올려 주세요."
    st.rerun()


def _demo_fill():
    for p in st.session_state.papers:
        if p["included"] and p.get("stored") and p["fulltext"] != "saved":
            p["fulltext"], p["main_file"] = "saved", "데모 예시 (실제 파일 없음)"


@st.dialog("전문 저장")
def zip_dialog():
    ts = [p for p in st.session_state.papers if p["included"] and p["fulltext"] == "saved"]
    data, n = fulltext_zip(ts, st.session_state.pdfs, st.session_state.supp)
    n_main = sum(p["uid"] in st.session_state.pdfs for p in ts)
    n_supp = sum(len(st.session_state.supp.get(p["uid"], [])) for p in ts)
    st.markdown(f"1. **논문 PDF를 zip 파일 하나로 내 컴퓨터에 저장**  \n본문 PDF {n_main}개는 `main` 폴더에, 보충자료 {n_supp}개는 "
                "`supplementary` 폴더에 ‘1저자_연도’ 이름으로 정리합니다.\n2. **LLM 추출로 이동**  \n저장이 끝나면 아래 버튼으로 넘어갑니다.")
    demo_only = len(ts) - n_main
    if demo_only:
        st.caption(f"데모 예시로 채운 {demo_only}편은 실제 PDF가 없어 zip에 들어가지 않습니다.")
    fn = f"fulltext_{date.today():%Y%m%d}.zip"
    if n:
        if st.download_button("zip 저장", data, fn, MIME["zip"], type="primary", width="stretch"):
            st.session_state.zip_saved = fn
    else:
        st.warning("zip에 넣을 파일이 없습니다. PDF를 하나 이상 올리면 저장할 수 있습니다.")
    if st.session_state.get("zip_saved"):
        st.success(f"✓ 저장했습니다: {st.session_state.zip_saved}")
    if st.button("다음: LLM 추출" if st.session_state.get("zip_saved") else "저장하지 않고 넘어가기", width="stretch"):
        unlock_and_go(5)
        st.rerun()


def render():
    header("4단계", "전문 확보",
           "LLM이 숫자와 근거를 찾으려면 논문 본문이 필요합니다. 먼저 DOI · PMID로 PubMed Central의 공개 원문을 자동으로 받고, "
           "받지 못한 논문만 직접 올려 주세요. 보충자료(supplementary)는 선택 사항으로, PDF로 올리면 AMSTAR 2 판단에 함께 쓰입니다.")
    ps = [p for p in st.session_state.papers if p["included"]]
    st.caption("출판사 이용 조건을 확인한 논문만 올려 주세요. 올린 파일은 이 탭(세션)의 메모리에만 있어서, "
               "새로 고치거나 탭을 닫으면 사라집니다. 잘못 올린 PDF는 ‘PDF 바꾸기’에서 바꾸거나 지울 수 있습니다.")
    if st.session_state.mode == "demo":
        left = [p for p in ps if p.get("stored") and p["fulltext"] != "saved"]
        with st.container(border=True):
            st.markdown("데모: 미리 분석해 둔 예시 논문 7편은 아래 버튼으로 한 번에 올린 상태로 채울 수 있습니다. "
                        "이렇게 채운 논문에는 실제 PDF 파일이 없습니다.")
            if left:
                st.button(f"데모: 예시 논문 {len(left)}편 채우기", on_click=_demo_fill)
    todo = [p for p in ps if p["fulltext"] != "saved" and not p.get("auto_tried")]
    if todo:
        if st.button(f"공개 원문 자동 받기 ({len(todo)}편)", type="primary"):
            _auto_fetch(todo)
        st.caption("PubMed Central에 공개된 논문만 받을 수 있습니다. 한 편씩 차례로 받습니다.")
    msg = st.session_state.pop("step4_msg", None)
    if msg:
        st.info(msg)
    saved = sum(p["fulltext"] == "saved" for p in ps)
    st.markdown(f":green-background[✓ 본문 저장됨 {saved}]  :red-background[✗ 본문 업로드 필요 {len(ps) - saved}]")
    h = st.columns([4, 3, 3])
    h[0].markdown("**논문**"); h[1].markdown("**본문 (필수)**"); h[2].markdown("**보충자료 (선택)**")
    for p in ps:
        uid = p["uid"]
        c = st.columns([4, 3, 3])
        c[0].markdown(f"{p['title']}  \n<span style='color:#5B6475;font-size:13px'>{label(p)} · {p['journal']}</span>",
                      unsafe_allow_html=True)
        with c[1]:
            if p["fulltext"] == "saved":
                st.markdown(":green-background[✓ 저장됨]")
                if p.get("main_file"):
                    st.caption(p["main_file"])
                if uid in st.session_state.pdfs:
                    with st.expander("1쪽 미리보기"):
                        try:
                            img, n = _first_page(st.session_state.pdfs[uid])
                            st.image(img, caption=f"1 / {n}쪽 — 올바른 논문인지 확인하세요", width="stretch")
                        except Exception:
                            st.error("PDF를 열 수 없습니다. 다른 파일로 바꿔 주세요.")
                with st.expander("PDF 바꾸기"):
                    f = st.file_uploader("다른 PDF로 바꾸기", type="pdf", key=f"replace_{uid}", label_visibility="collapsed")
                    if f is not None:
                        _save_main(p, f)
                    st.button("본문 지우기", key=f"del_{uid}", on_click=_delete_main, args=(uid,))
            else:
                st.markdown(":red-background[✗ 본문 업로드 필요]")
                if p.get("auto_tried"):
                    st.caption(f"자동 받기: {p.get('auto_note')}")
                if p.get("doi"):
                    st.link_button("DOI 열기 ↗", f"https://doi.org/{p['doi']}")
                f = st.file_uploader("본문 PDF 올리기", type="pdf", key=f"main_{uid}_{p.get('main_ver', 0)}",
                                     label_visibility="collapsed")
                if f is not None:
                    _save_main(p, f)
        with c[2]:
            files = st.file_uploader("보충자료 올리기", accept_multiple_files=True,
                                     key=f"supp_{uid}_{st.session_state.get(f'supp_ver_{uid}', 0)}", label_visibility="collapsed")
            if files:
                st.session_state.supp[uid] = [(x.name, x.getvalue()) for x in files]
            if st.session_state.supp.get(uid):
                st.caption(" · ".join(n for n, _ in st.session_state.supp[uid]))
                st.button("보충자료 지우기", key=f"delsupp_{uid}", on_click=_delete_supp, args=(uid,))
        st.divider()
    if st.button("전문 저장", type="primary", disabled=not saved):
        zip_dialog()
    st.caption("올린 논문 PDF들을 zip 파일 하나로 내 컴퓨터에 저장한 뒤 LLM 추출로 넘어갑니다. "
               "본문이 없는 논문은 추출에서 빠지고 PRISMA에 ‘확보 못 함’으로 집계됩니다.")
