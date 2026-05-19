"""
每週選股主流程
五個維度全部整合版
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

from src.scorers.relative_strength import calc_relative_strength
from src.scorers.news_sentiment    import calc_news_sentiment
from src.scorers.us_correlation    import calc_us_correlation_scores
from src.scorers.capital_flow      import calc_capital_flow_scores, _mock_records
from src.scorers.fundamentals      import calc_fundamental_scores, _mock_revenue

log = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def load_config():
    industries = json.loads((CONFIG_DIR / "industries.json").read_text())
    settings   = json.loads((CONFIG_DIR / "settings.json").read_text())
    return industries, settings


def score_industries(
    industry_histories, benchmark_history,
    correlation_quotes, sp500_pct,
    news_articles,
    industry_institutional,
    industry_revenues,
    period, weights,
):
    log.info("計算五維度產業評分...")

    rs_scores   = calc_relative_strength(industry_histories, benchmark_history)
    sent_scores = calc_news_sentiment(news_articles)
    us_scores   = calc_us_correlation_scores(correlation_quotes, sp500_pct)
    cap_scores  = calc_capital_flow_scores(industry_institutional)
    fund_scores = calc_fundamental_scores(industry_revenues)

    w = weights[period]
    all_codes = (set(rs_scores) | set(sent_scores) | set(us_scores)
                 | set(cap_scores) | set(fund_scores))

    results = []
    for code in all_codes:
        rs   = rs_scores.get(code,   50.0)
        sent = sent_scores.get(code, 50.0)
        us   = us_scores.get(code,   50.0)
        cap  = cap_scores.get(code,  50.0)
        fund = fund_scores.get(code, 50.0)

        total = (
            cap  * w["capital_flow"]      +
            sent * w["news_sentiment"]     +
            rs   * w["relative_strength"] +
            us   * w["us_correlation"]    +
            fund * w["fundamentals"]
        )
        results.append({
            "code": code, "score": round(total, 1),
            "breakdown": {
                "capital_flow":      cap,
                "news_sentiment":    sent,
                "relative_strength": rs,
                "us_correlation":    us,
                "fundamentals":      fund,
            }
        })

    return sorted(results, key=lambda x: -x["score"])


def run(period: str = "3m"):
    log.info(f"=== 每週選股開始，週期：{period} ===")
    industries, settings = load_config()
    weights = settings["scoring"]["weights"]
    top_n   = settings["scoring"]["top_industries_count"]
    ind_names = {k: v["name"] for k, v in industries.items()}

    # ── 模擬資料（GitHub Actions 上會換成真實 fetcher）────────
    np.random.seed(7)
    dates = pd.date_range("2024-08-01", periods=90, freq="B")

    def sim(trend, noise=1.0):
        r = np.random.randn(90) * noise + trend
        return pd.Series((1 + r/100).cumprod() * 1000, index=dates)

    industry_histories = {
        "SEMI": sim(0.12), "TECH": sim(0.09), "FIN": sim(0.01),
        "SHIP": sim(-0.03), "EV": sim(0.06), "BIO": sim(-0.01),
    }
    benchmark_history = sim(0.04)

    correlation_quotes = {
        "SEMI": {"name": "費城半導體", "pct": 2.8},
        "TECH": {"name": "Nasdaq 100", "pct": 1.5},
        "FIN":  {"name": "KBW 銀行",   "pct": -0.3},
        "SHIP": {"name": "BDI ETF",    "pct": -0.8},
        "EV":   {"name": "電動車 ETF", "pct": 0.9},
        "BIO":  {"name": "那斯達克生技","pct": 0.2},
    }

    news_articles = [
        {"title": "台積電 AI 晶片需求強勁", "industries": ["SEMI"], "sentiment_score": 0.85},
        {"title": "廣達 AI 伺服器出貨創新高", "industries": ["TECH"], "sentiment_score": 0.80},
        {"title": "Fed 降息預期升溫，金融股走強", "industries": ["FIN"], "sentiment_score": 0.65},
        {"title": "BDI 指數四連跌，航運承壓", "industries": ["SHIP"], "sentiment_score": -0.55},
        {"title": "電動車滲透率提升，零組件需求旺", "industries": ["EV"], "sentiment_score": 0.60},
    ]

    industry_institutional = {
        "SEMI": {
            "2330": _mock_records(800,  120, streak_days=7),
            "2454": _mock_records(200,   80, streak_days=3),
        },
        "TECH": {
            "2382": _mock_records(150,   60, streak_days=4),
            "3231": _mock_records(-50,   30),
        },
        "FIN": {
            "2882": _mock_records(-200, -50),
            "2881": _mock_records(-100,  20),
        },
        "SHIP": {
            "2603": _mock_records(-400, -80),
            "2609": _mock_records(-300, -60),
        },
        "EV": {
            "1536": _mock_records(100,   40, streak_days=2),
        },
        "BIO": {
            "1789": _mock_records(-50,   10),
        },
    }

    industry_revenues = {
        "SEMI": {
            "2330": _mock_revenue(200000, yoy_recent=65, yoy_prev=42),
            "2454": _mock_revenue(50000,  yoy_recent=30, yoy_prev=18),
        },
        "TECH": {
            "2382": _mock_revenue(80000,  yoy_recent=45, yoy_prev=20),
            "3231": _mock_revenue(60000,  yoy_recent=10, yoy_prev=15),
        },
        "FIN": {
            "2882": _mock_revenue(30000,  yoy_recent=8,  yoy_prev=12),
            "2881": _mock_revenue(28000,  yoy_recent=5,  yoy_prev=8),
        },
        "SHIP": {
            "2603": _mock_revenue(90000,  yoy_recent=-15, yoy_prev=5),
            "2609": _mock_revenue(60000,  yoy_recent=-20, yoy_prev=-5),
        },
        "EV": {
            "1536": _mock_revenue(15000,  yoy_recent=25, yoy_prev=15),
        },
        "BIO": {
            "1789": _mock_revenue(8000,   yoy_recent=5,  yoy_prev=10),
        },
    }

    ranked = score_industries(
        industry_histories, benchmark_history,
        correlation_quotes, 0.7,
        news_articles,
        industry_institutional,
        industry_revenues,
        period, weights,
    )

    top = ranked[:top_n]

    # ── 輸出報告 ──────────────────────────────────────────
    period_label = {"1m": "1 個月", "3m": "3 個月", "1y": "1 年"}[period]
    print(f"\n{'='*46}")
    print(f"  每週選股報告｜目標週期：{period_label}")
    print(f"{'='*46}")
    print(f"\n  {'排名':<4} {'產業':<12} {'綜合分':>6}  {'資金':>5} {'情緒':>5} {'強度':>5} {'連動':>5} {'基本面':>6}")
    print(f"  {'-'*60}")

    for i, ind in enumerate(top, 1):
        code = ind["code"]
        name = ind_names.get(code, code)
        bd   = ind["breakdown"]
        print(
            f"  {i:<4} {name:<12} {ind['score']:>6.1f}  "
            f"{bd['capital_flow']:>5.0f} "
            f"{bd['news_sentiment']:>5.0f} "
            f"{bd['relative_strength']:>5.0f} "
            f"{bd['us_correlation']:>5.0f} "
            f"{bd['fundamentals']:>6.0f}"
        )

    print(f"\n  ── 完整排名 ──")
    for i, ind in enumerate(ranked, 1):
        code = ind["code"]
        bar  = "█" * int(ind["score"] / 5)
        print(f"  {i}. [{code}] {ind_names.get(code,code):<12} {ind['score']:5.1f}  {bar}")

    log.info("=== 每週選股完成 ===")
    return top


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    period = os.getenv("REPORT_PERIOD", "3m")
    run(period)
