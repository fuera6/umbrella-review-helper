"""앱 전체를 클릭해 보는 테스트. 외부 서비스(PubMed · Claude)는 가짜로 바꾼다."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.test_logic import mock_output

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PDF = (Path(__file__).resolve().parent / "fixtures" / "sample.pdf").read_bytes()


def ok(at):
    assert not at.exception, at.exception[0].message if at.exception else ""


def btn(at, text):
    return next(b for b in at.button if b.label.startswith(text))


def test_demo_full_flow():
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); ok(at)
    assert btn(at, "다음: PubMed").disabled                     # 검색식이 비어 있으면 못 넘어감
    at.text_area(key="q_input").set_value("(exercise AND depress*").run()
    assert any("괄호" in e.value for e in at.error)
    btn(at, "AI 추천").click().run(); ok(at)
    assert at.success and not btn(at, "다음: PubMed").disabled
    btn(at, "다음: PubMed").click().run(); ok(at)
    assert at.session_state.page == "step2" and at.button(key="nav_4").disabled
    btn(at, "다음: 스크리닝").click().run(); ok(at)
    # 3단계: 직접 추가 · 제거
    at.text_input(key="m_title").set_value("Hand-searched thesis"); at.text_input(key="m_author").set_value("Kim")
    at.number_input(key="m_year").set_value(2021); btn(at, "행 추가").click().run(); ok(at)
    assert len(at.session_state.papers) == 22 and at.session_state.search["other_sources"] == 1
    btn(at, "제거").click().run(); ok(at)                      # 첫 논문(Andermo) 완전 제거
    assert len(at.session_state.papers) == 21 and at.session_state.search["records_identified"] == 20
    at.session_state.reach = 4; at.session_state.page = "step4"; at.run(); ok(at)   # (대화창 확인은 화면에서)
    btn(at, "데모: 예시 논문").click().run(); ok(at)
    saved = [p for p in at.session_state.papers if p["fulltext"] == "saved"]
    assert len(saved) == 6
    at.session_state.reach = 5; at.session_state.page = "step5"; at.run(); ok(at)
    btn(at, "추출 시작").click().run(); ok(at)
    ext = at.session_state.ext
    assert sum(v["status"] == "fail" for v in ext.values()) == 1 and at.session_state.ask_retry   # Zang 모의 실패
    btn(at, "다시 추출").click().run(); ok(at)
    assert all(v["status"] == "ok" for v in at.session_state.ext.values())
    btn(at, "다음: 저자").click().run(); ok(at)
    assert btn(at, "다음: 표").disabled
    keys = lambda: [b.key for b in at.button if b.key and b.key.startswith("rvnav_")]
    assert keys()[0].startswith("rvnav_cur_") and all(k.startswith(("rvnav_todo_", "rvnav_cur_")) for k in keys())
    btn(at, "이 논문 검토 완료").click().run(); ok(at)
    assert keys()[0].startswith("rvnav_done_") and keys()[1].startswith("rvnav_cur_")     # 1편 완료 → 초록, 다음 논문으로
    at.button(key=keys()[0]).click().run(); ok(at)
    assert keys()[0].startswith("rvnav_donecur_") and at.button(key="rv_main_done").label == "✓ 검토 완료됨"
    at.button(key=next(k for k in keys() if "_cur_" in k or "todo" in k)).click().run()
    for _ in range(5):
        btn(at, "이 논문 검토 완료").click().run(); ok(at)
    assert not btn(at, "다음: 표").disabled
    btn(at, "다음: 표").click().run(); ok(at)
    assert len(at.get("image")) >= 2
    btn(at, "다음: 내보내기").click().run(); ok(at)
    assert len(at.get("download_button")) == 9                # PRISMA 4 + Forest 4 + 표 1
    assert not any(b.label == "검증 결과" for b in at.button)


def test_api_full_flow(monkeypatch):
    import core.extract, core.pubmed
    import views.step1 as s1, views.step5 as s5
    monkeypatch.setattr(s1, "suggest_query", lambda pico: '("exercise"[mh]) AND depress*[tiab] AND meta-analysis[pt]')
    monkeypatch.setattr(core.pubmed, "search", lambda q, retmax=500: (3, ["1", "2", "3"]))
    monkeypatch.setattr(core.pubmed, "fetch_summaries", lambda ids: {i: {"title": f"Title {i}", "first_author": f"A{i}",
                        "year": 2020, "journal": "J", "doi": f"10.1/{i}"} for i in ids})
    calls = []
    def fake_extract(pdf, pico, supp=()):
        calls.append(len(supp))
        if pdf == b"bad":
            raise TimeoutError()
        return core.extract.to_app_format(mock_output())
    monkeypatch.setattr(s5, "extract_one", fake_extract)

    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["mode"] = "api"; at.session_state["api_key"] = "sk-ant-FAKE"; at.session_state["provider"] = "claude"
    at.run(); ok(at)
    for k, v in {"in_P": "adolescents", "in_I": "exercise", "in_O": "depression"}.items():
        at.text_input(key=k).set_value(v)
    at.run()
    btn(at, "AI 추천").click().run(); ok(at)
    assert at.success
    btn(at, "다음: PubMed").click().run()
    btn(at, "검색 실행").click().run(); ok(at)
    assert len(at.session_state.papers) == 3
    btn(at, "다음: 스크리닝").click().run(); ok(at)
    # 4단계: 파일 올리기 대신 세션에 PDF를 넣어 둔다
    for p, data in zip(at.session_state.papers, [PDF, b"bad", None]):
        if data:
            at.session_state.pdfs[p["uid"]] = data; p["fulltext"] = "saved"
    at.session_state.supp[at.session_state.papers[0]["uid"]] = [("s.pdf", PDF), ("t.docx", b"x")]
    at.session_state.reach = 5; at.session_state.page = "step5"; at.run(); ok(at)
    btn(at, "추출 시작").click().run(); ok(at)
    assert calls == [1, 0]                                     # 보충자료는 PDF만 전달
    assert at.session_state.ask_retry
    btn(at, "그냥 넘어가기").click().run(); ok(at)
    btn(at, "다음: 저자").click().run(); ok(at)
    assert len(at.get("image")) == 1                           # 본문 PDF 쪽 그림
    btn(at, "원문 p. 3").click().run(); ok(at)
    assert at.session_state["pg_1"] == 3


def test_start_screen_gemini_key_flow(monkeypatch):
    import core.gemini
    monkeypatch.setattr(core.gemini, "list_models", lambda key: ["gemini-2.5-flash", "gemini-3-flash"])
    def probe(key, m):      # 2.5-flash는 새 사용자에게 막힌 상황을 흉내
        if m == "gemini-2.5-flash":
            e = Exception("404 no longer available to new users"); e.code = 404; raise e
    monkeypatch.setattr(core.gemini, "probe", probe)
    at = AppTest.from_file(APP, default_timeout=60).run(); ok(at)
    at.radio(key="provider_choice").set_value("gemini").run()
    at.text_input(key="key_gemini").set_value("A" * 39).run()
    btn(at, "키 확인").click().run(); ok(at)
    assert at.selectbox(key="gemini_model_choice").value == "gemini-2.5-flash"
    btn(at, "이 키로 시작").click().run(); ok(at)
    assert at.session_state.provider == "gemini" and at.session_state.mode == "api"
    assert at.session_state.gemini_model == "gemini-3-flash"            # 막힌 모델 대신 자동으로 바뀜
    assert any("Gemini 연결됨" in m.value for m in at.sidebar.markdown)


def test_switching_demo_to_api_clears_demo_list(monkeypatch):
    """데모를 하다가 API 모드로 바꾸면 데모 목록이 남지 않고, 내 검색 결과만 보여야 한다."""
    import core.gemini, core.pubmed
    monkeypatch.setattr(core.gemini, "list_models", lambda key: ["gemini-3-flash"])
    monkeypatch.setattr(core.gemini, "probe", lambda key, m: None)
    monkeypatch.setattr(core.pubmed, "search", lambda q, retmax=500: (2, ["111", "222"]))
    monkeypatch.setattr(core.pubmed, "fetch_summaries", lambda ids: {i: {"title": f"MY PAPER {i}", "first_author": "Me",
                        "year": 2024, "journal": "J", "doi": f"10.9/{i}"} for i in ids})
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); btn(at, "AI 추천").click().run()
    btn(at, "다음: PubMed").click().run(); btn(at, "다음: 스크리닝").click().run()
    assert len(at.session_state.papers) == 21
    at.session_state.mode = None; at.run()            # '처음부터 다시'를 누르지 않고 시작 화면으로 돌아간 경우
    at.radio(key="provider_choice").set_value("gemini").run()
    at.text_input(key="key_gemini").set_value("A" * 39).run()
    btn(at, "키 확인").click().run(); btn(at, "이 키로 시작").click().run(); ok(at)
    assert at.session_state.papers == [] and at.session_state.reach == 1      # 데모 흔적이 지워짐
    for k, v in {"in_P": "a", "in_I": "b", "in_O": "c"}.items():
        at.text_input(key=k).set_value(v)
    at.text_area(key="q_input").set_value("exercise[tiab] AND depress*[tiab]").run()
    btn(at, "다음: PubMed").click().run(); btn(at, "검색 실행").click().run(); ok(at)
    btn(at, "다음: 스크리닝").click().run(); ok(at)
    assert [p["title"] for p in at.session_state.papers] == ["MY PAPER 111", "MY PAPER 222"]
    assert any("내 목록" in c.value for c in at.caption)


def test_select_all_and_deselect_all():
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); btn(at, "AI 추천").click().run()
    btn(at, "다음: PubMed").click().run(); btn(at, "다음: 스크리닝").click().run()
    btn(at, "모두 해제").click().run(); ok(at)
    assert not any(p["included"] for p in at.session_state.papers)
    btn(at, "모두 선택").click().run(); ok(at)
    assert all(p["included"] and p["exclude_reason"] is None for p in at.session_state.papers)
    at.session_state.reach = 4; at.session_state.page = "step4"; at.run(); ok(at)
    assert any("본문 업로드 필요" in m.value for m in at.markdown)


class FakeUpload:
    def __init__(self, name, data):
        self.name, self._d = name, data
    def getvalue(self):
        return self._d


def test_replace_and_delete_main_pdf(monkeypatch):
    """잘못 올린 본문을 바꾸면 PDF가 교체되고 그 논문의 추출은 다시 해야 하는 상태가 된다."""
    import streamlit as st
    import views.step4 as s4
    st.session_state.clear()
    p = {"uid": "u1", "first_author": "Kim", "year": 2021, "fulltext": "saved", "main_file": "wrong.pdf",
         "main_hash": "old", "extraction": {"x": 1}, "reviewed": True}
    st.session_state.update(papers=[p], pdfs={"u1": b"wrong"}, ext={"u1": {"status": "ok"}}, supp={})
    monkeypatch.setattr(st, "rerun", lambda: None)
    s4._save_main(p, FakeUpload("right.pdf", PDF))
    assert st.session_state.pdfs["u1"] == PDF and p["main_file"] == "right.pdf"
    assert p["extraction"] is None and not p["reviewed"] and "u1" not in st.session_state.ext
    assert "다시 추출" in st.session_state.step4_msg
    s4._save_main(p, FakeUpload("right.pdf", PDF))          # 같은 파일이 다시 들어와도 아무 일 없음
    s4._delete_main("u1")
    assert p["fulltext"] == "missing" and "u1" not in st.session_state.pdfs and p["main_ver"] == 1


def test_leave_warning_visible():
    at = AppTest.from_file(APP, default_timeout=60).run()
    btn(at, "키 없이 데모로 시작").click().run(); ok(at)
    assert any("새로 고치거나 탭을 닫으면" in m.value for m in at.sidebar.markdown)
