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
from datetime import date

from src.scorers.relative_strength import calc_relative_strength
from src.scorers.news_sentiment    import calc_news_sentiment
from src.scorers.us_correlation    import calc_us_correlation_scores
from src.scorers.capital_flow      import calc_capital_flow_scores
from src.scorers.fundamentals      import calc_fundamental_scores, _mock_revenue
from src.weekly_report.backtest    import screen_stocks, format_backtest_reasons
from src.notifiers.email_notifier  import send_email
from src.fetchers.finmind          import fetch_industry_institutional

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


def build_html_report(period: str, ranked: list, stock_results: dict, ind_names: dict) -> str:
    period_label = {"1m": "1 個月", "3m": "3 個月", "1y": "1 年"}[period]
    today = date.today().strftime("%Y-%m-%d")

    rows = ""
    for i, ind in enumerate(ranked[:5], 1):
        code = ind["code"]
        bd   = ind["breakdown"]
        rows += f"""
        <tr>
          <td>{i}</td>
          <td>{ind_names.get(code, code)}</td>
          <td><b>{ind['score']}</b></td>
          <td>{bd['capital_flow']:.0f}</td>
          <td>{bd['news_sentiment']:.0f}</td>
          <td>{bd['relative_strength']:.0f}</td>
          <td>{bd['us_correlation']:.0f}</td>
          <td>{bd['fundamentals']:.0f}</td>
        </tr>"""

    stock_sections = ""
    for code, stocks in stock_results.items():
        ind_name = ind_names.get(code, code)
        if not stocks:
            stock_sections += f"<h3>📌 {ind_name}（無符合個股）</h3>"
            continue
        stock_sections += f"<h3>📌 {ind_name}</h3><ul>"
        for s in stocks:
            bt = s["backtest"]
            reasons = format_backtest_reasons(s)
            stock_sections += f"""
            <li>
              <b>{s['name']}（{s['symbol']}）</b><br>
              {'<br>'.join(f'• {r}' for r in reasons)}
            </li>"""
        stock_sections += "</ul>"

    explanation = """
    <hr>
    <h3>📖 名詞說明</h3>

    <h4>🔢 個股回測指標</h4>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
      <tr style="background:#f0f0f0">
        <th>指標</th><th>意思</th><th>怎麼看</th>
      </tr>
      <tr>
        <td><b>持有勝率</b></td>
        <td>過去持有 N 天後，獲利的機率</td>
        <td>越高越好，門檻為 55%（1年期 60%）</td>
      </tr>
      <tr>
        <td><b>平均報酬</b></td>
        <td>過去每次持有 N 天的平均獲利幅度</td>
        <td>越高越好，1個月門檻 +3%，3個月 +6%，1年 +12%</td>
      </tr>
      <tr>
        <td><b>中位數報酬</b></td>
        <td>排除極端值後的「典型」獲利幅度</td>
        <td>接近平均報酬代表結果穩定，差異大代表偶爾有極端值</td>
      </tr>
      <tr>
        <td><b>報酬穩定度</b></td>
        <td>每次持有的報酬是否集中、不飄移</td>
        <td>越高越穩定；低於 20% 代表結果波動大，風險較高</td>
      </tr>
    </table>

    <h4>🏭 產業評分維度（各 0–100 分）</h4>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
      <tr style="background:#f0f0f0">
        <th>維度</th><th>意思</th><th>1個月權重</th><th>3個月權重</th><th>1年權重</th>
      </tr>
      <tr>
        <td><b>資金（外資/投信）</b></td>
        <td>外資與投信近期買超張數，代表法人對該產業的信心</td>
        <td>35%</td><td>20%</td><td>10%</td>
      </tr>
      <tr>
        <td><b>情緒（新聞）</b></td>
        <td>AI 分析近期財經新聞的正負面情緒</td>
        <td>30%</td><td>15%</td><td>5%</td>
      </tr>
      <tr>
        <td><b>強度（相對強度）</b></td>
        <td>該產業股價相對大盤的強弱，強者恆強</td>
        <td>20%</td><td>30%</td><td>20%</td>
      </tr>
      <tr>
        <td><b>連動（美國指數）</b></td>
        <td>對應美國連動指數（費城半導體、BDI 等）的超額報酬</td>
        <td>15%</td><td>20%</td><td>15%</td>
      </tr>
      <tr>
        <td><b>基本面（月營收）</b></td>
        <td>近期月營收年增率是否加速成長</td>
        <td>0%</td><td>15%</td><td>50%</td>
      </tr>
    </table>

    <p style="color:#888;font-size:12px;">
    ⚠️ 本報告由 Stock Intelligence System 自動產生，所有數據來自歷史回測，不代表未來表現，僅供參考，不構成投資建議。投資人須自行承擔投資風險。
    </p>
    """

    return f"""
    
    <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:auto;">
    <h2>📊 每週選股報告｜{today}｜目標週期：{period_label}</h2>

    <h3>🏆 產業排名</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
      <tr style="background:#f0f0f0">
        <th>排名</th><th>產業</th><th>綜合分</th>
        <th>資金</th><th>情緒</th><th>強度</th><th>連動</th><th>基本面</th>
      </tr>
      {rows}
    </table>

    <h3>⭐ 推薦個股</h3>
    {stock_sections}

    <hr>
    <small>本報告由 Stock Intelligence System 自動產生，僅供參考，不構成投資建議。</small>
    </body></html>
    """


