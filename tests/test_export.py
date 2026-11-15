import io
import json
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt

from core.export import all_formats, fulltext_zip, table_xlsx
from core.figures import PRISMA_DESIGNS, forest_plot, prisma
from core.prisma import counts
from tests.test_logic import paper

DEMO = json.loads((Path(__file__).resolve().parent.parent / "data/demo/demo_results.json").read_text())


def test_all_formats_forest_and_prisma():
    from core.results import forest_rows
    rows = forest_rows([paper("SMD", -0.5, -0.8, -0.2), paper("SMD", -0.2, -0.4, 0.0)])
    files = all_formats(lambda: forest_plot(rows, "SMD"), 96)
    assert files["png"][:4] == b"\x89PNG" and files["pdf"][:4] == b"%PDF" and b"<svg" in files["svg"][:400]
    assert zipfile.is_zipfile(io.BytesIO(files["pptx"]))
    c = counts(DEMO["search"], DEMO["papers"])
    for d in PRISMA_DESIGNS:
        fig = prisma(c, d); plt.close(fig)


def test_table_xlsx_has_amstar_sheet():
    import openpyxl
    from core.results import amstar_rows
    p = paper("SMD", -0.5, -0.8, -0.2)
    for i in range(1, 17):
        p["extraction"]["amstar"][str(i)]["answer"] = "Yes"
    p["extraction"]["amstar"]["7"]["answer"] = "No"
    p["extraction"]["amstar"]["4"]["answer"] = "Partial Yes"
    p["extraction"]["amstar"]["15"]["answer"] = None
    wb = openpyxl.load_workbook(io.BytesIO(table_xlsx([{"First author, year": "A 2020"}], amstar_rows([p]))))
    assert wb.sheetnames == ["Characteristics", "AMSTAR 2 items"]
    assert wb["Characteristics"]["I1"].value == "AMSTAR 2 confidence"
    ws = wb["AMSTAR 2 items"]
    head = [c.value for c in ws[1]]
    assert head[0] == "First author, year" and head[2] == "2*" and head[3] == "3" and head[-1] == "Overall confidence"
    row = [c.value for c in ws[2]]
    assert row[0] == "A 2020" and row[4] == "PY" and row[7] == "N" and row[15] is None and row[-1] == "Low (provisional)"
    assert ws.cell(row=4, column=1).value.startswith("Y = yes")


def test_fulltext_zip_only_pdfs():
    ps = [{"uid": "a", "first_author": "Kim", "year": 2021}, {"uid": "b", "first_author": "Lee", "year": 2020}]
    data, n = fulltext_zip(ps, {"a": b"%PDF"}, {"a": [("s.docx", b"x")]})
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert n == 2 and names == ["main/Kim_2021.pdf", "supplementary/Kim_2021_1_s.docx"]
