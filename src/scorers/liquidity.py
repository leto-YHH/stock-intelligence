"""
流動性評分（第六維度）
篩選：日均成交量 < 100張 直接排除
評分：當日成交量 / 20日均量 的比值
"""
import logging
import numpy as np
import yfinance as yf

log = logging.getLogger(__name__)


def calc_liquidity_scores(all_stock_ids: dict) -> dict:
    """
    計算各產業流動性分數（0-100）
    all_stock_ids: {"TECH": ["2330", "2317", ...], "EV": [...], ...}
    回傳: {"TECH": 72.5, "EV": 45.0, ...}
    """
    industry_scores = {}

    for ind_code, symbols in all_stock_ids.items():
        scores = []
        for symbol in symbols:
            score = _calc_stock_liquidity(symbol)
            if score is not None:
                scores.append(score)
                print(f"[Liquidity] {symbol} 流動性分數: {score:.1f}")
            else:
                print(f"[Liquidity] {symbol} 資料不足，略過")

        if scores:
            industry_scores[ind_code] = round(float(np.mean(scores)), 1)
        else:
            industry_scores[ind_code] = 50.0  # 無資料給中性分數

    return industry_scores


def _calc_stock_liquidity(symbol: str) -> float | None:
    """
    計算單一個股流動性分數
    1. 門檻篩選：20日均量 < 100張 → 回傳 0（極低分，幾乎不會被選上）
    2. 評分：成交量比值 → 映射到 0-100 分
    """
    try:
        ticker = None
        hist = None

        for suffix in [".TW", ".TWO"]:
            t = yf.Ticker(f"{symbol}{suffix}")
            h = t.history(period="60d")
            if not h.empty and len(h) >= 20:
                ticker = t
                hist = h
                break

        if hist is None or len(hist) < 20:
            return None

        # 成交量單位：股 → 換算成張（1張 = 1000股）
        volume_lots = hist["Volume"] / 1000

        avg_20 = float(volume_lots.iloc[-20:].mean())
        latest = float(volume_lots.iloc[-1])

        print(f"[Liquidity] {symbol} 20日均量: {avg_20:.0f}張, 最新量: {latest:.0f}張")

        # 門檻篩選：20日均量 < 100張 → 極低分
        if avg_20 < 100:
            print(f"[Liquidity] {symbol} 均量不足100張，給予低分")
            return 10.0

        # 評分：量比（當日量 / 20日均量）
        # 量比 >= 2.0 → 100分（爆量）
        # 量比 = 1.0 → 60分（正常）
        # 量比 = 0.5 → 30分（縮量）
        # 量比 <= 0.2 → 10分（極度縮量）
        ratio = latest / avg_20 if avg_20 > 0 else 1.0
        ratio = max(0.1, min(ratio, 3.0))  # 限制在 0.1 ~ 3.0

        if ratio >= 2.0:
            score = 80.0 + (ratio - 2.0) / 1.0 * 20.0  # 2.0~3.0 → 80~100
            score = min(score, 100.0)
        elif ratio >= 1.0:
            score = 60.0 + (ratio - 1.0) / 1.0 * 20.0  # 1.0~2.0 → 60~80
        elif ratio >= 0.5:
            score = 30.0 + (ratio - 0.5) / 0.5 * 30.0  # 0.5~1.0 → 30~60
        else:
            score = 10.0 + ratio / 0.5 * 20.0           # 0.1~0.5 → 10~30

        return round(score, 1)

    except Exception as e:
        log.warning(f"流動性計算失敗 {symbol}: {e}")
        return None