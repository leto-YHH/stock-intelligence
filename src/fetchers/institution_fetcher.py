"""
三大法人共識清單產生器
找出外資、投信、自營商同時買超或同時賣超的個股
"""
import os
import logging
import requests
from datetime import date, timedelta

log = logging.getLogger(__name__)

# 監控的個股清單（可依需求擴充）
WATCH_STOCKS = {
    "2330": "台積電", "2454": "聯發科", "2303": "聯電", "2379": "瑞昱", "3711": "日月光投控",
    "2382": "廣達", "2353": "宏碁", "3231": "緯創", "2356": "英業達", "6669": "緯穎",
    "2882": "國泰金", "2881": "富邦金", "2891": "中信金", "2884": "玉山金", "2886": "兆豐金",
    "2603": "長榮", "2609": "陽明", "2615": "萬海", "2601": "益航", "2637": "慧洋-KY",
    "1303": "南亞", "1326": "台化", "1301": "台塑", "6505": "台塑石化", "1304": "台聚",
    "3008": "大立光", "3006": "晶技", "2327": "國巨", "2328": "廣宇", "3443": "創意",
    "2330": "台積電", "6282": "康舒", "2324": "仁寶", "2409": "友達",
}

STOCK_INDUSTRY = {
    "2330": "半導體", "2454": "半導體", "2303": "半導體", "2379": "半導體", "3711": "半導體",
    "2382": "科技硬體", "2353": "科技硬體", "3231": "科技硬體", "2356": "科技硬體", "6669": "科技硬體",
    "2882": "金融", "2881": "金融", "2891": "金融", "2884": "金融", "2886": "金融",
    "2603": "航運", "2609": "航運", "2615": "航運", "2601": "航運", "2637": "航運",
    "1303": "化工", "1326": "化工", "1301": "化工", "6505": "化工", "1304": "化工",
    "3008": "光電", "3006": "光電", "2327": "光電", "2328": "光電", "3443": "光電",
    "6282": "科技硬體", "2324": "科技硬體", "2409": "面板",
}


def fetch_institution_consensus() -> dict:
    """抓取三大法人共識清單"""
    token = os.environ.get("FINMIND_TOKEN", "")
    start_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    buy_list = []
    sell_list = []

    for code, name in WATCH_STOCKS.items():
        try:
            params = {
                "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                "data_id": code,
                "start_date": start_date,
                "token": token,
            }
            resp = requests.get("https://api.finmindtrade.com/api/v4/data", params=params, timeout=15)
            data = resp.json().get("data", [])
            if not data:
                continue

            # 找最新日期
            last_date = sorted(set(r.get("date", "") for r in data))[-1]
            rows = [r for r in data if r.get("date") == last_date]

            foreign = trust = dealer = 0
            for row in rows:
                n = row.get("name", "")
                buy = int(row.get("buy", 0))
                sell = int(row.get("sell", 0))
                net = (buy - sell) // 1000
                if "Foreign_Investor" in n:
                    foreign += net
                elif "Investment_Trust" in n:
                    trust += net
                elif "Dealer" in n:
                    dealer += net

            total = foreign + trust + dealer

            def fmt(v):
                if v == 0: return "0"
                return f"+{v:,}" if v > 0 else f"−{abs(v):,}"

            entry = {
                "code": code,
                "name": name,
                "ind": STOCK_INDUSTRY.get(code, "其他"),
                "foreign": fmt(foreign),
                "trust": fmt(trust),
                "dealer": fmt(dealer),
                "total": fmt(total),
                "foreignRaw": foreign,
                "totalRaw": total,
            }

            # 三方同時買超
            if foreign > 0 and trust > 0 and dealer > 0:
                buy_list.append(entry)
            # 三方同時賣超
            elif foreign < 0 and trust < 0 and dealer < 0:
                sell_list.append(entry)

        except Exception as e:
            log.warning(f"法人共識 {code} 失敗: {e}")
            continue

    # 依合計絕對值排序
    buy_list.sort(key=lambda x: abs(x["totalRaw"]), reverse=True)
    sell_list.sort(key=lambda x: abs(x["totalRaw"]), reverse=True)

    print(f"[Institution] 三方買超: {len(buy_list)} 檔，三方賣超: {len(sell_list)} 檔")
    return {"buy": buy_list, "sell": sell_list}