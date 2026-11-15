"""표·그림이 함께 쓰는 정리 함수 (Streamlit에 의존하지 않음)."""
from core.amstar import grade

RATIO = {"RR", "OR", "HR"}
MEASURES = ["RR", "OR", "HR", "SMD", "MD"]
DESIGNS = ["RCT", "Observational", "Mixed (RCT + observational)"]
MODELS = ["Random effects", "Fixed effect"]
FIELDS = ["outcome", "k", "n", "population", "design", "characteristics", "effect_measure",
          "estimate", "ci_low", "ci_high", "i2", "p_het", "model", "egger_p"]
CHAR_COLS = ["First author, year", "No. of studies", "Total sample", "Population or condition",
             "Primary study design", "Characteristics", "Outcome", "Effect measure", "AMSTAR 2 confidence"]


def is_num(v) -> bool:
    try:
        return v is not None and v != "" and float(v) == float(v)
    except (TypeError, ValueError):
        return False


def amstar_of(ex):
    return grade({i: v["answer"] for i, v in ex["amstar"].items()})


def blank_extraction() -> dict:
    ex = {k: {"value": None, "evidence": None, "page": None} for k in FIELDS}
    ex["lower_favours_intervention"] = True
    ex["amstar"] = {str(i): {"answer": None, "evidence": None, "page": None} for i in range(1, 17)}
    ex["_warnings"] = []
    return ex


def targets(papers):
    """추출 대상: 포함 + 본문 확보."""
    return [p for p in papers if p["included"] and p["fulltext"] == "saved"]


def reviewed(papers):
    return [p for p in targets(papers) if p.get("extraction") and p.get("reviewed")]


def characteristics_rows(papers):
    rows = []
    for p in reviewed(papers):
        ex, g = p["extraction"], amstar_of(p["extraction"])
        rows.append({
            "First author, year": f"{p['first_author']} {p['year']}",
            "No. of studies": ex["k"]["value"], "Total sample": ex["n"]["value"],
            "Population or condition": ex["population"]["value"] or "",
            "Primary study design": ex["design"]["value"] or "",
            "Characteristics": ex["characteristics"]["value"] or "",
            "Outcome": ex["outcome"]["value"] or "",
            "Effect measure": ex["effect_measure"]["value"] or "",
            "AMSTAR 2 confidence": g["rating"] + (" (provisional)" if g["provisional"] else ""),
        })
    return rows


CODE = {"Yes": "Y", "Partial Yes": "PY", "No": "N"}


def amstar_columns():
    from core.amstar import CRITICAL_ITEMS
    return ["First author, year"] + [f"{i}*" if i in CRITICAL_ITEMS else str(i) for i in range(1, 17)] + ["Overall confidence"]


def amstar_rows(papers):
    """보충 Table S3 형식: 논문마다 16문항(Y/PY/N, 답 없으면 빈칸)과 종합 등급."""
    cols = amstar_columns()
    rows = []
    for p in reviewed(papers):
        ex, g = p["extraction"], amstar_of(p["extraction"])
        row = {cols[0]: f"{p['first_author']} {p['year']}"}
        for i, c in enumerate(cols[1:17], 1):
            row[c] = CODE.get(ex["amstar"][str(i)]["answer"], "")
        row[cols[-1]] = g["rating"] + (" (provisional)" if g["provisional"] else "")
        rows.append(row)
    return rows


def forest_rows(papers):
    """검토 완료된 논문의 그림용 행. 효과 방향을 맞춰(기준선 아래 = 중재 유리) 표시값을 만든다."""
    rows = []
    for p in reviewed(papers):
        ex = p["extraction"]
        m = ex["effect_measure"]["value"]
        vals = [ex[k]["value"] for k in ("estimate", "ci_low", "ci_high")]
        if m not in MEASURES or not all(is_num(v) for v in vals):
            continue
        est, lo, hi = map(float, vals)
        if m in RATIO and min(est, lo, hi) <= 0:
            continue
        flipped = ex.get("lower_favours_intervention") is False
        if flipped:
            est, lo, hi = (1 / est, 1 / hi, 1 / lo) if m in RATIO else (-est, -hi, -lo)
        rows.append({"uid": p["uid"], "label": f"{p['first_author']} {p['year']}",
                     "author": p["first_author"] or "", "year": p["year"] or 0,
                     "outcome": ex["outcome"]["value"] or "", "measure": m,
                     "est": est, "lo": lo, "hi": hi, "flipped": flipped,
                     "k": ex["k"]["value"], "i2": ex["i2"]["value"]})
    return rows


SORTS = ["효과 크기순 (중재 유리한 것부터)", "효과 크기순 (반대)", "출판 연도순", "1저자 이름순", "입력 순서"]


def sort_rows(rows, how: str):
    """forest plot 행 정렬. 효과 크기는 방향을 맞춘 값(기준선 아래 = 중재 유리) 기준."""
    rows = list(rows)
    if how == SORTS[0]:
        return sorted(rows, key=lambda r: r["est"])
    if how == SORTS[1]:
        return sorted(rows, key=lambda r: -r["est"])
    if how == SORTS[2]:
        return sorted(rows, key=lambda r: (int(r.get("year") or 0), r.get("author", "").lower()))
    if how == SORTS[3]:
        return sorted(rows, key=lambda r: (r.get("author", "").lower(), int(r.get("year") or 0)))
    return rows


def measures_present(rows):
    return [m for m in MEASURES if any(r["measure"] == m for r in rows)]
