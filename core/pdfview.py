"""원문 PDF 쪽을 그림으로 그리고, 근거 문장의 위치를 찾아 노란색으로 강조한다 (6·7단계 '원문 대조').

근거 문장은 AI가 옮긴 것이라 줄바꿈·하이픈 때문에 원문과 조금 다를 수 있다.
그래서 문장 전체 → 앞부분 80자 → 50자 → 30자 순으로 찾고, 적힌 쪽에 없으면 다른 쪽도 찾아 본다.
"""
import re

SCALE = 1.6
RENDER_VERSION = 2   # 그리는 방식이 바뀌면 올린다 → 예전에 저장(캐시)해 둔 쪽 그림을 다시 쓰지 않음 (2 = 투명 형광펜)


def _clean(s: str) -> str:
    s = (s or "").replace("[Supplementary] ", "").replace("“", "").replace("”", "")
    s = s.replace("−", "-").replace("–", "-").replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = re.sub(r"\.{3}|…", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .;,")


def _candidates(evidence: str):
    s = _clean(evidence)
    if not s:
        return []
    out = [s]
    for n in (80, 50, 30):
        if len(s) > n:
            cut = s[:n].rsplit(" ", 1)[0]
            out.append(cut)
    pieces = sorted(re.split(r"[;,()\[\]]", s), key=len, reverse=True)   # 숫자가 든 긴 조각도 시도
    out += [p.strip() for p in pieces if len(p.strip()) >= 12]
    return list(dict.fromkeys(out))


def find_evidence(pdf: bytes, evidence: str, page_hint: int | None = None):
    """(쪽 번호 1부터, [사각형(left, bottom, right, top)…]) 또는 (page_hint, [])."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    n = len(doc)
    order = list(range(n))
    if page_hint and 1 <= page_hint <= n:
        order.remove(page_hint - 1)
        order.insert(0, page_hint - 1)
    for cand in _candidates(evidence):
        for i in order:
            tp = doc[i].get_textpage()
            searcher = tp.search(cand, match_case=False)
            hit = searcher.get_next()
            if hit:
                idx, cnt = hit
                return i + 1, [tp.get_rect(k) for k in range(tp.count_rects(idx, cnt))]
    return page_hint, []


def render(pdf: bytes, page: int, rects=()):
    """쪽 그림(PIL)과 전체 쪽 수. rects가 있으면 형광펜처럼 칠한다.

    '곱하기(multiply)' 방식으로 섞어서 흰 바탕만 노랗게 되고 검은 글씨는 그대로 보인다.
    (예전에는 노란 상자를 위에 덮어 그려서 글씨가 가려졌다)
    """
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops, ImageDraw
    doc = pdfium.PdfDocument(pdf)
    n = len(doc)
    page = max(1, min(page or 1, n))
    pg = doc[page - 1]
    img = pg.render(scale=SCALE).to_pil().convert("RGB")
    if rects:
        h = pg.get_size()[1]
        boxes = [(left * SCALE - 2, (h - top) * SCALE - 2, right * SCALE + 2, (h - bottom) * SCALE + 2)
                 for left, bottom, right, top in rects]
        marker = Image.new("RGB", img.size, (255, 255, 255))         # 흰색 = 바뀌지 않음
        d = ImageDraw.Draw(marker)
        for b in boxes:
            d.rectangle(b, fill=(255, 236, 110))                      # 연한 노랑
        img = ImageChops.multiply(img, marker)                        # 글씨(검정)는 그대로, 바탕만 노랗게
        d2 = ImageDraw.Draw(img)
        for b in boxes:                                               # 위치를 알아보기 쉽게 얇은 테두리
            d2.rectangle((b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2), outline=(230, 140, 0), width=2)
    return img, n
