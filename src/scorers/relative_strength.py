"""
相對強度評分器
邏輯：計算每個產業相對加權指數的超額報酬
      4 週強度（60%）+ 12 週強度（40%）加權合併
      轉換為 0–100 分後輸出
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)


def _pct_return(series: pd.Series, days: int) -> Optional[float]:
    """計算 series 最近 N 個交易日的報酬率"""
    if series is None or len(series) < days + 1:
        return None
    return (series.iloc[-1] / series.iloc[-days] - 1) * 100


def calc_relative_strength(
    industry_histories: dict[str, pd.Series],
    benchmark_history: pd.Series,
) -> dict[str, float]:
    """
    計算各產業相對強度分數（0–100）

    Args:
        industry_histories : { 'SEMI': pd.Series(收盤價), ... }
                             每個產業用成分股平均收盤價組成
        benchmark_history  : pd.Series  加權指數收盤價

    Returns:
        { 'SEMI': 82.4, 'TECH': 67.1, ... }
    """
    scores_raw = {}

    for code, hist in industry_histories.items():
        if hist is None or hist.empty:
            log.warning(f"  {code} 無歷史資料，跳過")
            continue

        r4w  = _pct_return(hist, 20)   # 約 4 週
        r12w = _pct_return(hist, 60)   # 約 12 週

        b4w  = _pct_return(benchmark_history, 20)
        b12w = _pct_return(benchmark_history, 60)

        if r4w is None or r12w is None:
            continue

        # 超額報酬 = 個股報酬 - 大盤報酬
        excess_4w  = r4w  - (b4w  or 0)
        excess_12w = r12w - (b12w or 0)

        # 加權合併
        combined = excess_4w * 0.6 + excess_12w * 0.4
        scores_raw[code] = combined
        log.info(f"  {code}: 4W={r4w:+.2f}% 12W={r12w:+.2f}% "
                 f"超額={combined:+.2f}%")

    if not scores_raw:
        return {}

    # 標準化到 0–100（最高 100，最低 0）
    values = np.array(list(scores_raw.values()))
    v_min, v_max = values.min(), values.max()

    if v_max == v_min:
        return {code: 50.0 for code in scores_raw}

    normalized = {
        code: round((v - v_min) / (v_max - v_min) * 100, 1)
        for code, v in scores_raw.items()
    }
    return normalized


def build_industry_history(
    stock_histories: dict[str, pd.Series],
) -> pd.Series:
    """
    把多檔個股的歷史收盤價合併成產業平均（等權重）
    stock_histories: { '2330': pd.Series, '2454': pd.Series, ... }
    """
    valid = [s for s in stock_histories.values()
             if s is not None and not s.empty]
    if not valid:
        return pd.Series(dtype=float)

    df = pd.concat(valid, axis=1)
    df = df.ffill().dropna(how="all")
    return df.mean(axis=1)


# ── 測試用模擬資料 ─────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import numpy as np

    np.random.seed(42)
    dates = pd.date_range("2024-08-01", periods=90, freq="B")

    def sim(trend: float, noise: float = 1.0) -> pd.Series:
        r = np.random.randn(90) * noise + trend
        return pd.Series((1 + r / 100).cumprod() * 1000, index=dates)

    industry_histories = {
        "SEMI": sim(0.15),   # 強勢：每天平均 +0.15%
        "TECH": sim(0.08),
        "FIN":  sim(-0.02),  # 弱勢
        "SHIP": sim(0.05),
        "EV":   sim(-0.10),  # 最弱
    }
    benchmark = sim(0.05)   # 大盤每天平均 +0.05%

    scores = calc_relative_strength(industry_histories, benchmark)

    print("\n=== 相對強度評分結果 ===")
    for code, score in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score / 5)
        print(f"  {code:6} {score:5.1f}  {bar}")
