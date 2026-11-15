"""참고 umbrella review(Singh 2026)의 포함 리뷰로 data/demo/demo_config.json을 만든다.

- 우울(depression) 결과가 있는 리뷰 19편을 포함 목록으로 넣는다.
- DOI로 PubMed에서 PMID를 찾는다 (NCBI 접속 필요, 팀원 컴퓨터에서 실행).
- license는 비워 둔다. PubMed Central에서 각 논문의 라이선스를 확인해 직접 채울 것.

실행: python tools/build_demo_config.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.pubmed import doi_to_pmid  # noqa: E402

REF = ROOT / "data" / "validation" / "singh2026_reference.json"
OUT = ROOT / "data" / "demo" / "demo_config.json"

QUERY = (
    '("Exercise"[Mesh] OR "Sports"[Mesh] OR exercis*[tiab] OR "physical activity"[tiab] OR sport*[tiab] '
    'OR yoga[tiab] OR "resistance training"[tiab] OR "aerobic training"[tiab]) '
    'AND ("Depression"[Mesh] OR depress*[tiab]) '
    'AND ("Child"[Mesh] OR "Adolescent"[Mesh] OR child*[tiab] OR adolescen*[tiab] OR youth[tiab] OR student*[tiab]) '
    'AND (meta-analysis[pt] OR "systematic review"[pt] OR meta-analy*[tiab]) '
    'AND english[la] AND ("1900/01/01"[dp] : "2024/04/08"[dp])'
)


def main():
    ref = json.loads(REF.read_text(encoding="utf-8"))
    papers, missing = [], []
    for r in ref["reviews"]:
        if "dep" not in r["outcomes"]:
            continue
        pmid = doi_to_pmid(r["doi"])
        if pmid is None:
            missing.append(r["key"])
            continue
        r["pmid"] = pmid
        papers.append({"pmid": pmid, "included": True, "license": None, "ref_key": r["key"]})
    cfg = {
        "pico": {
            "question": "운동(신체활동) 중재는 아동·청소년의 우울 증상을 줄이는가?",
            "P": "5~18세 아동·청소년 (건강군 및 임상군)",
            "I": "운동 중재 (유산소, 근력, 복합, 심신 운동 등)",
            "C": "중재 없음, 대기, 일반 관리, 비운동 대조",
            "O": "Depressive symptoms (depression)",
            "query": QUERY,
        },
        "search": {"query": QUERY, "records_identified": 0, "duplicates_removed": 0},
        "papers": papers,
    }
    OUT.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    REF.write_text(json.dumps(ref, ensure_ascii=False, indent=2), encoding="utf-8")  # PMID 기록
    print(f"{len(papers)}편 → {OUT.name}")
    if missing:
        print("PMID를 못 찾음 (PubMed에서 직접 확인):", ", ".join(missing))
    print("다음: records_identified는 PubMed에서 QUERY를 실행한 건수로 채우고, license를 채우세요.")


if __name__ == "__main__":
    main()