def run(period: str = "3m"):
    log.info(f"=== 每週選股開始，週期：{period} ===")
    industries, settings = load_config()
    weights   = settings["scoring"]["weights"]
    top_n     = settings["scoring"]["top_industries_count"]
    top_stk   = settings["scoring"]["top_stocks_per_industry"]
    ind_names = {k: v["name"] for k, v in industries.items()}

    # ── 模擬資料（相對強度、連動、新聞，之後換真實 fetcher）──
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

    # ── 基本面：還是模擬（之後換真實月營收）──────────────────
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
        "EV":   {"1536": _mock_revenue(15000, yoy_recent=25, yoy_prev=15)},
        "BIO":  {"1789": _mock_revenue(8000,  yoy_recent=5,  yoy_prev=10)},
    }

    # ── 資金流向：真實 FinMind 資料 ───────────────────────────
    log.info("抓取 FinMind 三大法人資料...")
    all_stock_ids = {
        code: [s["symbol"] for s in info["stocks"]]
        for code, info in industries.items()
    }
    industry_institutional = fetch_industry_institutional(
        stock_ids=all_stock_ids,
        days=15,
    )

    # ── 第一層：產業評分 ────────────────────────────────────
    ranked = score_industries(
        industry_histories, benchmark_history,
        correlation_quotes, 0.7,
        news_articles,
        industry_institutional,
        industry_revenues,
        period, weights,
    )
    top_industries = ranked[:top_n]

    # ── 第二、三層：個股篩選 + 回測 ────────────────────────
    np.random.seed(42)
    stock_dates = pd.date_range("2022-01-01", periods=600, freq="B")

    def sim_stock(trend, vol=0.012, start=100.0):
        r = np.random.randn(600) * vol + trend
        return pd.Series(start * (1 + r).cumprod(), index=stock_dates)

    stock_results = {}
    for ind in top_industries:
        code = ind["code"]
        ind_stocks = industries.get(code, {}).get("stocks", [])

        price_histories = {
            s["symbol"]: sim_stock(0.0005) for s in ind_stocks
        }
        candidates = [
            {"symbol": s["symbol"], "name": s["name"], "momentum_score": 70.0}
            for s in ind_stocks
        ]

        passed = screen_stocks(candidates, price_histories, period, top_n=top_stk)
        stock_results[code] = passed
        log.info(f"  {ind_names.get(code, code)}：通過 {len(passed)} 檔")

    # ── Console 輸出 ────────────────────────────────────────
    period_label = {"1m": "1 個月", "3m": "3 個月", "1y": "1 年"}[period]
    print(f"\n{'='*46}")
    print(f"  每週選股報告｜目標週期：{period_label}")
    print(f"{'='*46}")
    print(f"\n  {'排名':<4} {'產業':<12} {'綜合分':>6}  {'資金':>5} {'情緒':>5} {'強度':>5} {'連動':>5} {'基本面':>6}")
    print(f"  {'-'*60}")

    for i, ind in enumerate(top_industries, 1):
        code = ind["code"]
        bd   = ind["breakdown"]
        print(
            f"  {i:<4} {ind_names.get(code,code):<12} {ind['score']:>6.1f}  "
            f"{bd['capital_flow']:>5.0f} "
            f"{bd['news_sentiment']:>5.0f} "
            f"{bd['relative_strength']:>5.0f} "
            f"{bd['us_correlation']:>5.0f} "
            f"{bd['fundamentals']:>6.0f}"
        )

    for code, stocks in stock_results.items():
        print(f"\n  📌 {ind_names.get(code, code)}")
        if not stocks:
            print("     無符合條件個股")
        for s in stocks:
            bt = s["backtest"]
            print(f"     ✅ {s['name']}（{s['symbol']}）勝率={bt['win_rate']:.0%} 均報={bt['avg_return']:+.1%}")

    # ── 寄送 Email ──────────────────────────────────────────
    try:
        recipients = settings.get("recipients", [os.environ["REPORT_TO_EMAIL"]])
        html = build_html_report(period, ranked, stock_results, ind_names)
        subject = f"📊 每週選股報告｜{date.today().strftime('%Y-%m-%d')}｜{period_label}"
        for addr in recipients:
            send_email(subject, html, to_addr=addr)
            print(f"\n  ✅ Email 已寄出至 {addr}")
    except Exception as e:
        log.error(f"Email 寄送失敗: {e}")
        print(f"\n  ❌ Email 寄送失敗: {e}")

    log.info("=== 每週選股完成 ===")
    return top_industries, stock_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    period = os.getenv("REPORT_PERIOD", "3m")
    run(period)
