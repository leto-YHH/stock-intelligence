"""
美股大盤 + 美國連動指數抓取器
資料來源：yfinance（免費，無需 API key）
"""

import logging
from datetime import timezone, timedelta
from typing import Optional
import yfinance as yf
import pandas as pd

log = logging.getLogger(__name__)

TZ_TW = timezone(timedelta(hours=8))

US_INDICES = [
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "^IXIC", "name": "Nasdaq"},
    {"symbol": "^DJI",  "name": "道瓊工業"},
    {"symbol": "^VIX",  "name": "VIX 恐慌指數"},
]

US_CORRELATION_MAP = {
    "SEMI":  {"symbol": "^SOX",  "name": "費城半導體"},
    "TECH":  {"symbol": "^NDX",  "name": "Nasdaq 100"},
    "FIN":   {"symbol": "^BKX",  "name": "KBW 銀行"},
    "SHIP":  {"symbol": "BDRY",  "name": "BDI ETF"},
    "EV":    {"symbol": "DRIV",  "name": "全球電動車 ETF"},
    "BIO":   {"symbol": "^NBI",  "name": "那斯達克生技"},
    "CHEM":  {"symbol": "XLB",   "name": "原物料 ETF"},
    "ELEC":  {"symbol": "^NDX",  "name": "Nasdaq 100"},
}


def fetch_quote(symbol: str, name: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info
        price  = info.last_price or 0
        prev   = info.previous_close or price
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        return {
            "symbol": symbol, "name": name,
            "price": round(price, 2), "change": round(change, 2),
            "pct": round(pct, 2), "ok": True,
        }
    except Exception as e:
        log.warning(f"抓取 {symbol} 失敗: {e}")
        return {"symbol": symbol, "name": name,
                "price": None, "change": None, "pct": None, "ok": False}


def fetch_history(symbol: str, days: int = 90) -> Optional[pd.Series]:
    try:
        hist = yf.Ticker(symbol).history(period=f"{days}d")
        return hist["Close"] if not hist.empty else None
    except Exception as e:
        log.warning(f"歷史資料 {symbol} 失敗: {e}")
        return None


def fetch_us_indices(indices_config: list = None) -> list:
    config = indices_config or US_INDICES
    results = []
    for item in config:
        log.info(f"  抓取美股大盤 {item['symbol']}")
        results.append(fetch_quote(item["symbol"], item["name"]))
    return results


def fetch_us_correlations(industry_codes: list = None) -> dict:
    codes = industry_codes or list(US_CORRELATION_MAP.keys())
    results, cache = {}, {}
    for code in codes:
        if code not in US_CORRELATION_MAP:
            continue
        mapping = US_CORRELATION_MAP[code]
        sym = mapping["symbol"]
        if sym not in cache:
            log.info(f"  抓取連動指數 {sym} ({mapping['name']})")
            cache[sym] = fetch_quote(sym, mapping["name"])
        results[code] = {**cache[sym], "industry_code": code}
    return results


def fetch_us_correlation_history(industry_code: str, days: int = 90) -> Optional[pd.Series]:
    if industry_code not in US_CORRELATION_MAP:
        return None
    return fetch_history(US_CORRELATION_MAP[industry_code]["symbol"], days)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("\n=== 美股大盤 ===")
    for q in fetch_us_indices():
        arrow = "▲" if (q["pct"] or 0) >= 0 else "▼"
        print(f"  {q['name']:12} {q['price']:>10,.2f}  {arrow}{abs(q['pct'] or 0):.2f}%")
    print("\n=== 美國連動指數 ===")
    for code, q in fetch_us_correlations().items():
        arrow = "▲" if (q["pct"] or 0) >= 0 else "▼"
        print(f"  [{code}] {q['name']:16} {q['price']:>10,.2f}  {arrow}{abs(q['pct'] or 0):.2f}%")
