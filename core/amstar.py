"""AMSTAR 2 (Shea BJ et al. BMJ 2017;358:j4008). 종합 등급은 LLM이 아니라 이 규칙으로 계산한다.

- 핵심(critical) 문항: 2, 4, 7, 9, 11, 13, 15 → No면 '핵심 결함'
- 나머지 문항이 No → '비핵심 약점'
- High: 핵심 결함 0, 비핵심 약점 0~1 / Moderate: 핵심 결함 0, 약점 2개 이상
- Low: 핵심 결함 1 / Critically low: 핵심 결함 2개 이상
- 답하지 않은 문항이 있으면 등급을 '잠정'으로 표시한다.
"""
CRITICAL_ITEMS = {2, 4, 7, 9, 11, 13, 15}
PARTIAL_ITEMS = {2, 4, 7, 8, 9}


def answers_for(item: int) -> list[str]:
    return ["Yes", "Partial Yes", "No"] if item in PARTIAL_ITEMS else ["Yes", "No"]


ITEMS = {
    1: ("PICO 요소를 포함한 연구 질문", "연구 질문과 포함 기준에 대상(P)·중재(I)·비교(C)·결과(O)가 모두 들어 있으면 Yes."),
    2: ("사전 프로토콜 등록", "리뷰를 시작하기 전에 방법을 정해 두었는가(PROSPERO 등록 등). Partial Yes: 질문·검색·포함 기준·비뚤림 평가 방법이 담긴 프로토콜이 있음. Yes: 여기에 더해 합성(메타분석) 계획, 이질성 대처 계획, 프로토콜을 바꾼 이유까지 밝힘."),
    3: ("포함 연구 설계 선택 이유", "RCT만 넣을지, 관찰연구도 넣을지 고른 이유를 설명했으면 Yes."),
    4: ("포괄적인 문헌 검색", "Partial Yes: 데이터베이스 2개 이상, 검색어나 검색 전략 제시, 언어 등 제한의 이유 제시. Yes: 여기에 더해 포함 연구의 참고문헌·임상시험 등록부 검색, 전문가 자문, 회색문헌 검색, 리뷰 완료 24개월 이내 검색."),
    5: ("연구 선정을 2인이 수행", "두 사람이 독립적으로 연구를 골랐거나, 일부를 함께 골라 일치도가 높음(예: 80% 이상)을 보인 뒤 나머지를 한 사람이 했으면 Yes."),
    6: ("자료 추출을 2인이 수행", "두 사람이 자료를 추출했거나, 일부를 함께 추출해 일치도가 높음을 보였으면 Yes."),
    7: ("제외 논문 목록 · 사유", "Partial Yes: 전문을 읽고 제외한 연구의 목록을 제시함. Yes: 각 연구를 제외한 이유까지 제시함. 보충자료에 있으면 보충자료를 확인해서 판단합니다."),
    8: ("포함 연구 특성의 충분한 기술", "Partial Yes: 대상, 중재, 비교, 결과, 연구 설계를 기술함. Yes: 이를 자세히 기술하고 연구 환경과 추적 기간까지 기술함."),
    9: ("개별 연구의 비뚤림 위험 평가", "RoB 2, ROBINS-I, Newcastle-Ottawa처럼 알맞은 도구로 각 연구의 비뚤림 위험을 평가했으면 Yes. 일부 영역만 평가했으면 Partial Yes."),
    10: ("개별 연구의 연구비 출처 보고", "포함된 각 연구가 어디서 연구비를 받았는지 보고했으면 Yes. (대부분의 리뷰가 No인 문항입니다)"),
    11: ("적절한 메타분석 방법", "합성한 이유가 타당하고, 알맞은 가중치(고정/무작위 효과)를 쓰고, 이질성을 살펴봤으면 Yes."),
    12: ("비뚤림 위험이 결과에 미친 영향 평가", "비뚤림 위험이 높은 연구를 빼고 다시 분석하는 등, 비뚤림이 합성 결과에 미친 영향을 살폈으면 Yes."),
    13: ("비뚤림 위험을 고려한 해석", "결과를 해석하거나 논의할 때 개별 연구의 비뚤림 위험을 고려했으면 Yes."),
    14: ("이질성에 대한 설명", "연구 간 결과 차이(이질성)가 있을 때 그 원인을 살펴보고 논의했으면 Yes."),
    15: ("출판 비뚤림 평가", "funnel plot, Egger 검정 등으로 출판 비뚤림(작은 연구 효과)을 조사하고 그 영향을 논의했으면 Yes."),
    16: ("이해상충 · 연구비 보고", "리뷰 저자들의 이해상충과 리뷰 자체의 연구비를 보고했으면 Yes."),
}


def grade(answers: dict) -> dict:
    """answers: {문항번호(int 또는 str): "Yes"/"Partial Yes"/"No"/None}"""
    critical, weak, missing = [], [], []
    for i in range(1, 17):
        a = answers.get(i, answers.get(str(i)))
        if not a:
            missing.append(i)
        elif a == "No":
            (critical if i in CRITICAL_ITEMS else weak).append(i)
    rating = ("Critically low" if len(critical) >= 2 else "Low" if critical
              else "Moderate" if len(weak) >= 2 else "High")
    return {"rating": rating, "provisional": bool(missing), "critical_flaws": critical,
            "weaknesses": weak, "missing": missing}
