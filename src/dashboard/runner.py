"""
每日 Dashboard 主流程
執行時間：台灣時間每天下午 2:10（台股收盤後）
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger(__name__)
TZ_TW = timezone(timedelta(hours=8))
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def _load_settings() -> dict:
    return json.loads((CONFIG_DIR / "settings.json").read_text())


def _fetch_market_data() -> dict:
    try:
        from src.fetchers.us_stock import fetch_us_indices, fetch_us_correlations
        from src.fetchers.tw_stock import fetch_taiex
        return {
            "taiex":      fetch_taiex(),
            "us_indices": fetch_us_indices(),
            "us_corr":    fetch_us_correlations(),
        }
    except Exception as e:
        log.warning(f"市場資料抓取失敗，使用模擬資料: {e}")
        return _mock_market_data()


def _fetch_news() -> list:
    try:
        from src.fetchers.news import fetch_finance_news
        return fetch_finance_news()
    except Exception as e:
        log.warning(f"新聞抓取失敗: {e}")
        return []


def _summarize_news_with_claude(articles: list, market: dict = None) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        titles = "\n".join(f"- {a['title']}" for a in articles[:15])

        market_context = ""
        if market:
            taiex = market.get("taiex", {})
            tw_pct = taiex.get("pct", 0) or 0
            market_context = f"""
今日大盤表現：
- 台股加權指數：{taiex.get('price', 'N/A'):,.0f} 點，{'+' if tw_pct >= 0 else ''}{tw_pct:.2f}%
"""
            for q in market.get("us_indices", []):
                pct = q.get("pct", 0) or 0
                market_context += f"- {q['name']}：{'+' if pct >= 0 else ''}{pct:.2f}%\n"

        prompt = f"""你是一位專業的台股市場分析師，請根據以下資訊產生今日市場報告。

{market_context}
今日財經新聞：
{titles}

請完成以下五件事：

1. **市場摘要**（300字左右）：
   - 說明今日市場整體狀況與主要漲跌原因
   - 點出今日最強與最弱的族群
   - 繁體中文，專業但易讀

2. **深度分析**（500字左右）：
   - 深入分析今日大盤走勢成因，引用具體指數數據
   - 詳細分析受影響的產業族群與個股動向，至少提及3-4個族群
   - 從總體經濟角度解讀（Fed政策、匯率、資金流向、外資動態、美債殖利率）
   - 技術面分析（關鍵支撐壓力、均線、成交量）
   - 點出明日或本週需要關注的關鍵指標或事件
   - 使用專業財經術語
   - 繁體中文

3. **市場情緒**：根據大盤漲跌幅度與新聞綜合判斷
   - positive（明顯偏多）、neutral（盤整觀望）、negative（明顯偏空）
   - 大盤跌超過 2% 應傾向 negative，漲超過 1% 應傾向 positive

4. **情緒分數**：-100 到 +100 的整數
   - 大盤漲跌是主要依據（跌 3% 約 -60 分，漲 1% 約 +30 分）
   - 新聞情緒作為微調（±20 分以內）

5. **台股影響分析**：針對今日3-5則重要新聞，分析對台股的影響
   - topic: 新聞主題（10字以內）
   - dir: pos（正面）/ neg（負面）/ warn（警示）/ neutral（中性）
   - dirText: 方向說明（如「強烈正面」、「中線正面」、「新興市場警訊」、「個股中性」）
   - impact: 對台股具體影響（20字以內，如「AI伺服器族群受惠」、「半導體設備需求延續」）

請只回傳 JSON，格式：
{{"summary": "...", "dailySummary": "...", "sentiment": "positive/neutral/negative", "score": 數字, "impacts": [{{"topic": "...", "dir": "pos/neg/warn/neutral", "dirText": "...", "impact": "..."}}]}}"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        log.warning(f"Claude 摘要失敗: {e}")
        return {"summary": "今日新聞摘要暫時無法產生。", "dailySummary": "今日深度分析暫時無法產生。", "sentiment": "neutral", "score": 0, "impacts": []}


