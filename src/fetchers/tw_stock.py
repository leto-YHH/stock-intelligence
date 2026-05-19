"""
台股大盤 + 個股抓取器
來源：
  - 大盤指數：台灣證交所公開 API（免費）
  - 個股：yfinance（代碼加 .TW）
"""

import logging
import requests
import yfinance as yf
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)

TAIEX_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw"


def fetch_taiex() -> dict:
    """抓取加權指數（優先用證交所 API，失敗則改用 yfinance）"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(TAIEX_URL, headers=headers, timeout=10)
        data = r.json()
        info  = data["msgArray"][0]
        price = float(info.get("z") or info.get("y", 0))
        prev  = float(info.get("y", price))
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        return {"symbol": "TAIEX", "name": "加權指數",
                "price": round(price, 2), "change": round(change, 2),
                "pct": round(pct, 2), "ok": True}
    except Exception as e:
        log.warning(f"證交所 API 失敗，改用 yfinance: {e}")
        return _yf_quote("^TWII", "加權指數")


def _yf_quote(symbol: str, name: str) -> dict:
    try:
        info   = yf.Ticker(symbol).fast_info
        price  = info.last_price or 0
        prev   = info.previous_close or price
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        return {"symbol": symbol, "name": name,
                "price": round(price, 2), "change": round(change, 2),
                "pct": round(pct, 2), "ok": True}
    except Exception as e:
        log.error(f"yfinance {symbol} 失敗: {e}")
        return {"symbol": symbol, "name": name,
                "price": None, "change": None, "pct": None, "ok": False}


def fetch_tw_stock(symbol: str, name: str) -> dict:
    """抓取台股個股（自動加 .TW）"""
    yf_sym = symbol if "." in symbol else f"{symbol}.TW"
    return _yf_quote(yf_sym, name)


def fetch_tw_history(symbol: str, days: int = 90) -> Optional[pd.Series]:
    """抓取台股個股歷史收盤價"""
    yf_sym = symbol if "." in symbol else f"{symbol}.TW"
    try:
        hist = yf.Ticker(yf_sym).history(period=f"{days}d")
        return hist["Close"] if not hist.empty else None
    except Exception as e:
        log.warning(f"歷史資料 {yf_sym} 失敗: {e}")
        return None


def fetch_tw_market(stocks_config: list) -> dict:
    """
    一次抓取大盤 + 多檔個股
    stocks_config: [{"symbol": "2330", "name": "台積電"}, ...]
    """
    result = {"index": fetch_taiex(), "stocks": []}
    for item in stocks_config:
        log.info(f"  抓取台股 {item['symbol']} {item.get('name','')}")
        result["stocks"].append(
            fetch_tw_stock(item["symbol"], item.get("name", item["symbol"]))
        )
    return result
