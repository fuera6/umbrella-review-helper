"""Forest plot과 PRISMA 흐름도 4종 (matplotlib). 화면 표시와 내보내기에 함께 쓴다."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from core.results import RATIO, is_num  # noqa: E402
from core.stats import pooled  # noqa: E402

plt.rcParams["font.family"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"

NAVY, BLUE, GREEN, GREY = "#10213D", "#2457D6", "#1B7F3B", "#8A93A3"


def fmt_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def mn(s):
    return str(s).replace("-", "−")


# ------------------------------------------------------------------ forest plot
def _title(fig, title, height_in):
    """그림 맨 위 왼쪽에 제목 (내보내는 파일에도 들어감)."""
    if title:
        fig.text(0.012, 1 - 0.18 / height_in, title, fontsize=11.5, fontweight="bold", color=NAVY, ha="left", va="top")


def forest_plot(rows, measure, title=None):
    rows = list(rows)
    n, ratio = len(rows), measure in RATIO
    null = 1.0 if ratio else 0.0
    pool = pooled(rows)
    bottom_units = 2.3 if pool else 0.0           # Overall 행 + 이질성 3줄이 들어갈 자리 (행 단위)
    top_in = 0.95 if title else 0.5                # 제목 자리
    height = 1.45 + 0.42 * (n + bottom_units) + (top_in - 0.5)
    fig, ax = plt.subplots(figsize=(12, height))
    fig.subplots_adjust(left=0.43, right=0.73, top=1 - top_in / height, bottom=0.95 / height)
    _title(fig, title, height)
    ys = list(range(n, 0, -1))
    weights = pool["weights"] if pool else [None] * n
    for y, r, w in zip(ys, rows, weights):
        size = 5 + (w ** 0.5) * 1.9 if w else 8
        ax.plot([r["lo"], r["hi"]], [y, y], color=NAVY, lw=1.4, solid_capstyle="butt")
        ax.plot(r["est"], y, marker="s", ms=size, color=BLUE, mec=BLUE)
    ax.plot([null, null], [-0.4 if pool else 0.4, n + 0.5], color=GREY, lw=1, ls=(0, (3, 3)))
    if pool:
        yo = 0
        ax.add_patch(Polygon([[pool["lo"], yo], [pool["est"], yo + 0.28], [pool["hi"], yo], [pool["est"], yo - 0.28]],
                             closed=True, color=GREEN))
        ax.plot([pool["est"], pool["est"]], [0, n + 0.5], color=GREEN, lw=0.8, ls=(0, (2, 4)))
    vals = [v for r in rows for v in (r["lo"], r["hi"])] + ([pool["lo"], pool["hi"]] if pool else [])
    lo, hi = min(vals), max(vals)
    if ratio:
        ax.set_xscale("log")
        lo, hi = min(lo, 0.9), max(hi, 1.1)
        ticks = [t for t in (0.1, 0.2, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 10) if lo / 1.2 <= t <= hi * 1.2]
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{t:g}" for t in ticks])
        ax.set_xlim(lo / 1.15, hi * 1.15)
    else:
        lo, hi = min(lo, -0.2), max(hi, 0.2)
        pad = (hi - lo) * 0.06
        ax.set_xlim(lo - pad, hi + pad)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: mn(f"{v:g}")))
    ax.set_ylim(-bottom_units + 0.2 if pool else 0.4, n + 0.7)
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel(f"{measure}{' (log scale)' if ratio else ''}   ←  Favours intervention  |  Favours control  →",
                  fontsize=9, color=NAVY)
    tr = blended_transform_factory(ax.transAxes, ax.transData)
    T = lambda x, y, s, **k: ax.text(x, y, s, transform=tr, va="center", clip_on=False, color=k.pop("color", NAVY), **k)
    head = n + 1.0
    T(-1.42, head, "Meta-analysis", fontsize=9.5, fontweight="bold")
    T(-0.36, head, "k", fontsize=9.5, fontweight="bold", ha="center")
    T(-0.16, head, "I² (%)", fontsize=9.5, fontweight="bold", ha="center")
    T(1.04, head, f"{measure} (95% CI)", fontsize=9.5, fontweight="bold")
    T(1.92, head, "Weight (%)", fontsize=9.5, fontweight="bold", ha="right")
    ax.plot([-1.42, 1.92], [n + 0.6, n + 0.6], transform=tr, color=NAVY, lw=0.8, clip_on=False)
    for y, r, w in zip(ys, rows, weights):     # 결과(outcome)는 모든 리뷰에서 같다고 보므로 표시하지 않는다
        T(-1.42, y, r["label"] + ("†" if r["flipped"] else ""), fontsize=9.5)
        T(-0.36, y, str(r["k"]) if is_num(r["k"]) else "–", fontsize=9.5, ha="center")
        T(-0.16, y, f"{float(r['i2']):.1f}" if is_num(r["i2"]) else "–", fontsize=9.5, ha="center")
        T(1.04, y, mn(f"{r['est']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]"), fontsize=9.5)
        T(1.92, y, f"{w:.2f}" if w else "–", fontsize=9.5, ha="right")
    if pool:
        T(-1.42, 0, "Overall", fontsize=9.5, fontweight="bold")
        T(1.04, 0, mn(f"{pool['est']:.2f} [{pool['lo']:.2f}, {pool['hi']:.2f}]"), fontsize=9.5, fontweight="bold")
        T(1.92, 0, "100.00", fontsize=9.5, ha="right", fontweight="bold")
        lines = [f"Heterogeneity: τ² = {pool['tau2']:.2f}, I² = {pool['I2']:.2f}%, H² = {pool['H2']:.2f}",
                 mn(f"Test of θi = θj: Q({pool['df']}) = {pool['Q']:.2f}, {fmt_p(pool['pQ'])}"),
                 mn(f"Test of θ = {null:g}: z = {pool['z']:.2f}, {fmt_p(pool['pz'])}")]
        for i, s in enumerate(lines):
            T(-1.42, -0.62 - i * 0.42, s, fontsize=8.5)
    note = ("Random-effects REML model" if pool else "") + \
           ("   † direction reversed so that values below the null favour the intervention" if any(r["flipped"] for r in rows) else "")
    if note.strip():
        fig.text(0.012, 0.1 / height, note.strip(), fontsize=7.5, color=GREY)
    return fig


# ------------------------------------------------------------------ PRISMA
PRISMA_DESIGNS = ["미니멀 흑백", "컬러 블록", "측면 제외", "세로 캡슐"]


def _texts(c):
    ident = f"Reviews identified from\ndatabases (n = {c['identified']:,})"
    if c.get("other"):
        ident += f"\nother methods (n = {c['other']:,})"
    return [
        (ident, f"Duplicates removed\n(n = {c['dup']:,})"),
        (f"Reviews screened\n(n = {c['screened']:,})", f"Reviews excluded\n(n = {c['excluded']:,})"),
        (f"Reports sought for retrieval\n(n = {c['sought']:,})", f"Reports not retrieved\n(n = {c['not_retrieved']:,})"),
        (f"Reports assessed for eligibility\n(n = {c['assessed']:,})", None),
        (f"Reviews included in\numbrella review (n = {c['final']:,})", None),
    ]


def _box(ax, x, y, w, h, text, *, face="white", edge=NAVY, color=NAVY, lw=1.2, ls="-", size=9, bold=False, rounding=0.06):
    if rounding == 0:
        ax.add_patch(Rectangle((x, y), w, h, fc=face, ec=edge, lw=lw, ls=ls))
    else:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}",
                                    fc=face, ec=edge, lw=lw, ls=ls, mutation_aspect=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color,
            fontweight="bold" if bold else "normal", linespacing=1.4)


def _arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=1.1, shrinkA=0, shrinkB=0))


def prisma(c, design="미니멀 흑백", title=None):
    t = _texts(c)
    if design == "세로 캡슐":
        fig, ax = plt.subplots(figsize=(6.4, 7.4 + (0.6 if title else 0)))
        if title:
            fig.subplots_adjust(top=1 - 0.6 / 8.0)
            _title(fig, title, 8.0)
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        ys = [8.4, 6.5, 4.6, 2.7, 0.8]
        for i, ((main, side), y) in enumerate(zip(t, ys)):
            last = i == 4
            txt = main.replace("\n", " ") + (f"\n— {side.replace(chr(10), ' ')}" if side else "")
            _box(ax, 0.4, y, 9.2, 1.3, txt, face=BLUE if last else "#F1F4FB", edge=BLUE if last else "#C9D7F7",
                 color="white" if last else NAVY, lw=1.5, bold=last, rounding=0.65)
            if i < 4:
                _arrow(ax, 5, y, 5, ys[i + 1] + 1.3)
        return fig
    pr, color, mini = design == "측면 제외", design == "컬러 블록", design == "미니멀 흑백"
    fig, ax = plt.subplots(figsize=(8.8, 8.4 + (0.6 if title else 0)))
    if title:
        fig.subplots_adjust(top=1 - 0.6 / 9.0)
        _title(fig, title, 9.0)
    ax.set_xlim(0, 10.4); ax.set_ylim(0, 10); ax.axis("off")
    mx, mw, h = (1.4 if pr else 0.4), 4.3, 1.1
    sx, sw = mx + mw + 0.7, 3.4
    ys = [8.5, 6.65, 4.8, 2.95, 1.1]
    if pr:
        for lab, top, bot in [("Identification", 9.85, 8.35), ("Screening", 7.9, 2.95), ("Included", 2.35, 1.1)]:
            _box(ax, 0.2, bot, 0.8, top - bot, "", face="#C9D7F7", edge="#C9D7F7", rounding=0.15)
            ax.text(0.6, (top + bot) / 2, lab, rotation=90, ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color=NAVY)
    for i, ((main, side), y) in enumerate(zip(t, ys)):
        last = i == 4
        if color:
            face = BLUE if last else ("#C9D7F7" if i % 2 == 0 else "#E7EDFB")
            _box(ax, mx, y, mw, h, main, face=face, edge=face, color="white" if last else NAVY, bold=last, rounding=0.2)
        elif mini:
            _box(ax, mx, y, mw, h, main, lw=2 if last else 1.1, bold=last, rounding=0)
        else:
            _box(ax, mx, y, mw, h, main, lw=1.8 if last else 1.2, bold=last, rounding=0.05)
        if i < 4:
            _arrow(ax, mx + mw / 2, y, mx + mw / 2, ys[i + 1] + h)
        if side:
            sy, sh = y + 0.15, h - 0.3
            if color:
                _box(ax, sx, sy, sw, sh, side, face="#F4F5F7", edge="#F4F5F7", size=8.5, rounding=0.2)
            elif mini:
                _box(ax, sx, sy, sw, sh, side, size=8.5, lw=1, rounding=0)
            else:
                _box(ax, sx, sy, sw, sh, side, size=8.5, ls="--", rounding=0.05)
            _arrow(ax, mx + mw, y + h / 2, sx, y + h / 2)
    return fig
