"""5단계: 논문 본문 PDF(+보충자료 PDF) → Claude 한 번 호출 → 앱 형식의 추출 결과.

같은 build_params()를 실시간 호출(extract_one)과 Batch API(tools/batch_extract.py)가 함께 쓴다.
출력 형식은 도구(tool) 정의로 강제한다(tool_choice).
"""
import base64
from pathlib import Path

from core.amstar import PARTIAL_ITEMS
from core.llm import MODEL_JUDGE

PROMPT_VERSION = "extract-v3"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_v3.txt"
MAX_TOKENS = 8000
MEASURES = ["RR", "OR", "HR", "SMD", "MD"]


def _field(value_schema, desc):
    return {"type": "object", "description": desc,
            "properties": {"value": value_schema, "evidence": {"type": ["string", "null"]},
                           "page": {"type": ["integer", "null"]}},
            "required": ["value", "evidence", "page"]}


NUM, INT, STR = {"type": ["number", "null"]}, {"type": ["integer", "null"]}, {"type": ["string", "null"]}
_item = {"type": "object",
         "properties": {"answer": {"type": ["string", "null"], "enum": ["Yes", "Partial Yes", "No", None]},
                        "evidence": {"type": ["string", "null"]}, "page": {"type": ["integer", "null"]}},
         "required": ["answer", "evidence", "page"]}
_FIELDS = {
    "outcome": _field(STR, "outcome name"), "k": _field(INT, "studies pooled"), "n": _field(INT, "participants pooled"),
    "population": _field(STR, "population or condition"),
    "design": _field({"type": ["string", "null"], "enum": ["RCT", "Observational", "Mixed (RCT + observational)", None]}, "primary study design"),
    "characteristics": _field(STR, "short description of included studies"),
    "effect_measure": _field({"type": ["string", "null"], "enum": MEASURES + [None]}, "pooled effect measure"),
    "estimate": _field(NUM, "pooled estimate"), "ci_low": _field(NUM, "95% CI lower"), "ci_high": _field(NUM, "95% CI upper"),
    "i2": _field(NUM, "I squared, percent"), "p_het": _field(NUM, "heterogeneity p"),
    "model": _field({"type": ["string", "null"], "enum": ["Random effects", "Fixed effect", None]}, "synthesis model"),
    "egger_p": _field(NUM, "Egger test p"),
}
TOOL = {
    "name": "record_extraction",
    "description": "Record the extracted main result and AMSTAR 2 appraisal for one meta-analysis.",
    "input_schema": {
        "type": "object",
        "properties": {**_FIELDS,
                       "n_is_review_total": {"type": "boolean"},
                       "lower_favours_intervention": {"type": ["boolean", "null"]},
                       "amstar": {"type": "object", "properties": {str(i): _item for i in range(1, 17)},
                                  "required": [str(i) for i in range(1, 17)]}},
        "required": list(_FIELDS) + ["n_is_review_total", "lower_favours_intervention", "amstar"],
    },
}


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _doc(pdf: bytes, title: str) -> dict:
    return {"type": "document", "title": title,
            "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(pdf).decode()}}


def build_params(main_pdf: bytes, pico: dict, supp_pdfs: list[bytes] = (), model: str = MODEL_JUDGE) -> dict:
    content = [_doc(main_pdf, "Main text")] + [_doc(b, f"Supplementary {i}") for i, b in enumerate(supp_pdfs, 1)]
    content.append({"type": "text", "text": (
        f"Umbrella review PICO\n- Question: {pico.get('question', '')}\n- P: {pico.get('P', '')}\n"
        f"- I/E: {pico.get('I', '')}\n- C: {pico.get('C', '')}\n- O: {pico.get('O', '')}\n\n"
        f"The first document is the main text{'; the others are supplementary material' if supp_pdfs else ''}. "
        "Extract from this meta-analysis.")})
    return {"model": model, "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": TOOL["name"]},
            "messages": [{"role": "user", "content": content}]}


def tool_input_from_message(content_blocks) -> dict:
    for b in content_blocks:
        btype = b.get("type") if isinstance(b, dict) else b.type
        if btype == "tool_use":
            return b["input"] if isinstance(b, dict) else b.input
    raise ValueError("응답에 record_extraction 도구 호출이 없습니다.")


def to_app_format(t: dict) -> dict:
    """LLM 출력 → 앱 형식. 값은 그대로 두고, 형식이 맞지 않는 답만 빈칸으로 돌리고 경고를 남긴다."""
    warnings = []
    ex = {k: dict(t[k]) for k in _FIELDS}
    lf = t.get("lower_favours_intervention")
    if lf is None:
        lf = True
        warnings.append("효과 방향이 논문에서 분명하지 않아 ‘기준선 아래가 중재 유리’로 두었습니다. 확인해 주세요.")
    ex["lower_favours_intervention"] = lf
    ex["amstar"] = {}
    for i in range(1, 17):
        item = dict(t["amstar"][str(i)])
        if item["answer"] == "Partial Yes" and i not in PARTIAL_ITEMS:
            warnings.append(f"AMSTAR {i}번은 Yes/No만 가능한데 Partial Yes가 나와 빈칸으로 두었습니다.")
            item["answer"] = None
        ex["amstar"][str(i)] = item
    if t.get("n_is_review_total"):
        warnings.append("Total sample이 이 분석이 아니라 리뷰 전체 인원일 수 있습니다.")
    ex["_warnings"] = warnings
    return ex


def extract_one(api_key: str, main_pdf: bytes, pico: dict, supp_pdfs: list[bytes] = (), model: str = MODEL_JUDGE) -> dict:
    import anthropic
    msg = anthropic.Anthropic(api_key=api_key).messages.create(**build_params(main_pdf, pico, supp_pdfs, model))
    return to_app_format(tool_input_from_message(msg.content))
