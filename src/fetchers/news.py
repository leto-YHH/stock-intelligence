"""
財經新聞抓取器
來源：RSS Feed（免費，無需 API key）
可選：NewsAPI（需 NEWSAPI_KEY 環境變數）
"""

import os
import logging
import feedparser
import requests
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)
TZ_TW = timezone(timedelta(hours=8))

RSS_FEEDS = [
    {"name": "鉅亨網",  "url": "https://news.cnyes.com/rss/index"},
    {"name": "經濟日報", "url": "https://money.udn.com/rssfeed/news/1001/5591/RSS.xml"},
    {"name": "Yahoo財經", "url": "https://tw.finance.yahoo.com/rss/"},
]

INDUSTRY_KEYWORDS = {
    "SEMI":  ["台積電", "聯發科", "晶圓", "半導體", "AI晶片", "HBM", "CoWoS", "先進封裝", "矽"],
    "TECH":  ["伺服器", "AI伺服器", "GPU", "散熱", "電源", "廣達", "緯創", "機殼"],
    "FIN":   ["升息", "降息", "Fed", "銀行", "壽險", "金控", "利率", "聯準會"],
    "SHIP":  ["BDI", "貨櫃", "散貨", "航運", "運費", "塞港", "長榮", "陽明"],
    "EV":    ["電動車", "Tesla", "特斯拉", "EV", "車用", "充電樁"],
    "BIO":   ["生技", "新藥", "醫材", "臨床", "FDA", "解盲", "藥廠"],
    "CHEM":  ["石化", "台塑", "乙烯", "原油", "原物料", "化工"],
    "ELEC":  ["大立光", "鏡頭", "光學", "被動元件", "MLCC", "電容"],
}


def _tag_industries(title: str, summary: str) -> list:
    """判斷新聞屬於哪些產業"""
    text = (title + " " + summary).lower()
    tagged = []
    for code, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tagged.append(code)
    return tagged


def fetch_rss(max_per_feed: int = 8) -> list:
    articles = []
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:max_per_feed]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", "")[:200]
                if not title:
                    continue
                articles.append({
                    "source":     feed_info["name"],
                    "title":      title,
                    "url":        entry.get("link", ""),
                    "summary":    summary,
                    "industries": _tag_industries(title, summary),
                })
        except Exception as e:
            log.warning(f"RSS {feed_info['name']} 失敗: {e}")
    return articles


def fetch_finance_news() -> list:
    """主入口：抓取並去重"""
    articles = fetch_rss()
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    log.info(f"新聞：共取得 {len(unique)} 則（去重後）")
    return unique[:20]
