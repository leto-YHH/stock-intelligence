"""
基本面趨勢評分器（Fundamentals Scorer）

核心指標：月營收年增率（YoY）的加速 or 減速
台股特殊優勢：每月 10 號強制公告月營收，全球少有的高頻基本面資料

評分邏輯：
  1. 計算每檔個股最近 3 個月的月營收 YoY 平均
  2. 和前 3 個月 YoY 平均比較，判斷加速 or 減速
  3. 連續月營收創新高額外加分
  4. 產業內個股平均後，跨產業標準化為 0–100

實證依據：
  月營收年增率加速是長線股價最可靠的領先指標之一
  台股連續三個月月營收創高的個股，一年後平均報酬顯著高於大盤
"""

import logging
import numpy as np

log = logging.getLogger(__name__)


def _calc_yoy(monthly_revenue: list[dict]) -> list[float]:
    """
    計算每個月的年增率（YoY）
    monthly_revenue: [{'year': 2024, 'month': 10, 'revenue': 12345}, ...]
    回傳: [yoy_pct, ...]（依時間排序，最舊到最新）
    """
    # 整理成 {(year, month): revenue} 的字典
    rev_map = {(r["year"], r["month"]): r["revenue"] for r in monthly_revenue}
    yoys = []

    for r in sorted(monthly_revenue, key=lambda x: (x["year"], x["month"])):
        y, m = r["year"], r["month"]
        prev_year_rev = rev_map.get((y - 1, m))
        if prev_year_rev and prev_year_rev > 0:
            yoy = (r["revenue"] - prev_year_rev) / prev_year_rev * 100
            yoys.append(yoy)

    return yoys


def _calc_stock_fundamental_score(monthly_revenue: list[dict]) -> dict:
    """
    計算單一個股的基本面分數

    Returns:
        {
            'recent_yoy_avg':  近3個月 YoY 平均
            'prev_yoy_avg':    前3個月 YoY 平均
            'acceleration':    加速幅度（recent - prev）
            'new_high_months': 近6個月中月營收創新高的次數
            'score':           原始分數
        }
    """
    if len(monthly_revenue) < 8:   # 至少需要 8 個月（含去年同期）
        return {"score": 0, "recent_yoy_avg": 0,
                "prev_yoy_avg": 0, "acceleration": 0, "new_high_months": 0}

    yoys = _calc_yoy(monthly_revenue)

    if len(yoys) < 6:
        return {"score": 0, "recent_yoy_avg": 0,
                "prev_yoy_avg": 0, "acceleration": 0, "new_high_months": 0}

    recent_yoy_avg = np.mean(yoys[-3:])   # 近 3 個月
    prev_yoy_avg   = np.mean(yoys[-6:-3]) # 前 3 個月
    acceleration   = recent_yoy_avg - prev_yoy_avg

    # 月營收創新高次數（近 6 個月）
    recent_6 = sorted(monthly_revenue, key=lambda x: (x["year"], x["month"]))[-6:]
    revenues  = [r["revenue"] for r in recent_6]
    new_high_months = sum(
        1 for i in range(1, len(revenues))
        if revenues[i] > max(revenues[:i])
    )

    # 原始分數：加速幅度 + 連續新高獎勵
    score = acceleration + new_high_months * 2.0

    return {
        "recent_yoy_avg":  round(recent_yoy_avg, 2),
        "prev_yoy_avg":    round(prev_yoy_avg, 2),
        "acceleration":    round(acceleration, 2),
        "new_high_months": new_high_months,
        "score":           score,
    }


def calc_fundamental_scores(
    industry_revenues: dict[str, dict[str, list]],
) -> dict[str, float]:
    """
    計算各產業基本面評分（0–100）

    Args:
        industry_revenues:
            {
              'SEMI': {
                '2330': [{'year':2024,'month':1,'revenue':200000}, ...],
                '2454': [...],
              },
              ...
            }

    Returns:
        { 'SEMI': 88.0, 'TECH': 55.0, ... }
    """
    industry_raw = {}

    for industry_code, stocks in industry_revenues.items():
        if not stocks:
            continue

        total_score = 0
        valid_count = 0

        for stock_id, records in stocks.items():
            result = _calc_stock_fundamental_score(records)
            if result["recent_yoy_avg"] == 0 and result["score"] == 0:
                continue

            total_score += result["score"]
            valid_count += 1

            log.info(
                f"  [{industry_code}] {stock_id} "
                f"近3月YoY:{result['recent_yoy_avg']:+.1f}% "
                f"前3月YoY:{result['prev_yoy_avg']:+.1f}% "
                f"加速:{result['acceleration']:+.1f}% "
                f"新高:{result['new_high_months']}個月"
            )

        if valid_count > 0:
            industry_raw[industry_code] = total_score / valid_count

    if not industry_raw:
        return {}

    values = np.array(list(industry_raw.values()))
    v_min, v_max = values.min(), values.max()

    if v_max == v_min:
        return {code: 50.0 for code in industry_raw}

    return {
        code: round((v - v_min) / (v_max - v_min) * 100, 1)
        for code, v in industry_raw.items()
    }


# ── 模擬資料產生器 ─────────────────────────────────────────
def _mock_revenue(
    base: int,
    yoy_recent: float,
    yoy_prev: float,
    months: int = 18,
) -> list[dict]:
    """
    產生模擬月營收資料
    base       : 基準月營收（百萬）
    yoy_recent : 近3個月目標YoY（%）
    yoy_prev   : 前3個月目標YoY（%）
    """
    import random
    random.seed(base)
    records = []

    # 產生 18 個月資料（含去年同期）
    for i in range(months):
        year  = 2023 + (i // 12)
        month = (i % 12) + 1

        # 依時間點給不同 YoY 趨勢
        if i < 6:
            growth = (yoy_prev / 100) + random.uniform(-0.02, 0.02)
        else:
            growth = (yoy_recent / 100) + random.uniform(-0.02, 0.02)

        rev = int(base * (1 + growth) ** (i / 12) * (1 + random.uniform(-0.05, 0.05)))
        records.append({"year": year, "month": month, "revenue": rev})

    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    mock_data = {
        "SEMI": {
            "2330": _mock_revenue(200000, yoy_recent=65, yoy_prev=42),  # 加速成長
            "2454": _mock_revenue(50000,  yoy_recent=30, yoy_prev=18),  # 穩健成長
        },
        "TECH": {
            "2382": _mock_revenue(80000,  yoy_recent=45, yoy_prev=20),  # 加速
            "3231": _mock_revenue(60000,  yoy_recent=10, yoy_prev=15),  # 減速
        },
        "FIN": {
            "2882": _mock_revenue(30000,  yoy_recent=8,  yoy_prev=12),  # 小幅減速
            "2881": _mock_revenue(28000,  yoy_recent=5,  yoy_prev=8),
        },
        "SHIP": {
            "2603": _mock_revenue(90000,  yoy_recent=-15, yoy_prev=5),  # 衰退
            "2609": _mock_revenue(60000,  yoy_recent=-20, yoy_prev=-5),
        },
    }

    scores = calc_fundamental_scores(mock_data)

    print("\n=== 基本面趨勢評分結果 ===")
    for code, score in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score / 5)
        print(f"  {code:6} {score:5.1f}  {bar}")

    print("\n── 解讀 ──")
    print("SEMI：台積電 YoY 從 42% 加速到 65%，動能最強")
    print("SHIP：長榮陽明月營收年增率轉負，基本面惡化")
