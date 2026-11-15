"""3단계: 초록을 보고 AI가 포함 / 제외 / 보류를 추천한다. 최종 결정은 저자가 한다.

- 초록이 없는 논문은 AI에 보내지 않고 '보류(초록 없음)'으로 둔다.
- 15편씩 묶어 한 번에 보내 무료 한도를 아낀다.
"""
import json

DECISIONS = {"include": "포함", "exclude": "제외", "maybe": "보류"}
BADGE = {"포함": "🟢 포함", "제외": "🔴 제외", "보류": "🟡 보류"}
BATCH = 15

SYSTEM = (
    "You screen records for an umbrella review (a review of systematic reviews WITH meta-analysis). For each record, "
    "decide from its title and abstract whether it should be included, using the PICO. Include only systematic reviews "
    "with a quantitative meta-analysis whose population, intervention/exposure and outcome match the PICO. Exclude "
    "primary studies, narrative reviews, umbrella reviews/overviews, protocols, and reviews on a different population, "
    "exposure or outcome. Answer 'maybe' when the abstract is unclear (e.g. not sure a meta-analysis was done, or "
    "partly matching population). Give a short reason in Korean (one sentence, under 60 characters)."
)
SCHEMA_HINT = 'Return ONLY JSON: {"results": [{"id": "...", "decision": "include|exclude|maybe", "reason": "..."}]}'

TOOL = {"name": "record_screening", "description": "Screening decisions.",
        "input_schema": {"type": "object", "properties": {"results": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "string"},
                                             "decision": {"type": "string", "enum": list(DECISIONS)},
                                             "reason": {"type": "string"}},
            "required": ["id", "decision", "reason"]}}}, "required": ["results"]}}


def user_text(pico: dict, items: list[dict]) -> str:
    head = "\n".join(f"{k}: {pico.get(k, '')}" for k in ["question", "P", "I", "C", "O"])
    recs = [{"id": it["id"], "title": it["title"], "abstract": it["abstract"][:3000]} for it in items]
    return f"PICO\n{head}\n\nRecords\n{json.dumps(recs, ensure_ascii=False)}"


def parse_results(raw: dict, ids: list[str]) -> dict[str, dict]:
    out = {}
    for r in raw.get("results", []):
        rid, dec = str(r.get("id")), str(r.get("decision", "")).lower().strip()
        if rid in ids and dec in DECISIONS:
            out[rid] = {"decision": DECISIONS[dec], "reason": str(r.get("reason", "")).strip()}
    return out


def claude_batch(api_key, pico, items) -> dict:
    import anthropic
    from core.llm import MODEL_JUDGE
    msg = anthropic.Anthropic(api_key=api_key).messages.create(
        model=MODEL_JUDGE, max_tokens=4000, system=SYSTEM, tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": user_text(pico, items)}])
    raw = next(b.input for b in msg.content if b.type == "tool_use")
    return parse_results(raw, [it["id"] for it in items])


def gemini_batch(api_key, pico, items, model) -> dict:
    from core import gemini
    raw = gemini.parse_json(gemini._generate(api_key, model, [user_text(pico, items)], SYSTEM + "\n" + SCHEMA_HINT))
    return parse_results(raw, [it["id"] for it in items])


def demo_recommendation(p) -> dict:
    """데모 전용 예시 (실제 AI 판단 아님): 참고 논문의 포함 여부를 그대로 보여 준다."""
    if "demo_include" not in p:
        return {"decision": "보류", "reason": "데모 예시: 직접 추가한 논문은 예시 판단이 없습니다"}
    if p["demo_include"]:
        return {"decision": "포함", "reason": "데모 예시: 참고 논문이 포함한 리뷰"}
    return {"decision": "제외", "reason": "데모 예시: 우울 결과가 없는 리뷰"}
