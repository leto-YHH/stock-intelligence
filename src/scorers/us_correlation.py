"""
美國連動指數評分器
邏輯：計算美國對應指數相對 S&P 500 的強度
      轉換為 0–100 分，作為台灣對應產業的領先訊號
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)


def calc_us_correlation_scores(
    correlation_quotes: dict,
    sp500_pct: float,
) -> dict[str, float]:
    """
    計算美國連動指數評分（0–100）

    Args:
        correlation_quotes: fetch_us_correlations() 的輸出
                            { 'SEMI': {'pct': 2.3, ...}, ... }
        sp500_pct         : S&P 500 當日漲跌幅（%）

    Returns:
        { 'SEMI': 78.0, 'TECH': 65.0, ... }
    """
    excess = {}

    for code, quote in correlation_quotes.items():
        pct = quote.get("pct")
        if pct is None:
            continue
        # 超額報酬 vs S&P 500
        excess[code] = pct - sp500_pct
        log.info(f"  [{code}] {quote['name']} {pct:+.2f}% "
                 f"(超額 vs SPX: {excess[code]:+.2f}%)")

    if not excess:
        return {}

    values = np.array(list(excess.values()))
    v_min, v_max = values.min(), values.max()

    if v_max == v_min:
        return {code: 50.0 for code in excess}

    return {
        code: round((v - v_min) / (v_max - v_min) * 100, 1)
        for code, v in excess.items()
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    mock_quotes = {
        "SEMI": {"name": "費城半導體", "pct": 3.2},
        "TECH": {"name": "Nasdaq 100", "pct": 1.8},
        "FIN":  {"name": "KBW 銀行",   "pct": -0.5},
        "SHIP": {"name": "BDI ETF",    "pct": 0.3},
        "EV":   {"name": "電動車 ETF", "pct": -1.2},
    }
    sp500_pct = 0.8

    scores = calc_us_correlation_scores(mock_quotes, sp500_pct)

    print("\n=== 美國連動指數評分 ===")
    for code, score in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score / 5)
        print(f"  {code:6} {score:5.1f}  {bar}")
