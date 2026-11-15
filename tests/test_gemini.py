"""Gemini 연결: 실제 Google 서버 대신 가짜 응답으로 형식 처리와 재시도를 확인한다."""
import json
import types as pytypes

import pytest

import core.gemini as gm
from tests.test_logic import mock_output


class FakeModels:
    def __init__(self, texts):
        self.texts, self.calls = list(texts), []

    def generate_content(self, model, contents, config):
        if self.closed:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        self.calls.append({"model": model, "contents": contents, "config": config})
        t = self.texts.pop(0)
        if isinstance(t, Exception):
            raise t
        return pytypes.SimpleNamespace(text=t)

    def list(self):
        """여러 쪽으로 나눠 오는 목록: 다음 쪽을 받을 때 연결이 닫혀 있으면 실패한다."""
        mk = lambda n, a: pytypes.SimpleNamespace(name=f"models/{n}", supported_actions=a)
        pages = [[mk("gemini-2.5-pro", ["generateContent"]), mk("gemini-2.5-flash", ["generateContent"])],
                 [mk("gemini-embedding-001", ["embedContent"]), mk("gemini-2.5-flash-lite", ["generateContent"])]]
        def gen():
            for i, page in enumerate(pages):
                if i and self.closed:
                    raise RuntimeError("Cannot send a request, as the client has been closed.")
                yield from page
        return gen()


class FakeClient:
    """진짜 Gemini 클라이언트처럼 with를 지원하고, 지워지거나 닫히면 연결을 닫는다."""
    def __init__(self, models):
        self.models = models
        models.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *a):
        self.models.closed = True
    def __del__(self):
        self.models.closed = True


def fake_client(monkeypatch, texts):
    models = FakeModels(texts)
    monkeypatch.setattr(gm, "_client", lambda key: FakeClient(models))
    return models


def test_list_models_flash_first(monkeypatch):
    fake_client(monkeypatch, [])
    assert gm.list_models("k") == ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]


def test_rank_prefers_newest_flash():
    names = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash", "gemini-3-pro-preview", "gemini-3-flash-lite", "gemini-2.0-flash"]
    assert sorted(names, key=gm._rank)[:3] == ["gemini-3-flash", "gemini-3-flash-lite", "gemini-3-pro-preview"]


class Err404(Exception):
    code = 404
    message = "This model models/gemini-2.5-flash is no longer available to new users."


def test_pick_working_model_skips_unavailable(monkeypatch):
    seen = []
    def probe(key, m):
        seen.append(m)
        if m == "gemini-2.5-flash":
            raise Err404()
    monkeypatch.setattr(gm, "probe", probe)
    assert gm.pick_working_model("k", ["gemini-3-flash", "gemini-2.5-flash"], "gemini-2.5-flash") == "gemini-3-flash"
    assert seen == ["gemini-2.5-flash", "gemini-3-flash"]


def test_pick_working_model_treats_quota_as_available(monkeypatch):
    class Err429(Exception):
        code = 429
    monkeypatch.setattr(gm, "probe", lambda k, m: (_ for _ in ()).throw(Err429()))
    assert gm.pick_working_model("k", ["gemini-3-flash"]) == "gemini-3-flash"


def test_provider_falls_back_during_work(monkeypatch):
    import streamlit as st
    import core.providers as pv
    st.session_state.clear()
    st.session_state.update(provider="gemini", api_key="k", gemini_model="gemini-2.5-flash",
                            gemini_models=["gemini-2.5-flash", "gemini-3-flash"])
    def fake_query(key, pico, model):
        if model == "gemini-2.5-flash":
            raise Err404()
        return f"ok via {model}"
    monkeypatch.setattr(gm, "suggest_query", fake_query)
    assert pv.suggest_query({}) == "ok via gemini-3-flash"
    assert st.session_state.gemini_model == "gemini-3-flash" and "바꿨습니다" in st.session_state.model_notice


def test_error_message_not_truncated():
    msg = gm.error_message(Err404())
    assert "no longer available to new users" in msg and "쓸 수 없습니다" in msg


def test_extract_one_parses_and_sends_pdfs(monkeypatch):
    raw = mock_output()
    models = fake_client(monkeypatch, ["```json\n" + json.dumps(raw) + "\n```"])
    ex = gm.extract_one("k", b"%PDF main", {"O": "depression"}, [b"%PDF supp"], "gemini-2.5-flash")
    assert ex["estimate"]["value"] == -0.5 and ex["amstar"]["1"]["answer"] == "Yes"
    call = models.calls[0]
    assert call["model"] == "gemini-2.5-flash" and len(call["contents"]) == 3   # 본문 + 보충 + 지시문
    assert call["config"].response_mime_type == "application/json"
    assert "record_extraction" not in call["config"].system_instruction


def test_normalize_messy_output():
    raw = mock_output()
    raw["estimate"] = {"value": "−0.47", "evidence": "SMD −0.47", "page": "6"}
    raw["effect_measure"] = {"value": "smd", "evidence": "x", "page": 5}
    raw["k"] = {"value": "10", "evidence": "x", "page": None}
    raw["amstar"]["2"] = {"answer": "partial yes", "evidence": "PROSPERO", "page": 2}
    raw["amstar"]["7"] = {"answer": "null", "evidence": "null", "page": None}
    del raw["egger_p"]
    raw["lower_favours_intervention"] = "yes"
    n = gm.normalize(raw)
    assert n["estimate"]["value"] == -0.47 and n["estimate"]["page"] == 6
    assert n["effect_measure"]["value"] == "SMD" and n["k"]["value"] == 10
    assert n["amstar"]["2"]["answer"] == "Partial Yes" and n["amstar"]["7"]["answer"] is None
    assert n["egger_p"] == {"value": None, "evidence": None, "page": None}
    assert n["lower_favours_intervention"] is None          # 애매하면 비워 두고 앱이 경고


def test_retry_on_rate_limit(monkeypatch):
    monkeypatch.setattr(gm.time, "sleep", lambda s: None)
    err = Exception("429 RESOURCE_EXHAUSTED")
    models = fake_client(monkeypatch, [err, json.dumps({"query": "exercise[tiab]"})])
    assert gm.suggest_query("k", {"P": "a"}) == "exercise[tiab]" and len(models.calls) == 2


def test_error_messages():
    assert "한도" in gm.error_message(Exception("429 quota"))
    assert "모델" in gm.error_message(Exception("404 not found"))


def test_bad_json_raises():
    with pytest.raises(ValueError):
        gm.parse_json("죄송합니다")


def test_old_pattern_reproduces_runtime_error(monkeypatch):
    """예전 코드처럼 클라이언트를 변수에 담지 않으면 두 번째 쪽에서 RuntimeError가 난다 (버그 재현)."""
    models = fake_client(monkeypatch, [])
    with pytest.raises(RuntimeError):
        list(gm._client("k").models.list())


def test_error_message_shows_detail_but_hides_key():
    key = "AIza" + "x" * 35
    msg = gm.error_message(RuntimeError(f"Cannot send a request with {key}"), key)
    assert "Cannot send a request" in msg and key not in msg
