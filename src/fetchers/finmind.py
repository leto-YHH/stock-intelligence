"""
FinMind API 抓取器
功能：台股三大法人買賣超（外資、投信、自營商）
"""
import os
import logging
import requests
from datetime import date, timedelta

log = logging.getLogger(__name__)
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

def _get_token() -> str:
    token = os.getenv("FINMIND_TOKEN", "")
    print(f"[FinMind] token 長度: {len(token)}, 前10碼: {token[:10] if token else '空白'}")
    return token

def fetch_institutional_investors(
    stock_id: str,
    start_date: str = None,
    end_date: str = None,
) -> list[dict]:
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "dataset":  "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id":  stock_id,
        "start_date": start_date,
        "end_date":   end_date,
        "token":    _get_token(),
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        print(f"[FinMind] {stock_id} 狀態碼: {r.status_code}")
        r.raise_for_status()
        raw = r.json().get("data", [])
        print(f"[FinMind] {stock_id} 回傳筆數: {len(raw)}")

        results = []
        for row in raw:
            name = row.get("name", "")
            net  = int(row.get("buy", 0)) - int(row.get("sell", 0))
            entry = next(
                (x for x in results if x["date"] == row["date"]), None
            )
            if entry is None:
                entry = {"date": row["date"], "stock_id": stock_id,
                         "foreign_net": 0, "investment_net": 0, "dealer_net": 0}
                results.append(entry)
            if "Foreign_Investor" in name:
                entry["foreign_net"] += net
            elif "Investment_Trust" in name:
                entry["investment_net"] += net
            elif "Dealer" in name:
                entry["dealer_net"] += net
        return sorted(results, key=lambda x: x["date"])
    except Exception as e:
        print(f"[FinMind ERROR] {stock_id}: {e}")
        log.warning(f"FinMind {stock_id} 三大法人失敗: {e}")
        return []

def fetch_industry_institutional(
    stock_ids: dict[str, list[str]],
    days: int = 15,
) -> dict[str, dict[str, list]]:
    start = (date.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    results = {}
    for industry_code, symbols in stock_ids.items():
        results[industry_code] = {}
        for sid in symbols:
            print(f"[FinMind] 抓取 [{industry_code}] {sid}")
            results[industry_code][sid] = fetch_institutional_investors(
                sid, start_date=start
            )
    return results


def fetch_monthly_revenue(
    stock_id: str,
    months: int = 18,
) -> list[dict]:
    """
    抓取單一個股的月營收資料
    回傳：[{'year': 2024, 'month': 1, 'revenue': 200000}, ...]
    """
    start = (date.today() - timedelta(days=months * 31)).strftime("%Y-%m-%d")

    params = {
        "dataset":    "TaiwanStockMonthRevenue",
        "data_id":    stock_id,
        "start_date": start,
        "token":      _get_token(),
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json().get("data", [])
        print(f"[FinMind Revenue] {stock_id} 回傳筆數: {len(raw)}")
        if raw:
            print(f"[FinMind Revenue] 欄位範例: {raw[0]}")
        results = []
        for row in raw:
            results.append({
                "year":    int(row.get("revenue_year",  0)),
                "month":   int(row.get("revenue_month", 0)),
                "revenue": int(row.get("revenue", 0)),
            })
        return sorted(results, key=lambda x: (x["year"], x["month"]))
    except Exception as e:
        log.warning(f"FinMind {stock_id} 月營收失敗: {e}")
        return []


def fetch_industry_revenues(
    stock_ids: dict[str, list[str]],
    months: int = 18,
) -> dict[str, dict[str, list]]:
    """
    批次抓取多產業月營收
    回傳 { 'SEMI': { '2330': [records...], ... }, ... }
    """
    results = {}
    for industry_code, symbols in stock_ids.items():
        results[industry_code] = {}
        for sid in symbols:
            log.info(f"  FinMind 抓取 [{industry_code}] {sid} 月營收")
            results[industry_code][sid] = fetch_monthly_revenue(sid, months=months)
    return results
