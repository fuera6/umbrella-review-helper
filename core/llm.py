"""Claude API 연결. 키는 인자로만 받고 저장·출력하지 않는다."""
MODEL_JUDGE = "claude-sonnet-5-5"   # AMSTAR 2처럼 판단이 필요한 작업, 검색식 작성
MODEL_FAST = "claude-haiku-5-5"     # 키 확인


def check_key(api_key: str) -> tuple[bool, str]:
    if not api_key or not api_key.startswith("sk-ant-"):
        return False, "키 형식이 맞지 않습니다. sk-ant-로 시작하는 키를 넣어 주세요."
    try:
        import anthropic
        anthropic.Anthropic(api_key=api_key).messages.create(
            model=MODEL_FAST, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
        return True, "키가 확인되었습니다."
    except Exception as e:   # 오류 메시지에 키가 섞이지 않도록 종류만 보여 준다
        name = type(e).__name__
        return False, {"AuthenticationError": "키가 올바르지 않습니다. 다시 확인해 주세요.",
                       "PermissionDeniedError": "이 키로는 모델을 쓸 권한이 없습니다.",
                       "APIConnectionError": "Anthropic 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                       "APITimeoutError": "Anthropic 서버 응답이 늦습니다. 잠시 후 다시 시도해 주세요."
                       }.get(name, f"키 확인 중 오류가 났습니다 ({name}).")


QUERY_TOOL = {
    "name": "suggest_query",
    "description": "Write a PubMed query for an umbrella review.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}
QUERY_SYSTEM = (
    "You write PubMed search queries for medical students planning an umbrella review (a review of systematic "
    "reviews with meta-analysis). From the PICO, write ONE PubMed query in English using MeSH terms ([mh]) and "
    "title/abstract keywords ([tiab]) combined with uppercase AND/OR, and finish with this filter: "
    '(meta-analysis[pt] OR "systematic review"[pt] OR meta-analy*[tiab]). Keep it broad enough not to miss '
    "relevant reviews. Do not add date or language limits unless the PICO asks for them. Return only the query."
)


def suggest_query(api_key: str, pico: dict) -> str:
    import anthropic
    text = "\n".join(f"{k}: {pico.get(k, '')}" for k in ["question", "P", "I", "C", "O"])
    msg = anthropic.Anthropic(api_key=api_key).messages.create(
        model=MODEL_JUDGE, max_tokens=800, system=QUERY_SYSTEM, tools=[QUERY_TOOL],
        tool_choice={"type": "tool", "name": "suggest_query"}, messages=[{"role": "user", "content": text}])
    return next(b.input for b in msg.content if b.type == "tool_use")["query"].strip()
