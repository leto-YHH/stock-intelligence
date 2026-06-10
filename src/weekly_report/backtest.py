"""
個股週期適配回測模組

核心邏輯：
  對每檔個股計算「過去持有 N 天的滾動勝率和平均報酬」
  使用滾動視窗（非全期固定值），避免過擬合

輸出：
  每檔個股在目標週期的 勝率 / 平均報酬 / 穩定度
  決定是否進入最終推薦名單
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)

# 各週期對應的持有交易日數
HOLD_DAYS = {"1m": 22, "3m": 66, "1y": 250}

# 各週期的最低門檻
MIN_WIN_RATE   = {"1m": 0.55, "3m": 0.55, "1y": 0.60}
MIN_AVG_RETURN = {"1m": 0.03, "3m": 0.03, "1y": 0.06}


def rolling_backtest(
    price_series: pd.Series,
    hold_days: int,
    window_weeks: int = 52,
) -> Optional[dict]:
    """
    對單一個股執行滾動持有回測

    Args:
        price_series : 收盤價 pd.Series（index 為日期）
        hold_days    : 持有天數（交易日）
        window_weeks : 回測視窗（週），預設一年

    Returns:
        {
            'win_rate':    勝率（持有後正報酬的比例）
            'avg_return':  平均報酬率
            'median_return': 中位數報酬率
            'max_drawdown':  最大單次虧損
            'stability':   報酬穩定度（1 - 標準差/平均絕對報酬）
            'sample_count': 有效樣本數
        }
        樣本數不足時回傳 None
    """
    if price_series is None or len(price_series) < hold_days + 20:
        return None

    # 只取最近 window_weeks 週的資料
    max_days = window_weeks * 5  # 一週約 5 個交易日
    series   = price_series.iloc[-max_days:] if len(price_series) > max_days else price_series

    returns = []
    for i in range(len(series) - hold_days):
        entry  = series.iloc[i]
        exit_  = series.iloc[i + hold_days]
        if entry > 0 and not np.isnan(entry) and not np.isnan(exit_):
            ret = (exit_ - entry) / entry
            if not np.isnan(ret):
                returns.append(ret)

    if len(returns) < 10:  # 樣本太少，不可信
        return None

    returns = np.array(returns)
    win_rate     = (returns > 0).mean()
    avg_return   = returns.mean()
    median_return = np.median(returns)
    max_drawdown = returns.min()

    # 穩定度：報酬越集中（標準差小）越穩定，0–1 之間
    std = returns.std()
    avg_abs = np.abs(returns).mean()
    stability = max(0, 1 - std / (avg_abs + 1e-6))
    stability = min(stability, 1.0)

    return {
        "win_rate":      round(float(win_rate),      4),
        "avg_return":    round(float(avg_return),    4),
        "median_return": round(float(median_return), 4),
        "max_drawdown":  round(float(max_drawdown),  4),
        "stability":     round(float(stability),     4),
        "sample_count":  len(returns),
    }


def screen_stocks(
    candidates: list[dict],
    price_histories: dict[str, pd.Series],
    period: str,
    top_n: int = 3,
) -> list[dict]:
    """
    個股三層篩選主流程

    Args:
        candidates     : 動能評分後的個股清單
                         [{'symbol':'2330','name':'台積電','momentum_score':87.3}, ...]
        price_histories: { '2330': pd.Series, ... }
        period         : '1m' | '3m' | '1y'
        top_n          : 最多推薦幾檔

    Returns:
        通過所有篩選的個股清單（含回測結果），依綜合評分排序
    """
    hold_days    = HOLD_DAYS[period]
    min_win      = MIN_WIN_RATE[period]
    min_ret      = MIN_AVG_RETURN[period]

    results = []

    for stock in candidates:
        symbol = stock["symbol"]
        name   = stock.get("name", symbol)
        hist   = price_histories.get(symbol)

        # ── 第三層：週期適配回測 ──────────────────────────
        window_map = {"1m": 52, "3m": 104, "1y": 260}
        bt = rolling_backtest(hist, hold_days, window_weeks=window_map[period])

        if bt is None:
            log.info(f"  {symbol} {name}: 歷史資料不足，跳過")
            continue
          
        print(f"[BT] {symbol} {name}: 勝率={bt['win_rate']:.1%} 均報={bt['avg_return']:+.1%} 門檻={min_win:.0%}/{min_ret:.0%}")
        passed = bt["win_rate"] >= min_win and bt["avg_return"] >= min_ret
      
        log.info(
            f"  {symbol} {name}: "
            f"勝率={bt['win_rate']:.1%} "
            f"均報={bt['avg_return']:+.1%} "
            f"穩定={bt['stability']:.2f} "
            f"{'✅ 通過' if passed else '❌ 未達標'}"
        )

        if not passed:
            continue

        # 綜合評分：動能分數 × 勝率 × 穩定度
        momentum = stock.get("momentum_score", 50)
        combined = momentum * bt["win_rate"] * (0.5 + bt["stability"] * 0.5)

        results.append({
            **stock,
            "backtest":       bt,
            "hold_days":      hold_days,
            "combined_score": round(combined, 2),
            "period":         period,
        })

    # 依綜合評分排序，取前 top_n
    results.sort(key=lambda x: -x["combined_score"])
    return results[:top_n]


def format_backtest_reasons(stock: dict) -> list[str]:
    """產生推薦理由文字"""
    bt     = stock["backtest"]
    period_label = {"1m": "1 個月", "3m": "3 個月", "1y": "1 年"}[stock["period"]]
    reasons = [
        f"過去 {period_label} 持有勝率 {bt['win_rate']:.0%}（樣本 {bt['sample_count']} 次）",
        f"平均報酬 {bt['avg_return']:+.1%}，中位數 {bt['median_return']:+.1%}",
        f"報酬穩定度 {bt['stability']:.0%}",
    ]
    if bt["max_drawdown"] < -0.10:
        reasons.append(f"⚠️ 最差情境曾虧損 {bt['max_drawdown']:.1%}，注意風險")
    return reasons


# ── 測試 ─────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    np.random.seed(42)

    dates = pd.date_range("2022-01-01", periods=600, freq="B")

    def sim_price(trend: float, vol: float = 0.012, start: float = 100.0) -> pd.Series:
        r = np.random.randn(600) * vol + trend
        return pd.Series(start * (1 + r).cumprod(), index=dates)

    # 模擬六檔個股，不同特性
    price_histories = {
        "2330": sim_price(0.0008),   # 台積電：穩定長期上漲
        "2454": sim_price(0.0005),   # 聯發科：溫和成長
        "2382": sim_price(0.0006),   # 廣達：中等
        "3231": sim_price(-0.0002),  # 緯創：略為下跌
        "2603": sim_price(-0.0005),  # 長榮：下跌趨勢
        "1536": sim_price(0.0004),   # 和大：小幅成長
    }

    candidates = [
        {"symbol": "2330", "name": "台積電",      "momentum_score": 91.0},
        {"symbol": "2454", "name": "聯發科",      "momentum_score": 78.5},
        {"symbol": "2382", "name": "廣達",        "momentum_score": 72.3},
        {"symbol": "3231", "name": "緯創",        "momentum_score": 55.1},
        {"symbol": "2603", "name": "長榮",        "momentum_score": 48.2},
        {"symbol": "1536", "name": "和大",        "momentum_score": 63.7},
    ]

    for period in ["1m", "3m", "1y"]:
        label = {"1m": "1個月", "3m": "3個月", "1y": "1年"}[period]
        print(f"\n{'='*50}")
        print(f"  週期：{label}｜持有 {HOLD_DAYS[period]} 個交易日")
        print(f"  門檻：勝率≥{MIN_WIN_RATE[period]:.0%}，均報≥{MIN_AVG_RETURN[period]:.0%}")
        print(f"{'='*50}")

        passed = screen_stocks(candidates, price_histories, period, top_n=3)

        if not passed:
            print("  本週期無符合條件個股")
            continue

        print(f"\n  推薦名單（Top {len(passed)}）：")
        for i, s in enumerate(passed, 1):
            bt = s["backtest"]
            print(f"\n  {i}. {s['name']}（{s['symbol']}）")
            print(f"     動能分數：{s['momentum_score']:.1f}")
            for reason in format_backtest_reasons(s):
                print(f"     • {reason}")
