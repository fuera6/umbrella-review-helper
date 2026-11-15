# Umbrella Review 도우미

umbrella review를 처음 하는 사람이 PubMed 검색부터 특성표 · PRISMA 흐름도 · forest plot까지
한 앱에서 끝내도록 돕는 교육용 프로토타입입니다. **진단·치료·처방 도구가 아닙니다.**

## 실행 (로컬)
```bash
pip install -r requirements.txt
streamlit run app.py
```
"키 없이 데모로 시작"을 누르면 API 키 없이 1~8단계를 모두 볼 수 있습니다.

## 배포 (Streamlit Community Cloud, 무료)
1. 이 폴더를 GitHub 공개 저장소에 올립니다. (`data/fulltext/`와 키는 .gitignore로 빠집니다)
2. share.streamlit.io → New app → 저장소 선택 → Main file: `app.py` → Deploy
3. `packages.txt`의 한글 글꼴(fonts-noto-cjk)이 자동 설치되어 그림의 한글이 깨지지 않습니다.
4. 배포 주소를 심사 기간 내내 열 수 있는지 확인하세요. (오래 안 쓰면 잠들 수 있음 → 발표 전 미리 깨우기)

## AI 선택 (Claude 또는 Gemini)
시작 화면에서 고릅니다. 키는 탭(세션) 메모리에만 있고 저장되지 않습니다.
- **Claude API (유료)**: 콘솔에서 키를 만들고 크레딧을 충전합니다. 자세한 방법과 요금은 https://docs.claude.com
- **Google Gemini API (무료 등급 가능)**: Google AI Studio에서 키를 받습니다. 무료 등급은 분당·일일 요청 수 제한이 있고,
  한도를 넘으면 앱이 잠시 기다렸다 다시 시도합니다. 무료 등급 입력은 Google 서비스 개선에 쓰일 수 있으므로 공개된 논문만 올리세요.
  모델은 키 확인 후 목록에서 고릅니다(이름에 flash가 들어간 모델 권장).
- 두 AI 모두 같은 추출 지침(prompts/extract_v3.txt)과 같은 결과 형식을 씁니다.

## 데모 데이터
- 주제: 운동 중재와 아동·청소년 우울 증상
- 참고 논문: Singh B, et al. J Am Acad Child Adolesc Psychiatry 2026;65(2):171-186 (CC BY 4.0)
- 지금 데모 값은 **LLM 추출이 아니라 참고 논문에서 옮긴 기준값**입니다(화면에 표시됨). 4단계의 '데모: 예시 논문 채우기'로 7편을 불러옵니다.
  오픈액세스 논문을 Batch API로 분석하면 그 결과로 바꿉니다 (아래).

## LLM 추출 결과로 데모 바꾸기
1. `python tools/build_demo_config.py` → DOI로 PMID를 찾아 `data/demo/demo_config.json` 생성 (PubMed 접속 필요)
2. 오픈액세스 PDF를 `data/fulltext/<PMID>.pdf`로 저장, config의 license 채우기
3. `export ANTHROPIC_API_KEY=...` (본인 키, 파일에 적지 말 것)
4. `python tools/batch_extract.py submit` → `status` → `collect`
5. 먼저 1~2편을 앱 API 모드로 돌려 근거 인용·쪽수가 맞는지 확인한 뒤 전체를 돌리세요.

## 폴더 구조
```
app.py                      진입점
core/state.py               공유 상태, 논문 한 편의 형식
core/ui.py                  글꼴·색, 왼쪽 메뉴, '이 단계는 왜?' 상자
core/llm.py                 Claude: 키 확인, 검색식 추천(1단계)
core/gemini.py              Gemini: 키 확인·모델 목록, 검색식 추천, 추출 (JSON 모드)
core/providers.py           AI 선택에 따라 Claude/Gemini로 나눔
core/pubmed.py              PubMed 검색·메타데이터·DOI→PMID (E-utilities, 키 불필요)
core/query_check.py         1단계 검색식 형식 검사
core/stats.py               forest plot 전체 효과 (REML)
core/export.py              내보내기 (PNG·SVG·PDF·PPTX·XLSX·zip)
core/extract.py             LLM 추출: 출력 스키마, 요청, 결과 변환
core/amstar.py              AMSTAR 2 종합 등급 규칙 (Shea 2017)
core/prisma.py              PRISMA 숫자 자동 집계와 검사
core/results.py             특성표·forest 행·해설 문장 정리 (효과 방향 맞추기 포함)
core/figures.py             forest plot · PRISMA 4종 (PNG·SVG·PDF)
prompts/extract_v3.txt      추출 프롬프트
views/                      단계별 화면 (파일 하나 = 단계 하나)
tools/                      데모 데이터 생성, Batch API 사전 분석
data/demo/                  데모 데이터
data/validation/            참고 논문 기준값 (검증용)
tests/                      자동 테스트 42개 (python -m pytest tests)
```

## 구현 상태
| 단계 | 데모 모드 | API 모드 |
|---|---|---|
| 1 PICO | 직접 입력 · AI 추천(예시 검색식) · 형식 검사 | + AI가 PICO로 검색식 작성 |
| 2 PubMed 검색 | 저장된 검색 결과 | 실제 검색 (최대 500건) |
| 3 스크리닝 | 포함/제외·사유 · 정렬 · DOI/직접 추가 · 완전 제거 · 최종 목록 확인/CSV | DOI 추가는 PubMed 조회 |
| 4 전문 확보 | 본문·보충자료 올리기 · 예시 7편 채우기 · zip 저장 | 같음 |
| 5 LLM 추출 | 진행 막대 · 예상 시간 · ✓/✗ · 재시도 | Claude로 논문별 추출 (보충자료 PDF 함께 전달) |
| 6 저자 검토 | 특성표 · 요약값 · AMSTAR 2(문항 설명) · 전체 검토 후 다음 | + 본문 PDF 쪽 보기 |
| 7 표·그림 | 논문형 표 · PRISMA 4종 · forest plot(REML 합성·이질성) | 같음 |
| 8 내보내기 | PNG·SVG·PDF·PPT(해상도 선택) · 표 XLSX | 같음 |

⚠ 실제 PubMed · Claude · Gemini 호출은 개발 환경에서 외부 접속이 막혀 가짜 응답으로만 시험했습니다. 배포 후 한 번씩 직접 확인하세요.
