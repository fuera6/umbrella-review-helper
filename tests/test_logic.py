import json
from pathlib import Path

import jsonschema
import pytest

from core.amstar import answers_for, grade
from core.extract import TOOL, build_params, to_app_format, tool_input_from_message
from core.prisma import counts
from core.query_check import check_query
from core.results import blank_extraction, forest_rows
from core.stats import Z, pooled, reml

ROOT = Path(__file__).resolve().parent.parent
REF = json.loads((ROOT / "data/validation/singh2026_reference.json").read_text())["reviews"]
DEMO = json.loads((ROOT / "data/demo/demo_results.json").read_text())


# ---------------- AMSTAR 2
def ans(**over):
    a = {i: "Yes" for i in range(1, 17)}
    a.update({int(k[1:]): v for k, v in over.items()})
    return a

@pytest.mark.parametrize("over,rating", [({}, "High"), ({"q10": "No"}, "High"), ({"q10": "No", "q12": "No"}, "Moderate"),
                                         ({"q13": "No"}, "Low"), ({"q2": "No", "q13": "No"}, "Critically low"),
                                         ({"q4": "Partial Yes"}, "High")])
def test_grade(over, rating):
    assert grade(ans(**over))["rating"] == rating

def test_missing_is_provisional_not_flaw():
    g = grade(ans(q7=None))
    assert g["rating"] == "High" and g["provisional"] and g["missing"] == [7]

def test_partial_yes_only_for_allowed_items():
    assert "Partial Yes" in answers_for(2) and "Partial Yes" not in answers_for(3)


# ---------------- 검색식 검사
def test_demo_query_is_valid():
    assert check_query(DEMO["demo_query"]) == []

@pytest.mark.parametrize("q,needle", [("", "비어"), ('"exercise AND depress*', "따옴표"), ("(exercise AND depress*", "여는 괄호"),
                                      ("exercise) AND (x", "먼저"), ("exercise[tiabx]", "필드 태그"), ("exercise and depression", "대문자"),
                                      ("exercise AND", "뒤에"), ("AND exercise", "앞에"), ("ex* AND y", "4자 미만")])
def test_query_errors(q, needle):
    assert any(needle in e for e in check_query(q))


# ---------------- REML: 참고 논문 Figure 2 · 3 재현
def _rm(rows):
    return reml([x["smd"] for x in rows], [((x["ci_high"] - x["ci_low"]) / (2 * Z)) ** 2 for x in rows])

def test_reml_reproduces_singh_figure2():
    r = _rm([x for rv in REF for x in rv["fig2_depression_smd"]])
    assert round(r["mu"], 2) == -0.45 and round(r["lo"], 2) == -0.59 and round(r["hi"], 2) == -0.31
    assert abs(r["I2"] - 71.37) < 0.5 and abs(r["H2"] - 3.49) < 0.05 and r["df"] == 19 and abs(r["Q"] - 57.89) < 0.5

def test_reml_reproduces_singh_figure3():
    r = _rm([rv["fig3_anxiety_smd"] for rv in REF if rv["fig3_anxiety_smd"]])
    assert round(r["mu"], 2) == -0.39 and abs(r["I2"] - 68.08) < 0.5 and r["df"] == 7


# ---------------- 추출 형식
def mock_output(**over):
    f = lambda v, e="quote", pg=3: {"value": v, "evidence": e, "page": pg}
    out = {"outcome": f("Depressive symptoms"), "k": f(12), "n": f(1500), "population": f("Adolescents"), "design": f("RCT"),
           "characteristics": f("Age 12-18"), "effect_measure": f("SMD"), "estimate": f(-0.5), "ci_low": f(-0.8),
           "ci_high": f(-0.2), "i2": f(40), "p_het": f(0.01), "model": f("Random effects"), "egger_p": f(None, None, None),
           "n_is_review_total": False, "lower_favours_intervention": True,
           "amstar": {str(i): {"answer": "Yes", "evidence": "q", "page": 2} for i in range(1, 17)}}
    out.update(over)
    return out

def test_schema_valid_and_mock_matches():
    jsonschema.Draft202012Validator.check_schema(TOOL["input_schema"])
    jsonschema.validate(mock_output(), TOOL["input_schema"])

