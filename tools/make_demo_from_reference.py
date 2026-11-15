"""참고 umbrella review(Singh 2026, CC BY)의 값으로 데모 데이터를 만든다.

⚠ 데모 값은 LLM 추출 결과가 아니다. Singh 2026 Figure 2(SMD·95% CI), Table 1(연구 수·인원·대상·특성),
보충 Table S3(AMSTAR 2 문항)에서 옮긴 기준값이다. 'stored'에 들어 있고, 4단계에서 '데모: 예시 논문 채우기'를
누르면 그 논문이 본문을 올린 것으로 처리되어 5단계에서 이 값이 나온다.

실행: python tools/make_demo_from_reference.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.build_demo_config import QUERY  # noqa: E402

REF = ROOT / "data" / "validation" / "singh2026_reference.json"
OUT = ROOT / "data" / "demo" / "demo_results.json"
S3 = {"Y": "Yes", "PY": "Partial Yes", "N": "No", "NA": None}
MAIN_LABEL = {"Barahona-Fuentes 2021": "Resistance exercise", "Wang 2022": "Depressive symptoms"}
T1 = {  # Singh 2026 Table 1 (대상, 특성)
    "Andermo": ("School children", "Age 6–19 y; school-based mixed-mode physical activity (active breaks, policies, environment); low to vigorous; 4 wk–1 y; 15–45 min, 2–5×/wk"),
    "Barahona-Fuentes": ("Adolescents with psychosocial disorders", "Mean age 11.0–17.9 y; mixed-mode strength training (aerobic, HIIT, CrossFit, resistance, Pilates); low to high; 4–22 wk; 20–60 min, 1–5×/wk"),
    "Oberste": ("Adolescents with depression", "Age 12–18 y; mixed mode (aerobic, resistance, circuit, sports); low to vigorous; 6–12 wk; 20–90 min, 2–4×/wk"),
    "Peng": ("Children and adolescents with neurodevelopmental disorders, depression, or obesity", "Mean age 6.9–16.9 y; mixed mode (aerobic, team sports, pool, resistance, yoga); low to vigorous; 6–78 wk; 15–90 min, 1–5×/wk"),
    "Wang": ("Adolescents with depression", "Mean age 15.9 y; mixed mode (aerobic, resistance, yoga, dance, cycling); low to vigorous; 6–40 wk; 30–120 min, 2–4×/wk"),
    "Zang": ("Children with paediatric cancer", "Mean age 7.6–13.4 y; mixed mode (aerobic, resistance, sports); low to vigorous; 6–26 wk; 15–60 min, 2–5×/wk"),
    "Zhang": ("Adolescents with depression", "Mean age 10–18 y; mixed mode (aerobic, resistance, sports, yoga); low to vigorous; 6–18 wk; 20–60 min, 2–4×/wk"),
}
DOI_LOOKUP = {  # 데모의 'DOI로 추가'에서 조회되는 예시 (Singh 2026 참고문헌)
    "10.1016/j.jaac.2023.04.017": {"title": "Umbrella systematic review and meta-analysis: physical activity as an effective therapeutic strategy for improving psychosocial outcomes in children and adolescents", "first_author": "Purgato", "year": 2024, "journal": "J Am Acad Child Adolesc Psychiatry"},
    "10.1136/bjsports-2022-106195": {"title": "Effectiveness of physical activity interventions for improving depression, anxiety and distress: an overview of systematic reviews", "first_author": "Singh", "year": 2023, "journal": "Br J Sports Med"},
    "10.1016/j.pmedr.2021.101687": {"title": "Impact of organized activities on mental health in children and adolescents: an umbrella review", "first_author": "Boelens", "year": 2022, "journal": "Prev Med Rep"},
    "10.1001/jamapsychiatry.2020.0164": {"title": "Psychotherapy for depression across different age groups: a systematic review and meta-analysis", "first_author": "Cuijpers", "year": 2020, "journal": "JAMA Psychiatry"},
}


def f(v, e=None, p=None):
    return {"value": v, "evidence": e, "page": p}


def stored(r):
    rows = r["fig2_depression_smd"]
    main = next((x for x in rows if x["label"] == MAIN_LABEL.get(r["key"])), rows[0])
    fig = (f"[기준값] Singh 2026 Figure 2: {r['key']}" + (f" ({main['label']})" if main["label"] else "")
           + f" {main['smd']:.2f} [{main['ci_low']:.2f}, {main['ci_high']:.2f}]")
    t1 = f"[기준값] Singh 2026 Table 1: 연구 {r['table1_review_total']['k']}편, 총 {r['table1_review_total']['n']:,}명"
    pop, ch = T1[r["first_author"]]
    am = {}
    for i, a in r["amstar2_items_tableS3"].items():
        ev = f"[기준값] Singh 2026 보충 Table S3 문항 {i}: {a}"
        if a == "NA":
            ev += " — Singh은 연구 10편 미만이라 NA로 표기. 저자가 직접 고르세요."
        am[i] = {"answer": S3[a], "evidence": ev, "page": None}
    outcome = "Depressive symptoms (resistance exercise)" if main["label"] == "Resistance exercise" else "Depressive symptoms"
    ex = {
        "outcome": f(outcome, fig), "k": f(r["table1_review_total"]["k"], t1), "n": f(r["table1_review_total"]["n"], t1),
        "population": f(pop, "[기준값] Singh 2026 Table 1"), "design": f("RCT", "[기준값] Singh 2026은 RCT 메타분석만 포함"),
        "characteristics": f(ch, "[기준값] Singh 2026 Table 1"),
        "effect_measure": f("SMD", "[기준값] Singh 2026은 모든 결과를 SMD로 합성"),
        "estimate": f(main["smd"], fig), "ci_low": f(main["ci_low"], fig), "ci_high": f(main["ci_high"], fig),
        "i2": f(None), "p_het": f(None), "model": f(None), "egger_p": f(None),
        "lower_favours_intervention": True, "amstar": am,
        "_warnings": ["No. of studies와 Total sample은 이 분석이 아니라 리뷰 전체 기준(Singh Table 1)입니다.",
                      "I²와 이질성 p는 Singh 2026에 리뷰별로 나와 있지 않아 비워 두었습니다. 원문에서 확인하세요."],
    }
    if r["first_author"] == "Zang":
        ex["_mock_fail_once"] = True   # 재시도 흐름을 보여 주는 데모용 모의 실패
    return ex


def main():
    ref = json.loads(REF.read_text(encoding="utf-8"))
    papers = []
    for r in ref["reviews"]:
        dep = "dep" in r["outcomes"]
        has = dep and r["open_access"].startswith("likely") and r["fig2_depression_smd"]
        papers.append({
            "uid": r["doi"], "pmid": r.get("pmid"), "doi": r["doi"], "title": r["title"].replace("students' ", "students’ "),
            "first_author": r["first_author"], "year": r["year"], "journal": r["journal"], "source": "search",
            "included": dep, "exclude_reason": None if dep else "결과 불일치 (우울 결과 없음)", "demo_include": dep,
            "fulltext": "missing" if dep else "pending",
            "stored": stored(r) if has else None, "extraction": None, "reviewed": False,
        })
    data = {
        "meta": {"source": "reference", "note": "LLM 추출이 아니라 Singh 2026(CC BY)에서 옮긴 기준값입니다.",
                 "model": None, "prompt_version": None, "created": "2026-11-14"},
        "pico": {"question": "운동(신체활동) 중재는 아동·청소년의 우울 증상을 줄이는가?",
                 "P": "5~18세 아동·청소년 (건강군 및 임상군)", "I": "운동 중재 (유산소, 근력, 복합, 심신 운동 등)",
                 "C": "중재 없음, 대기, 일반 관리, 비운동 대조", "O": "Depressive symptoms (depression)", "query": ""},
        "demo_query": QUERY,
        "search": {"query": "", "records_identified": len(papers), "duplicates_removed": 0, "other_sources": 0,
                   "note": "데모: 참고 논문(Singh 2026)이 포함한 리뷰 21편을 검색 결과로 불러왔습니다. 실제 PubMed 검색 결과가 아닙니다."},
        "papers": papers, "doi_lookup": DOI_LOOKUP,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(papers)}편 (포함 {sum(p['included'] for p in papers)}, 예시 결과 {sum(bool(p['stored']) for p in papers)}) → {OUT.name}")


if __name__ == "__main__":
    main()
