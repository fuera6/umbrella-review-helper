"""시연용 논문을 Batch API(요금 50% 할인)로 미리 분석해 데모 JSON을 만든다.

준비물
  data/fulltext/<PMID>.pdf           포함 논문 본문 PDF (공개 저장소에 올리지 않음, .gitignore 처리됨)
  data/fulltext/<PMID>_supp*.pdf     (선택) 보충자료 PDF
  data/demo/demo_config.json         PICO·검색 숫자·논문 목록 (demo_config.example.json 참고)
  환경변수 ANTHROPIC_API_KEY          팀원 본인 키. 코드·파일에 적지 말 것

사용
  python tools/batch_extract.py submit    # 요청 보내기 → batch id 저장
  python tools/batch_extract.py status    # 진행 상황 (보통 1시간 안, 최대 24시간)
  python tools/batch_extract.py collect   # 결과 받아 data/demo/demo_results.json 생성
"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.extract import PROMPT_VERSION, build_params, to_app_format, tool_input_from_message  # noqa: E402
from core.llm import MODEL_JUDGE  # noqa: E402

PDF_DIR = ROOT / "data" / "fulltext"
CONFIG = ROOT / "data" / "demo" / "demo_config.json"
BATCH_ID_FILE = ROOT / "data" / "demo" / "batch_id.txt"
OUT = ROOT / "data" / "demo" / "demo_results.json"
RAW_OUT = ROOT / "data" / "demo" / "raw_outputs.json"   # LLM 원본 출력 (보고서 부록용)


def _client():
    import anthropic
    return anthropic.Anthropic()   # ANTHROPIC_API_KEY 환경변수에서 읽음


def _config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def submit():
    cfg = _config()
    requests_ = []
    for p in cfg["papers"]:
        pdf = PDF_DIR / f"{p['pmid']}.pdf"
        if p.get("included", True) and pdf.exists():
            supp = [f.read_bytes() for f in sorted(PDF_DIR.glob(f"{p['pmid']}_supp*.pdf"))]
            requests_.append({"custom_id": f"pmid_{p['pmid']}",
                              "params": build_params(pdf.read_bytes(), cfg["pico"], supp, MODEL_JUDGE)})
        elif p.get("included", True):
            print(f"  PDF 없음 → 건너뜀 (앱에서 ✗로 표시): {p['pmid']}")
    if not requests_:
        sys.exit("보낼 PDF가 없습니다.")
    batch = _client().messages.batches.create(requests=requests_)
    BATCH_ID_FILE.write_text(batch.id)
    print(f"{len(requests_)}편 제출. batch id: {batch.id}")


def status():
    b = _client().messages.batches.retrieve(BATCH_ID_FILE.read_text().strip())
    print(b.processing_status, b.request_counts)


def collect():
    from core.pubmed import fetch_summaries
    client = _client()
    batch_id = BATCH_ID_FILE.read_text().strip()
    b = client.messages.batches.retrieve(batch_id)
    if b.processing_status != "ended":
        sys.exit(f"아직 끝나지 않았습니다: {b.processing_status}")

    raw, results, failed = {}, {}, []
    for r in client.messages.batches.results(batch_id):
        pmid = r.custom_id.removeprefix("pmid_")
        if r.result.type != "succeeded":
            failed.append((pmid, r.result.type))
            continue
        t = tool_input_from_message(r.result.message.content)
        raw[pmid] = {"model": r.result.message.model, "output": t,
                     "usage": r.result.message.usage.model_dump()}
        results[pmid] = to_app_format(t)

    cfg = _config()
    meta = fetch_summaries([p["pmid"] for p in cfg["papers"]])
    papers = []
    for p in cfg["papers"]:
        m = meta.get(p["pmid"], {})
        included = p.get("included", True)
        papers.append({
            "uid": p["pmid"], "pmid": p["pmid"], "doi": m.get("doi"), "title": m.get("title", ""),
            "first_author": m.get("first_author", ""), "year": m.get("year"), "journal": m.get("journal", ""),
            "source": "search", "included": included, "exclude_reason": p.get("exclude_reason"),
            "fulltext": "missing" if included else "pending",
            "stored": results.get(p["pmid"]),     # 4단계 '데모: 예시 논문 채우기' 후 5단계에서 나오는 값
            "extraction": None, "reviewed": False,
        })
    from core.demo import DEMO_PATH
    old = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps({
        "meta": {"source": "llm", "model": MODEL_JUDGE, "prompt_version": PROMPT_VERSION,
                 "batch_id": batch_id, "created": datetime.date.today().isoformat(),
                 "note": "Batch API로 미리 분석한 결과. 저자 검토 전 원본."},
        "pico": {**cfg["pico"], "query": ""}, "demo_query": cfg["pico"].get("query", ""),
        "search": {**cfg["search"], "note": "데모: 미리 불러온 검색 결과입니다."},
        "papers": papers, "doi_lookup": old.get("doi_lookup", {}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    RAW_OUT.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"성공 {len(results)}편 → {OUT.name}")
    for pmid, why in failed:
        print(f"  실패: {pmid} ({why}) — 앱에서 직접 다시 돌리거나 재제출")


if __name__ == "__main__":
    cmds = {"submit": submit, "status": status, "collect": collect}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]]()