def test_schema_rejects_other_measure():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(mock_output(effect_measure={"value": "IRR", "evidence": "", "page": 1}), TOOL["input_schema"])

def test_build_params_with_supplement():
    p = build_params(b"%PDF main", {"O": "depression"}, [b"%PDF supp"])
    json.dumps(p)
    docs = [c for c in p["messages"][0]["content"] if c["type"] == "document"]
    assert [d["title"] for d in docs] == ["Main text", "Supplementary 1"]
    assert p["tool_choice"]["name"] == "record_extraction"

def test_to_app_format_flags():
    t = mock_output(lower_favours_intervention=None, n_is_review_total=True)
    t["amstar"]["13"]["answer"] = "Partial Yes"
    t["amstar"]["7"]["answer"] = None
    ex = to_app_format(t)
    assert ex["lower_favours_intervention"] is True and ex["amstar"]["13"]["answer"] is None
    assert ex["amstar"]["7"]["answer"] is None and len(ex["_warnings"]) == 3

def test_tool_input_from_dict():
    assert tool_input_from_message([{"type": "text"}, {"type": "tool_use", "input": {"a": 1}}]) == {"a": 1}


# ---------------- 결과 정리 · PRISMA
def paper(measure, est, lo, hi, lower=True):
    ex = blank_extraction()
    for k, v in {"outcome": "dep", "k": 5, "effect_measure": measure, "estimate": est, "ci_low": lo, "ci_high": hi}.items():
        ex[k]["value"] = v
    ex["lower_favours_intervention"] = lower
    return {"uid": "u", "first_author": "A", "year": 2020, "included": True, "fulltext": "saved", "extraction": ex, "reviewed": True}

def test_flip_directions():
    r = forest_rows([paper("SMD", 0.5, 0.2, 0.8, lower=False)])[0]
    assert (r["est"], r["lo"], r["hi"], r["flipped"]) == (-0.5, -0.8, -0.2, True)
    r = forest_rows([paper("RR", 2.0, 1.25, 4.0, lower=False)])[0]
    assert (r["est"], r["lo"], r["hi"]) == (0.5, 0.25, 0.8)

def test_sort_rows():
    from core.results import SORTS, sort_rows
    def pp(author, year, est):
        p = paper("SMD", est, est - 0.2, est + 0.2); p["first_author"], p["year"], p["uid"] = author, year, author
        return p
    rows = forest_rows([pp("Kim", 2021, -0.2), pp("Lee", 2019, -0.9), pp("Ahn", 2023, 0.1)])
    order = lambda how: [r["author"] for r in sort_rows(rows, how)]
    assert order(SORTS[0]) == ["Lee", "Kim", "Ahn"] and order(SORTS[1]) == ["Ahn", "Kim", "Lee"]
    assert order(SORTS[2]) == ["Lee", "Kim", "Ahn"] and order(SORTS[3]) == ["Ahn", "Kim", "Lee"]
    assert order(SORTS[4]) == ["Kim", "Lee", "Ahn"]


def test_forest_has_no_outcome_text():
    import matplotlib.pyplot as plt
    from core.figures import forest_plot
    rows = forest_rows([paper("SMD", -0.5, -0.8, -0.2)])
    rows[0]["outcome"] = "SPECIAL OUTCOME TEXT"
    fig = forest_plot(rows, "SMD")
    texts = [t.get_text() for t in fig.axes[0].texts]
    plt.close(fig)
    assert "A 2020" in texts and not any("SPECIAL OUTCOME" in t for t in texts)


def test_unreviewed_not_plotted():
    p = paper("SMD", -0.5, -0.8, -0.2); p["reviewed"] = False
    assert forest_rows([p]) == []

def test_pooled_ratio_back_transformed():
    rows = forest_rows([paper("RR", 0.8, 0.7, 0.9), paper("RR", 0.9, 0.8, 1.0)])
    assert 0.8 < pooled(rows)["est"] < 0.9

def test_demo_prisma_counts():
    c = counts(DEMO["search"], DEMO["papers"])
    assert (c["identified"], c["excluded"], c["sought"], c["not_retrieved"], c["final"], c["mismatch"]) == (21, 2, 19, 19, 0, [])

def test_prisma_mismatch_detected():
    assert counts(dict(DEMO["search"], records_identified=25), DEMO["papers"])["mismatch"]
