"""
FinMind API 抓取器
功能：台股三大法人買賣超（外資、投信、自營商）
文件：https://finmind.github.io/

免費版限制：每天 600 次請求
設定 FINMIND_TOKEN 環境變數可提升限額
"""

import os
import logging
import requests
from datetime import date, timedelta

log = logging.getLogger(__name__)

BASE_URL = "https://api.finmindtrade.com/api/v4/data"


def _get_token() -> str:
    return os.getenv("FINMIND_TOKEN", "")


def fetch_institutional_investors(
    stock_id: str,
    start_date: str = None,
    end_date: str = None,
) -> list[dict]:
    """
    抓取單一個股的三大法人買賣超
    stock_id  : 股票代碼，例如 '2330'
    start_date: 'YYYY-MM-DD'，預設 20 個交易日前
    end_date  : 'YYYY-MM-DD'，預設今天

    回傳：[{
        'date': '2024-10-01',
        'stock_id': '2330',
        'foreign_net': 12345,    # 外資買超張數（負為賣超）
        'investment_net': 500,   # 投信買超張數
        'dealer_net': -200,      # 自營商買超張數
    }, ...]
    """
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
        r.raise_for_status()
        raw = r.json().get("data", [])

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

            if "外資" in name:
                entry["foreign_net"] += net
            elif "投信" in name:
                entry["investment_net"] += net
            elif "自營" in name:
                entry["dealer_net"] += net

        return sorted(results, key=lambda x: x["date"])

    except Exception as e:
        log.warning(f"FinMind {stock_id} 三大法人失敗: {e}")
        return []


def fetch_industry_institutional(
    stock_ids: list[str],
    days: int = 10,
) -> dict[str, list]:
    """
    批次抓取多檔個股的三大法人資料
    回傳 { stock_id: [records...] }
    """
    start = (date.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    results = {}
    for sid in stock_ids:
        log.info(f"  FinMind 抓取 {sid} 籌碼資料")
        results[sid] = fetch_institutional_investors(sid, start_date=start)
    return results
