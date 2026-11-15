"""8단계 내보내기: 그림(PNG·SVG·PDF·PPTX), characteristics table(XLSX), 4단계 전문 zip."""
import io
import re
import zipfile

import matplotlib.pyplot as plt
import pandas as pd

from core.results import CHAR_COLS

DPI = {"보통 (96 dpi)": 96, "높음 (192 dpi)": 192, "인쇄용 (300 dpi)": 300, "최고 (400 dpi)": 400}
MIME = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "zip": "application/zip"}


def fig_bytes(fig, fmt: str, dpi: int = 300) -> bytes:
    buf = io.BytesIO()
    if fmt == "pptx":
        return _pptx(fig_bytes(fig, "png", dpi))
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=dpi, facecolor="white")
    return buf.getvalue()


def _pptx(png: bytes) -> bytes:
    from PIL import Image
    from pptx import Presentation
    from pptx.util import Inches
    w, h = Image.open(io.BytesIO(png)).size
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])   # 빈 슬라이드
    r = min(12.33 / w, 6.9 / h)
    pw, ph = w * r, h * r
    slide.shapes.add_picture(io.BytesIO(png), Inches((13.333 - pw) / 2), Inches((7.5 - ph) / 2), Inches(pw), Inches(ph))
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def all_formats(make_fig, dpi: int) -> dict:
    out = {}
    for fmt in ("png", "svg", "pdf", "pptx"):
        fig = make_fig()
        out[fmt] = fig_bytes(fig, fmt, dpi)
        plt.close(fig)
    return out


AMSTAR_NOTE = ["Y = yes; PY = partial yes; N = no; blank = not answered.",
               "* Critical domains (items 2, 4, 7, 9, 11, 13, 15). Overall confidence rated by the rules of Shea et al., BMJ 2017;358:j4008."]


def table_xlsx(rows: list[dict], amstar: list[dict] | None = None) -> bytes:
    """시트 1: Characteristics table, 시트 2: AMSTAR 2 items (문항별 답과 종합 등급)."""
    from openpyxl.utils import get_column_letter
    from core.results import amstar_columns
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(rows, columns=CHAR_COLS).to_excel(xw, index=False, sheet_name="Characteristics")
        ws = xw.sheets["Characteristics"]
        for col, width in zip("ABCDEFGHI", [20, 14, 13, 34, 22, 50, 28, 14, 20]):
            ws.column_dimensions[col].width = width
        cols = amstar_columns()
        pd.DataFrame(amstar or [], columns=cols).to_excel(xw, index=False, sheet_name="AMSTAR 2 items")
        ws2 = xw.sheets["AMSTAR 2 items"]
        ws2.column_dimensions["A"].width = 22
        for i in range(2, 18):
            ws2.column_dimensions[get_column_letter(i)].width = 5.5
        ws2.column_dimensions[get_column_letter(18)].width = 24
        start = ws2.max_row + 2
        for k, line in enumerate(AMSTAR_NOTE):
            ws2.cell(row=start + k, column=1, value=line)
    return buf.getvalue()


def fulltext_zip(papers, pdfs: dict, supp: dict) -> tuple[bytes, int]:
    """논문 PDF 모음: main/1저자_연도.pdf, supplementary/1저자_연도_번호_원래이름."""
    name = lambda p: re.sub(r"[^\w.-]+", "_", f"{p['first_author']}_{p['year']}")
    buf, n = io.BytesIO(), 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in papers:
            if p["uid"] in pdfs:
                z.writestr(f"main/{name(p)}.pdf", pdfs[p["uid"]]); n += 1
            for i, (fname, data) in enumerate(supp.get(p["uid"], []), 1):
                z.writestr(f"supplementary/{name(p)}_{i}_{fname}", data); n += 1
    return buf.getvalue(), n
