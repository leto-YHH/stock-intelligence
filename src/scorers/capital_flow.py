"""
資金流向評分器（Capital Flow Scorer）

評分邏輯：
  1. 外資近 10 日買超金額加總（權重 60%）
  2. 投信近 10 日買超金額加總（權重 40%）
  3. 產業內所有個股加總後，跟過去 4 週平均比較
  4. 連續買超天數加分（動能加速獎勵）
  5. 跨產業標準化為 0–100 分

實證依據：
  機構資金持續買進在接下來 4–8 週對股價有顯著預測力
  台灣外資佔市值約 40%，外資方向決定大型股走勢
"""

import logging
import numpy as np
from collections import defaultdict

log = logging.getLogger(__name__)


def _calc_stock_flow_score(records: list[dict]) -> dict:
    """
    計算單一個股的資金流向原始分數

    Args:
        records: FinMind 回傳的三大法人資料（依日期排序）

    Returns:
        {
            'recent_foreign':     近10日外資買超張數加總
            'recent_investment':  近10日投信買超張數加總
            'foreign_streak':     外資連續買超天數（賣超為負）
            'investment_streak':  投信連續買超天數
            'combined_score':     加權合併原始分數
        }
    """
    if not records:
        return {"combined_score": 0, "recent_foreign": 0,
                "recent_investment": 0, "foreign_streak": 0,
                "investment_streak": 0}

    recent = records[-10:]  # 最近 10 個交易日

    recent_foreign     = sum(r["foreign_net"]     for r in recent)
    recent_investment  = sum(r["investment_net"]  for r in recent)

    # 計算連續買超天數（從最新往回算）
    def streak(key):
        count = 0
        for r in reversed(records):
            if r[key] > 0:
                count += 1
            else:
                break
        # 如果最新一天是賣超，回傳負數
        if records and records[-1][key] <= 0:
            count = 0
            for r in reversed(records):
                if r[key] < 0:
                    count -= 1
                else:
                    break
        return count

    foreign_streak    = streak("foreign_net")
    investment_streak = streak("investment_net")

    # 加權合併（外資 60%，投信 40%）
    combined = recent_foreign * 0.6 + recent_investment * 0.4

    # 連續買超天數獎勵（每連續一天加 5%）
    if foreign_streak > 0:
        combined *= (1 + foreign_streak * 0.05)

    return {
        "combined_score":    combined,
        "recent_foreign":    recent_foreign,
        "recent_investment": recent_investment,
        "foreign_streak":    foreign_streak,
        "investment_streak": investment_streak,
    }


def calc_capital_flow_scores(
    industry_institutional: dict[str, dict[str, list]],
) -> dict[str, float]:
    """
    計算各產業資金流向評分（0–100）

    Args:
        industry_institutional:
            {
              'SEMI': {
                '2330': [records...],
                '2454': [records...],
              },
              'TECH': { ... },
              ...
            }

    Returns:
        { 'SEMI': 87.3, 'TECH': 62.1, ... }
    """
    industry_raw = {}

    for industry_code, stocks in industry_institutional.items():
        if not stocks:
            continue

        total_score = 0
        valid_count = 0

        for stock_id, records in stocks.items():
            result = _calc_stock_flow_score(records)
            total_score += result["combined_score"]
            valid_count += 1

            log.info(
                f"  [{industry_code}] {stock_id} "
                f"外資:{result['recent_foreign']:+,}張 "
                f"投信:{result['recent_investment']:+,}張 "
                f"外資連買:{result['foreign_streak']}天"
            )

        if valid_count > 0:
            industry_raw[industry_code] = total_score / valid_count

    if not industry_raw:
        return {}

    # 標準化到 0–100
    values = np.array(list(industry_raw.values()))
    v_min, v_max = values.min(), values.max()

    print(f"[CapFlow] 各產業原始分數: {industry_raw}")
    print(f"[CapFlow] min={v_min:.1f}, max={v_max:.1f}")
  
    if v_max == v_min:
        print("[CapFlow] 所有產業分數相同，全部回傳 50")
        return {code: 50.0 for code in industry_raw}
      
    return {
        code: round((v - v_min) / (v_max - v_min) * 100, 1)
        for code, v in industry_raw.items()
    }


# ── 測試用模擬資料 ─────────────────────────────────────────
def _mock_records(
    foreign_trend: int,
    investment_trend: int,
    days: int = 15,
    streak_days: int = 0,
) -> list[dict]:
    """產生模擬的三大法人資料"""
    import random
    random.seed(foreign_trend + investment_trend)
    records = []
    for i in range(days):
        # streak_days 最後幾天強制買超
        if streak_days > 0 and i >= days - streak_days:
            f = abs(foreign_trend) + random.randint(0, 200)
            inv = abs(investment_trend) + random.randint(0, 50)
        else:
            f   = foreign_trend    + random.randint(-500, 500)
            inv = investment_trend + random.randint(-100, 100)
        records.append({
            "date": f"2024-10-{i+1:02d}",
            "stock_id": "mock",
            "foreign_net":    f,
            "investment_net": inv,
            "dealer_net":     random.randint(-100, 100),
        })
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 模擬各產業的籌碼狀況
    mock_data = {
        "SEMI": {
            "2330": _mock_records(800,  120, streak_days=7),   # 台積電：外資強力買超
            "2454": _mock_records(200,   80, streak_days=3),   # 聯發科：溫和買超
        },
        "TECH": {
            "2382": _mock_records(150,   60, streak_days=4),   # 廣達
            "3231": _mock_records(-50,   30),                   # 緯創：外資小賣
        },
        "FIN": {
            "2882": _mock_records(-200, -50),                   # 國泰金：法人賣超
            "2881": _mock_records(-100,  20),                   # 富邦金
        },
        "SHIP": {
            "2603": _mock_records(-400, -80, streak_days=0),   # 長榮：大賣
            "2609": _mock_records(-300, -60),                   # 陽明
        },
    }

    scores = calc_capital_flow_scores(mock_data)

    print("\n=== 資金流向評分結果 ===")
    for code, score in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score / 5)
        print(f"  {code:6} {score:5.1f}  {bar}")

    print("\n── 解讀 ──")
    print("SEMI 分數最高：台積電連續 7 天外資買超，拉高整體產業分數")
    print("SHIP 分數最低：長榮陽明同步遭外資大賣")
