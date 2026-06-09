"""
從 Supabase 讀取持股清單，並抓取即時股價、法人買賣超、AI 分析
"""
import os
import logging
import requests
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


def fetch_stock_price(code: str) -> dict:
    """抓取個股收盤價與今日漲跌"""
    try:
        for suffix in [".TW", ".TWO"]:
            ticker = yf.Ticker(f"{code}{suffix}")
            hist = ticker.history(period="5d")
            if not hist.empty:
                valid = hist["Close"].dropna()
                valid = valid[valid > 0]
                if len(valid) >= 2:
                    price = round(float(valid.iloc[-1]), 2)
                    prev = round(float(valid.iloc[-2]), 2)
                    chg = round(price - prev, 2)
                    chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
                    return {"price": price, "prev": prev, "chg": chg, "chg_pct": chg_pct}
                elif len(valid) == 1:
                    price = round(float(valid.iloc[-1]), 2)
                    return {"price": price, "prev": price, "chg": 0, "chg_pct": 0}
        return {"price": 0, "prev": 0, "chg": 0, "chg_pct": 0}
    except Exception as e:
        log.warning(f"股價抓取失敗 {code}: {e}")
        return {"price": 0, "prev": 0, "chg": 0, "chg_pct": 0}


def fetch_institution_data(code: str) -> dict:
    """從 FinMind 抓取法人買賣超"""
    try:
        token = os.environ.get("FINMIND_TOKEN", "")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": code,
            "start_date": "2026-06-01",
            "token": token,
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json().get("data", [])
        if not data:
            return {"foreign": 0, "trust": 0, "dealer": 0, "total": 0}

        latest = {}
        for row in data:
            date = row.get("date", "")
            if date not in latest or date > latest[date].get("date", ""):
                latest[date] = row

        if not latest:
            return {"foreign": 0, "trust": 0, "dealer": 0, "total": 0}

        last_date = sorted(latest.keys())[-1]
        rows_on_date = [r for r in data if r.get("date") == last_date]

        foreign = trust = dealer = 0
        for row in rows_on_date:
            name = row.get("name", "")
            buy = int(row.get("buy", 0))
            sell = int(row.get("sell", 0))
            net = (buy - sell) // 1000
            if "外資" in name:
                foreign += net
            elif "投信" in name:
                trust += net
            elif "自營" in name:
                dealer += net

        total = foreign + trust + dealer
        return {
            "foreign": foreign,
            "trust": trust,
            "dealer": dealer,
            "total": total,
            "date": last_date,
        }
    except Exception as e:
        log.warning(f"法人資料抓取失敗 {code}: {e}")
        return {"foreign": 0, "trust": 0, "dealer": 0, "total": 0}


def analyze_stock_with_claude(
    name: str, code: str, cost: float, price: float,
    chg_pct: float, inst: dict, news_titles: list
) -> dict:
    """用 Claude 分析個股狀況"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        foreign = inst.get("foreign", 0)
        trust = inst.get("trust", 0)
        dealer = inst.get("dealer", 0)
        total = inst.get("total", 0)
        pnl_pct = round((price - cost) / cost * 100, 1) if cost > 0 else 0

        news_text = "\n".join(f"- {t}" for t in news_titles[:5]) if news_titles else "無相關新聞"

        prompt = f"""你是一位專業的台股分析師，請分析以下個股今日狀況。

股票：{name}（{code}）
成本：{cost} 元，現價：{price} 元，損益：{pnl_pct:+.1f}%
今日漲跌：{chg_pct:+.2f}%
法人今日買賣超（張）：外資 {foreign:+,}、投信 {trust:+,}、自營商 {dealer:+,}、合計 {total:+,}
相關新聞：
{news_text}

請回傳 JSON，包含：
1. signal: "buy"（加碼）/ "hold"（繼續持有）/ "watch"（觀察中）/ "sell"（考慮賣出）
2. signalText: 操作建議中文簡短標籤（4字以內）
3. reason: 分析原因（50-80字，說明今日漲跌原因、法人動態、操作建議）
4. tags: 陣列，最多2個標籤，每個標籤含 type 和 text
   - type 可選：tag-chip（籌碼）、tag-tech（技術面）、tag-theme（題材）、tag-fund（基本面）
   - text：標籤說明文字（4字以內）

格式：{{"signal": "...", "signalText": "...", "reason": "...", "tags": [{{"type": "...", "text": "..."}}]}}"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        import json
        return json.loads(text.strip())
    except Exception as e:
        log.warning(f"Claude 分析失敗 {code}: {e}")
        return {
            "signal": "hold",
            "signalText": "持有觀察",
            "reason": "今日資料分析暫時無法產生。",
            "tags": [],
        }


def build_portfolio_data(holdings: list, news_articles: list = None) -> list:
    """組合持股資料，計算損益並產生 AI 分析"""
    news_titles = [a.get("title", "") for a in (news_articles or [])]
    result = []

    for h in holdings:
        code = h.get("code", "")
        cost = float(h.get("cost", 0))
        shares = int(h.get("shares", 0))

        price_info = fetch_stock_price(code)
        price = price_info["price"]
        chg_pct = price_info["chg_pct"]

        inst = fetch_institution_data(code)

        analysis = analyze_stock_with_claude(
            name=h.get("name", ""),
            code=code,
            cost=cost,
            price=price,
            chg_pct=chg_pct,
            inst=inst,
            news_titles=news_titles,
        )

        pnl = round((price - cost) * shares * 1000)
        pnl_pct = round((price - cost) / cost * 100, 1) if cost > 0 else 0
        price_dir = "up" if price >= cost else "down"
        pnl_str = f"+{pnl:,}" if pnl >= 0 else f"−{abs(pnl):,}"
        pnl_pct_str = f"▲{pnl_pct}%" if pnl_pct >= 0 else f"▼{abs(pnl_pct)}%"

        def fmt_inst(val):
            if val == 0:
                return "0"
            return f"+{val:,}" if val > 0 else f"−{abs(val):,}"

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
            "inst": {
                "foreign": fmt_inst(inst.get("foreign", 0)),
                "trust": fmt_inst(inst.get("trust", 0)),
                "dealer": fmt_inst(inst.get("dealer", 0)),
                "total": fmt_inst(inst.get("total", 0)),
            },
            "instDir": {
                "foreign": "up" if inst.get("foreign", 0) >= 0 else "down",
                "trust": "up" if inst.get("trust", 0) >= 0 else "down",
                "dealer": "up" if inst.get("dealer", 0) >= 0 else "down",
                "total": "up" if inst.get("total", 0) >= 0 else "down",
            },
            "signal": analysis.get("signal", "hold"),
            "signalText": analysis.get("signalText", "持有觀察"),
            "reason": analysis.get("reason", ""),
            "tags": analysis.get("tags", []),
        })

    return result