def _build_html(date_str: str, market: dict, news: list, ai_summary: dict) -> str:
    def arrow(pct): return "–" if pct is None else ("▲" if pct >= 0 else "▼")
    def color(pct): return "#888" if pct is None else ("#e03c3c" if pct >= 0 else "#16a34a")
    def fmt(v, d=2): return "N/A" if v is None else f"{v:,.{d}f}"

    taiex = market["taiex"]
    us    = market["us_indices"]

    tw_row = f"""
    <tr>
      <td><b>{taiex['name']}</b></td>
      <td style="text-align:right">{fmt(taiex['price'])}</td>
      <td style="text-align:right;color:{color(taiex['pct'])}">
        {arrow(taiex['pct'])} {fmt(abs(taiex['pct'] or 0))}%
      </td>
    </tr>"""

    us_rows = "".join(f"""
    <tr>
      <td>{q['name']}</td>
      <td style="text-align:right">{fmt(q['price'])}</td>
      <td style="text-align:right;color:{color(q['pct'])}">
        {arrow(q['pct'])} {fmt(abs(q['pct'] or 0))}%
      </td>
    </tr>""" for q in us)

    corr_rows = "".join(f"""
    <tr>
      <td>{q['name']}</td>
      <td style="text-align:right">{fmt(q['price'])}</td>
      <td style="text-align:right;color:{color(q['pct'])}">
        {arrow(q['pct'])} {fmt(abs(q['pct'] or 0))}%
      </td>
    </tr>""" for q in market["us_corr"].values())

    sent    = ai_summary.get("sentiment", "neutral")
    score   = ai_summary.get("score", 0)
    sent_color = {"positive":"#16a34a","neutral":"#888","negative":"#e03c3c"}.get(sent,"#888")
    sent_label = {"positive":"偏多","neutral":"中性","negative":"偏空"}.get(sent,"中性")

    news_items = "".join(
        f'<li style="margin:6px 0"><a href="{n["url"]}" style="color:#2563eb">{n["title"]}</a>'
        f'<span style="color:#888;font-size:12px"> — {n["source"]}</span></li>'
        for n in news[:10]
    )

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日財金 Dashboard {date_str}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f8f9fa;color:#222;margin:0;padding:0}}
  .wrap{{max-width:660px;margin:0 auto;padding:20px}}
  .header{{background:#1e293b;color:#fff;border-radius:12px;padding:24px 28px;margin-bottom:16px}}
  .header h1{{margin:0;font-size:22px;font-weight:600}}
  .header .sub{{margin:4px 0 0;font-size:13px;opacity:.65}}
  .card{{background:#fff;border-radius:10px;padding:18px 22px;
         margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
  .card h2{{margin:0 0 12px;font-size:15px;font-weight:600;color:#1e293b}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th{{text-align:left;color:#64748b;font-weight:500;padding:5px 0;border-bottom:1px solid #e2e8f0}}
  td{{padding:7px 0;border-bottom:1px solid #f1f5f9}}
  .sentiment{{display:inline-block;padding:4px 12px;border-radius:20px;font-weight:600;font-size:13px}}
  .summary{{font-size:14px;line-height:1.8;color:#334155;background:#f8fafc;border-radius:8px;padding:14px}}
  ul{{margin:0;padding-left:18px}}
  .footer{{text-align:center;font-size:12px;color:#94a3b8;margin-top:20px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>📊 每日財金 Dashboard</h1>
    <div class="sub">{date_str}　台股收盤後摘要</div>
  </div>
  <div class="card">
    <h2>🌐 今日市場情緒</h2>
    <div style="margin-bottom:10px">
      <span class="sentiment" style="background:{sent_color}22;color:{sent_color}">
        {sent_label}　{score:+d}
      </span>
    </div>
    <div class="summary">{ai_summary.get('summary','')}</div>
  </div>
  <div class="card">
    <h2>🇹🇼 台股大盤</h2>
    <table>
      <tr><th>指數</th><th style="text-align:right">點位</th><th style="text-align:right">漲跌</th></tr>
      {tw_row}
    </table>
  </div>
  <div class="card">
    <h2>🇺🇸 美股大盤</h2>
    <table>
      <tr><th>指數</th><th style="text-align:right">點位</th><th style="text-align:right">漲跌</th></tr>
      {us_rows}
    </table>
  </div>
  <div class="card">
    <h2>🔗 美國連動指數</h2>
    <table>
      <tr><th>指數</th><th style="text-align:right">點位</th><th style="text-align:right">漲跌</th></tr>
      {corr_rows}
    </table>
  </div>
  <div class="card">
    <h2>📰 今日財經新聞</h2>
    <ul>{news_items}</ul>
  </div>
  <div class="card">
    <h2>📋 今日市場深度分析</h2>
    <div class="summary">{ai_summary.get('dailySummary','')}</div>
  </div>
  <div class="footer">由 GitHub Actions 自動產生 · Stock Intelligence System</div>
</div>
</body>
</html>"""


def _build_text(date_str: str, market: dict, ai_summary: dict) -> str:
    def arrow(pct): return "▲" if (pct or 0) >= 0 else "▼"
    def fmt(v): return f"{v:,.2f}" if v else "N/A"

    taiex      = market["taiex"]
    sent_label = {"positive":"偏多","neutral":"中性","negative":"偏空"}.get(
        ai_summary.get("sentiment","neutral"), "中性")

    lines = [
        f"📊 每日財金 Dashboard {date_str}",
        "─" * 30,
        f"市場情緒：{sent_label}（{ai_summary.get('score',0):+d}）",
        "",
        ai_summary.get("summary", ""),
        "",
        f"🇹🇼 加權指數：{fmt(taiex['price'])}　{arrow(taiex['pct'])}{abs(taiex['pct'] or 0):.2f}%",
    ]
    for q in market["us_indices"]:
        lines.append(f"🇺🇸 {q['name']}：{fmt(q['price'])}　{arrow(q['pct'])}{abs(q['pct'] or 0):.2f}%")
    lines.append("\n🔗 連動指數")
    for q in market["us_corr"].values():
        lines.append(f"  {q['name']}：{arrow(q['pct'])}{abs(q['pct'] or 0):.2f}%")
    return "\n".join(lines)


def _mock_market_data() -> dict:
    return {
        "taiex": {"symbol":"TAIEX","name":"加權指數","price":21850.3,"change":156.2,"pct":0.72,"ok":True},
        "us_indices": [
            {"symbol":"^GSPC","name":"S&P 500", "price":5432.1,"change":18.3, "pct":0.34,"ok":True},
            {"symbol":"^IXIC","name":"Nasdaq",  "price":17215.4,"change":82.1, "pct":0.48,"ok":True},
            {"symbol":"^DJI", "name":"道瓊工業","price":39854.2,"change":-45.2,"pct":-0.11,"ok":True},
            {"symbol":"^VIX", "name":"VIX",     "price":14.2,  "change":-0.8, "pct":-5.33,"ok":True},
        ],
        "us_corr": {
            "SEMI":{"name":"費城半導體","price":5123.4,"pct":1.25,"industry_code":"SEMI"},
            "TECH":{"name":"Nasdaq 100","price":19234.5,"pct":0.48,"industry_code":"TECH"},
            "FIN": {"name":"KBW 銀行",  "price":118.3,  "pct":-0.22,"industry_code":"FIN"},
            "SHIP":{"name":"BDI ETF",   "price":8.45,   "pct":-1.05,"industry_code":"SHIP"},
        },
    }


def run():
    log.info("=== 每日 Dashboard 開始 ===")
    today = datetime.now(TZ_TW).strftime("%Y-%m-%d")

    market     = _fetch_market_data()
    news       = _fetch_news()
    ai_summary = _summarize_news_with_claude(news, market)

    # 抓取持股資料
    try:
        from src.fetchers.portfolio import fetch_portfolio, build_portfolio_data
        holdings = fetch_portfolio()
        portfolio_data = build_portfolio_data(holdings, news)
        log.info(f"持股資料：共 {len(portfolio_data)} 檔")
    except Exception as e:
        log.warning(f"持股資料抓取失敗: {e}")
        portfolio_data = []

    html       = _build_html(today, market, news, ai_summary)
    text       = _build_text(today, market, ai_summary)

    subject = f"📊 每日財金 Dashboard {today}"
    errors  = []

    if os.getenv("GMAIL_USER"):
        try:
            from src.notifiers.email_notifier import send_email
            settings = _load_settings()
            recipients = settings.get("recipients", [os.environ["REPORT_TO_EMAIL"]])
            for addr in recipients:
                send_email(subject, html, to_addr=addr)
                log.info(f"✅ Email 發送成功至 {addr}")
        except Exception as e:
            log.error(f"❌ Email 失敗: {e}")
            errors.append(str(e))

    if os.getenv("LINE_CHANNEL_TOKEN"):
        try:
            from src.notifiers.line_notifier import send_line
            send_line(text)
            log.info("✅ LINE 發送成功")
        except Exception as e:
            log.error(f"❌ LINE 失敗: {e}")
            errors.append(str(e))

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            from src.notifiers.telegram_notifier import send_telegram
            send_telegram(text.replace("-","\\-").replace(".","\\-").replace("+","\\+"))
            log.info("✅ Telegram 發送成功")
        except Exception as e:
            log.error(f"❌ Telegram 失敗: {e}")
            errors.append(str(e))

    # ── 匯出 JSON 給前端 ──────────────────────────────────
    try:
        from src.exporters.json_exporter import export_dashboard

        taiex = market["taiex"]
        indices_json = [
            {
                "label": "台股加權",
                "value": f"{taiex['price']:,.0f}",
                "chg": f"{'▲' if (taiex['pct'] or 0) >= 0 else '▼'} {abs(taiex['change'] or 0):,.0f} pts　{(taiex['pct'] or 0):+.2f}%",
                "vol": "見台股官網",
                "dir": "up" if (taiex['pct'] or 0) >= 0 else "down",
            }
        ]
        for q in market["us_indices"]:
            indices_json.append({
                "label": q["name"],
                "value": f"{q['price']:,.0f}",
                "chg": f"{'▲' if (q['pct'] or 0) >= 0 else '▼'} {abs(q['change'] or 0):,.0f} pts　{(q['pct'] or 0):+.2f}%",
                "vol": "",
                "dir": "up" if (q['pct'] or 0) >= 0 else "down",
            })

        news_json = [
            {"title": n["title"], "summary": n.get("summary", ""), "source": n.get("source", ""), "url": n.get("url", "#")}
            for n in news[:8]
        ]

        sent = ai_summary.get("sentiment", "neutral")
        score = ai_summary.get("score", 0)
        sent_label = {"positive": "偏多", "neutral": "中性", "negative": "偏空"}.get(sent, "中性")
        arrow = "▲" if score >= 0 else "▼"
        sentiment_str = f"{arrow} {sent_label}　{score:+d}"

        export_dashboard(
            indices=indices_json,
            news=news_json,
            impacts=ai_summary.get("impacts", []),
            sentiment=sentiment_str,
            summary=ai_summary.get("summary", ""),
            daily_summary=ai_summary.get("dailySummary", ai_summary.get("summary", "")),
            portfolio=portfolio_data,
        )
        log.info("✅ dashboard.json 匯出成功")
    except Exception as e:
        log.error(f"❌ JSON 匯出失敗: {e}")

    # ── 匯出 institution.json ──────────────────────────────
    try:
        from src.fetchers.institution_fetcher import fetch_institution_consensus
        from src.exporters.json_exporter import export_institution
        consensus = fetch_institution_consensus()
        export_institution(buy=consensus["buy"], sell=consensus["sell"])
        log.info("✅ institution.json 匯出成功")
    except Exception as e:
        log.error(f"❌ institution.json 匯出失敗: {e}")
  
    log.info("=== 每日 Dashboard 完成 ===")
    return {"html": html, "text": text, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run()
    print("\n── 文字版預覽 ──")
    print(result["text"])