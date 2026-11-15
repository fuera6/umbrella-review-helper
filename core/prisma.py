"""PRISMA 숫자를 2~4단계 기록에서 자동으로 센다 (umbrella review → 단위는 reviews).

목록에서 '완전히 제거'한 논문은 검색 건수(또는 기타 출처 건수)에서도 빠지므로 집계에 남지 않는다.
"""


def counts(search: dict, papers: list) -> dict:
    identified = search.get("records_identified", 0)
    other = search.get("other_sources", 0)
    dup = search.get("duplicates_removed", 0)
    screened = identified + other - dup
    excluded = [p for p in papers if not p["included"]]
    included = [p for p in papers if p["included"]]
    not_retrieved = [p for p in included if p["fulltext"] != "saved"]
    c = {"identified": identified, "other": other, "dup": dup, "screened": screened,
         "excluded": len(excluded), "sought": len(included), "not_retrieved": len(not_retrieved),
         "assessed": len(included) - len(not_retrieved), "final": len(included) - len(not_retrieved),
         "mismatch": []}
    if screened != len(papers):
        c["mismatch"].append(f"선별 대상 {screened}건과 목록의 논문 {len(papers)}건이 다릅니다.")
    no_reason = [p for p in excluded if not p.get("exclude_reason")]
    if no_reason:
        c["mismatch"].append(f"제외 사유가 없는 논문이 {len(no_reason)}편 있습니다.")
    return c
