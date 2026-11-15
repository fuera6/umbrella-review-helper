"""Google Gemini API 연결 (무료 등급 사용 가능). Claude와 같은 프롬프트·같은 결과 형식을 쓴다.

- 키 확인: 모델 목록을 불러와 본다 (생성 요청이 아니라 무료 한도를 쓰지 않음).
- 출력: JSON 모드(response_mime_type="application/json") + 프롬프트의 JSON 견본.
  결과는 core.gemini.normalize()가 앱 형식에 맞게 정리한다.
- 무료 등급은 분당·일일 요청 수 제한이 있어 429(한도 초과)가 나면 잠시 기다렸다 다시 시도한다.
- ⚠ 개발 환경에서는 Google 서버에 접속할 수 없어 실제 호출은 시험하지 못했다.
"""
import json
import re
import time

from core.extract import MEASURES, system_prompt, to_app_format

DEFAULT_MODEL = "gemini-2.5-flash"   # 목록을 못 받았을 때만 쓰는 예비값 (새 사용자에게는 막혀 있을 수 있음)
FIELD_KEYS = ["outcome", "k", "n", "population", "design", "characteristics", "effect_measure", "estimate",
              "ci_low", "ci_high", "i2", "p_het", "model", "egger_p"]
NUMERIC = {"k": int, "n": int, "estimate": float, "ci_low": float, "ci_high": float, "i2": float, "p_het": float, "egger_p": float}
ENUMS = {"effect_measure": MEASURES, "design": ["RCT", "Observational", "Mixed (RCT + observational)"],
         "model": ["Random effects", "Fixed effect"]}

TEMPLATE = {**{k: {"value": None, "evidence": "verbatim quote or null", "page": 1} for k in FIELD_KEYS},
            "n_is_review_total": False, "lower_favours_intervention": True,
            "amstar": {str(i): {"answer": "Yes | Partial Yes | No | null", "evidence": "quote or null", "page": 1} for i in range(1, 17)}}
JSON_RULE = ("\n\n# Output format\nReturn ONLY one JSON object (no markdown, no comments) with exactly these keys:\n"
             + json.dumps(TEMPLATE, ensure_ascii=False)
             + "\nUse null (not the string \"null\") for missing values.")


def _client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def _code(e) -> int | None:
    c = getattr(e, "code", None)
    if isinstance(c, int):
        return c
    m = re.search(r"\b(4\d\d|5\d\d)\b", str(e))
    return int(m.group(1)) if m else None


