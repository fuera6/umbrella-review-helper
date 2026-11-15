"""7단계 forest plot의 전체 효과: 메타분석 요약값들을 무작위 효과 모형(REML)으로 다시 합성.

참고 논문(Singh 2026) Figure 2·3의 결과를 재현함을 tests/test_stats.py에서 확인한다.
"""
import math

Z = 1.959964


def _chi2_sf(x: float, df: int) -> float:
    from scipy.stats import chi2
    return float(chi2.sf(x, df))


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def reml(y: list[float], v: list[float]) -> dict:
    k = len(y)
    w0 = [1 / x for x in v]
    sw0, sw02 = sum(w0), sum(w * w for w in w0)
    mfe = sum(w * yi for w, yi in zip(w0, y)) / sw0
    q = sum(w * (yi - mfe) ** 2 for w, yi in zip(w0, y))
    t = max(0.0, (q - (k - 1)) / (sw0 - sw02 / sw0))     # DerSimonian–Laird로 시작
    for _ in range(500):                                  # REML 반복
        w = [1 / (x + t) for x in v]
        sw = sum(w)
        m = sum(wi * yi for wi, yi in zip(w, y)) / sw
        tn = sum(wi * wi * ((yi - m) ** 2 - vi) for wi, yi, vi in zip(w, y, v)) / sum(wi * wi for wi in w) + 1 / sw
        tn = max(0.0, tn)
        if abs(tn - t) < 1e-10:
            t = tn
            break
        t = tn
    w = [1 / (x + t) for x in v]
    sw = sum(w)
    mu = sum(wi * yi for wi, yi in zip(w, y)) / sw
    se = math.sqrt(1 / sw)
    s2 = (k - 1) * sw0 / (sw0 * sw0 - sw02)              # 전형적인 연구 내 분산 (Higgins–Thompson)
    z = mu / se
    return {"mu": mu, "lo": mu - Z * se, "hi": mu + Z * se, "tau2": t,
            "I2": 100 * t / (t + s2), "H2": (t + s2) / s2, "Q": q, "df": k - 1,
            "pQ": _chi2_sf(q, k - 1), "z": z, "pz": 2 * _norm_sf(abs(z)),
            "weights": [100 * wi / sw for wi in w]}


def pooled(rows: list[dict]) -> dict | None:
    """forest 행(같은 지표)들을 합성. 비율 지표는 log 척도에서 합성 후 되돌린다."""
    from core.results import RATIO
    if len(rows) < 2:
        return None
    ratio = rows[0]["measure"] in RATIO
    tr = math.log if ratio else (lambda x: x)
    y = [tr(r["est"]) for r in rows]
    v = [((tr(r["hi"]) - tr(r["lo"])) / (2 * Z)) ** 2 for r in rows]
    if any(not x > 0 for x in v):
        return None
    r = reml(y, v)
    back = math.exp if ratio else (lambda x: x)
    return {**r, "est": back(r["mu"]), "lo": back(r["lo"]), "hi": back(r["hi"])}
