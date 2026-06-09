"""
從 Supabase 讀取持股清單，並抓取即時股價與法人買賣超
"""
import os
import logging
import yfinance as yf
from supabase import create_client

log = logging.getLogger(__name__)


def fetch_portfolio() -> list:
    """從 Supabase 讀取持股清單"""
    try:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_ANON_KEY"]
        supabase = create_client(url, key)
        res = supabase.table("portfolio").select("*").order("id").execute()
        return res.data or []
    except Exception as e:
        log.warning(f"Supabase 讀取失敗: {e}")
        return []


def fetch_stock_info(code: str) -> dict:
    """抓取個股即時收盤價與法人買賣超"""
    try:
        ticker = yf.Ticker(f"{code}.TW")
        hist = ticker.history(period="5d")
        if hist.empty:
            ticker = yf.Ticker(f"{code}.TWO")
            hist = ticker.history(period="5d")

        price = 0.0
        if not hist.empty:
            valid = hist["Close"].dropna()
            valid = valid[valid > 0]
            if len(valid) > 0:
                price = round(float(valid.iloc[-1]), 2)

        return {"price": price}
    except Exception as e:
        log.warning(f"股價抓取失敗 {code}: {e}")
        return {"price": 0.0}


def build_portfolio_data(holdings: list) -> list:
    """組合持股資料，計算損益"""
    result = []
    for h in holdings:
        code = h.get("code", "")
        cost = float(h.get("cost", 0))
        shares = int(h.get("shares", 0))
        info = fetch_stock_info(code)
        price = info["price"]

        pnl = round((price - cost) * shares * 1000)
        pnl_pct = round((price - cost) / cost * 100, 1) if cost > 0 else 0
        price_dir = "up" if price >= cost else "down"
        pnl_str = f"+{pnl:,}" if pnl >= 0 else f"−{abs(pnl):,}"
        pnl_pct_str = f"▲{pnl_pct}%" if pnl_pct >= 0 else f"▼{abs(pnl_pct)}%"

        result.append({
            "name": h.get("name", ""),
            "code": code,
            "shares": f"{shares}張",
            "cost": cost,
            "price": price,
            "pnl": pnl_str,
            "pnlPct": pnl_pct_str,
            "priceDir": price_dir,
            "entryDate": h.get("entry_date", ""),
        })
    return result