def _call(fn, tries=3, wait=20):
    """무료 한도 초과(429)·서버 혼잡(500/503)이면 기다렸다가 다시 시도."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if _code(e) in (429, 500, 503) and i < tries - 1:
                time.sleep(wait * (i + 1))
                continue
            raise


def error_message(e, api_key: str | None = None) -> str:
    code = _code(e)
    known = {400: "요청 형식 또는 키 문제입니다 (400).", 401: "키가 올바르지 않습니다.", 403: "키가 올바르지 않거나 권한이 없습니다.",
             404: "이 모델은 지금 쓸 수 없습니다 (새 사용자에게 막혔거나 없어진 모델).",
             429: "Gemini 무료 사용 한도를 넘었습니다. 1~2분 뒤 다시 시도하거나 내일 다시 해 주세요."}.get(code)
    detail = (getattr(e, "message", None) or str(e)).replace("\n", " ").strip()
    if api_key:
        detail = detail.replace(api_key, "***")      # 키가 화면에 나오지 않게
    detail = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "***", detail)[:400]
    head = known or f"Gemini 호출 오류 ({type(e).__name__}{', ' + str(code) if code else ''})."
    return f"{head} 자세한 내용: {detail}" if detail else head


def list_models(api_key) -> list[str]:
    """문서를 만들 수 있는(generateContent) Gemini 모델 이름. flash를 앞에.

    클라이언트를 with로 열어 두고 목록의 모든 쪽을 다 받은 뒤에 닫는다.
    (변수에 담지 않으면 파이썬이 클라이언트를 바로 지우면서 연결이 닫혀, 다음 쪽을 받을 때 RuntimeError가 났다)
    """
    names = []
    with _client(api_key) as client:
        items = list(client.models.list())
    for m in items:
        acts = getattr(m, "supported_actions", None) or []
        name = (getattr(m, "name", "") or "").removeprefix("models/")
        if "gemini" in name and (not acts or "generateContent" in acts) and not any(x in name for x in ("embedding", "image", "tts", "live")):
            names.append(name)
    return sorted(set(names), key=_rank)


def _version(name: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def _rank(name: str):
    """최신 버전 → flash → lite 아님 → 정식(preview·exp 아님) 순서."""
    return (-_version(name), "flash" not in name, "lite" in name, any(x in name for x in ("preview", "exp")), name)


def check_key(api_key: str) -> tuple[bool, str, list[str]]:
    if not api_key or len(api_key) < 20:
        return False, "키 형식이 맞지 않습니다. Google AI Studio에서 받은 키를 넣어 주세요.", []
    try:
        models = list_models(api_key)
        if not models:
            return False, "이 키로 쓸 수 있는 Gemini 모델이 없습니다.", []
        return True, "키가 확인되었습니다.", models
    except Exception as e:
        return False, error_message(e, api_key), []


def _generate(api_key, model, contents, system):
    from google.genai import types
    cfg = types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", temperature=0)
    with _client(api_key) as client:      # 응답을 다 받을 때까지 연결을 열어 둔다
        resp = _call(lambda: client.models.generate_content(model=model, contents=contents, config=cfg))
        return resp.text


def parse_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise ValueError("Gemini 응답에서 JSON을 찾지 못했습니다.")
        return json.loads(m.group(0))


def _num(v, cast):
    if v is None or v == "":
        return None
    try:
        return cast(float(str(v).replace("−", "-").replace(",", "").replace("<", "").strip()))
    except (TypeError, ValueError):
        return None


def normalize(raw: dict) -> dict:
    """Gemini 출력의 작은 형식 차이(문자열 숫자, 대소문자, 빠진 키)를 앱 형식으로 맞춘다. 값의 의미는 바꾸지 않는다."""
    out = {}
    for k in FIELD_KEYS:
        f = raw.get(k) if isinstance(raw.get(k), dict) else {"value": raw.get(k)}
        v = f.get("value")
        if v in ("null", "None", ""):
            v = None
        if k in NUMERIC:
            v = _num(v, NUMERIC[k])
        if k in ENUMS and v is not None:
            v = next((e for e in ENUMS[k] if str(v).strip().lower() == e.lower()), None)
        ev = f.get("evidence")
        page = _num(f.get("page"), int)
        out[k] = {"value": v, "evidence": None if ev in (None, "null", "") else str(ev), "page": page}
    lf = raw.get("lower_favours_intervention")
    out["lower_favours_intervention"] = lf if isinstance(lf, bool) else None
    out["n_is_review_total"] = bool(raw.get("n_is_review_total"))
    am = raw.get("amstar") or {}
    out["amstar"] = {}
    for i in range(1, 17):
        it = am.get(str(i)) or am.get(i) or {}
        a = str(it.get("answer") or "").strip().lower()
        ans = {"yes": "Yes", "partial yes": "Partial Yes", "partial": "Partial Yes", "no": "No"}.get(a)
        ev = it.get("evidence")
        out["amstar"][str(i)] = {"answer": ans, "evidence": None if ev in (None, "null", "") else str(ev),
                                 "page": _num(it.get("page"), int)}
    return out


def _pdf_part(data):
    from google.genai import types
    return types.Part.from_bytes(data=data, mime_type="application/pdf")


def extract_one(api_key, main_pdf, pico, supp_pdfs=(), model=DEFAULT_MODEL) -> dict:
    system = system_prompt().replace("Return your answer ONLY by calling the `record_extraction` tool.", "") + JSON_RULE
    text = (f"Umbrella review PICO\n- Question: {pico.get('question', '')}\n- P: {pico.get('P', '')}\n- I/E: {pico.get('I', '')}\n"
            f"- C: {pico.get('C', '')}\n- O: {pico.get('O', '')}\n\nThe first document is the main text"
            f"{'; the others are supplementary material' if supp_pdfs else ''}. Extract from this meta-analysis.")
    contents = [_pdf_part(main_pdf)] + [_pdf_part(b) for b in supp_pdfs] + [text]
    return to_app_format(normalize(parse_json(_generate(api_key, model, contents, system))))


def suggest_query(api_key, pico, model=DEFAULT_MODEL) -> str:
    from core.llm import QUERY_SYSTEM
    text = "\n".join(f"{k}: {pico.get(k, '')}" for k in ["question", "P", "I", "C", "O"])
    raw = parse_json(_generate(api_key, model, [text], QUERY_SYSTEM + '\nReturn ONLY JSON: {"query": "..."}'))
    return str(raw["query"]).strip()


def unavailable(e) -> bool:
    """모델 자체를 못 쓰는 오류인가 (404, 또는 '더 이상 제공하지 않음')."""
    t = str(getattr(e, "message", None) or e).lower()
    return _code(e) == 404 or "no longer available" in t or "not found for api version" in t


def probe(api_key, model) -> None:
    """아주 짧은 요청으로 모델을 쓸 수 있는지 확인한다. 쓸 수 없으면 예외."""
    from google.genai import types
    with _client(api_key) as client:
        client.models.generate_content(model=model, contents="ping",
                                       config=types.GenerateContentConfig(max_output_tokens=5, temperature=0))


def pick_working_model(api_key, models: list[str], preferred: str | None = None, max_tries: int = 6) -> str:
    """선택한 모델부터 차례로 시험해 처음으로 되는 모델을 돌려준다.
    무료 한도 초과(429)는 모델이 있다는 뜻이므로 '쓸 수 있음'으로 본다."""
    order = ([preferred] if preferred else []) + [m for m in models if m != preferred]
    last = None
    for m in order[:max_tries]:
        try:
            probe(api_key, m)
            return m
        except Exception as e:
            if _code(e) == 429:
                return m
            if not unavailable(e):
                raise
            last = e
    raise last or RuntimeError("쓸 수 있는 Gemini 모델을 찾지 못했습니다.")
