"""
新聞情緒評分器
用 Claude API 對每則新聞做情緒分析，
再依產業關鍵字分配分數，輸出各產業 0–100 情緒分數
"""

import os
import json
import logging
from collections import defaultdict

log = logging.getLogger(__name__)

DECAY_WEIGHTS = [1.0, 0.85, 0.70, 0.55, 0.40]  # 最新一天最重


def _score_with_claude(articles: list) -> list:
    """
    呼叫 Claude API 對新聞批次做情緒分析
    回傳：[{"title": ..., "score": -1.0~1.0, "reason": ...}, ...]
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        titles = "\n".join(
            f"{i+1}. {a['title']}" for i, a in enumerate(articles)
        )
        prompt = f"""以下是台灣財經新聞標題，請對每則新聞做情緒分析。

新聞列表：
{titles}

請回傳 JSON 陣列，每個元素包含：
- index: 新聞編號（從1開始）
- score: 情緒分數，範圍 -1.0（極度負面）到 +1.0（極度正面），0 為中性
- reason: 一句話說明判斷原因（繁體中文）

只回傳 JSON，不要其他文字。格式：
[{{"index": 1, "score": 0.8, "reason": "..."}}, ...]"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        print(f"[Claude] 回應內容: {resp.content}") 
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        results = json.loads(text.strip())

        scored = []
        for item in results:
            idx = item["index"] - 1
            if 0 <= idx < len(articles):
                scored.append({
                    **articles[idx],
                    "sentiment_score":  float(item["score"]),
                    "sentiment_reason": item.get("reason", ""),
                })
        return scored

    except Exception as e:
        log.warning(f"Claude API 情緒分析失敗，使用中性分數: {e}")
        return [{**a, "sentiment_score": 0.0, "sentiment_reason": "API 不可用"} for a in articles]


def calc_news_sentiment(articles: list) -> dict[str, float]:
    """
    計算各產業新聞情緒分數（0–100）

    Args:
        articles: fetch_finance_news() 的輸出
                  每篇需有 "industries" 欄位（產業代碼列表）

    Returns:
        { 'SEMI': 72.5, 'FIN': 45.0, ... }
    """
    if not articles:
        return {}

    # 用 Claude API 打情緒分數
    scored = _score_with_claude(articles)

    # 依產業累積加權分數
    industry_scores = defaultdict(list)
    for article in scored:
        s = article.get("sentiment_score", 0.0)
        # 負面新聞權重 * 1.2（損失趨避效應）
        weighted = s * 1.2 if s < 0 else s
        for code in article.get("industries", []):
            industry_scores[code].append(weighted)

    if not industry_scores:
        return {}

    # 平均後轉換為 0–100
    # -1.2 → 0, 0 → 50, +1.0 → 100
    result = {}
    for code, scores in industry_scores.items():
        avg = sum(scores) / len(scores)
        normalized = (avg + 1.2) / 2.2 * 100
        result[code] = round(max(0, min(100, normalized)), 1)

    return result


# ── 測試（不呼叫 API，直接模擬）─────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    mock_articles = [
        {"title": "台積電 CoWoS 產能大幅擴充，法人看好",
         "industries": ["SEMI"], "sentiment_score": 0.85},
        {"title": "Fed 暗示年底前降息，金融股全面上漲",
         "industries": ["FIN"], "sentiment_score": 0.70},
        {"title": "BDI 指數連續下跌，航運股承壓",
         "industries": ["SHIP"], "sentiment_score": -0.60},
        {"title": "聯發科下季展望保守，AI 晶片競爭加劇",
         "industries": ["SEMI", "TECH"], "sentiment_score": -0.30},
        {"title": "AI 伺服器需求爆發，廣達訂單滿載",
         "industries": ["TECH"], "sentiment_score": 0.90},
    ]

    # 跳過 API，直接用 mock 分數算
    industry_scores = defaultdict(list)
    for a in mock_articles:
        s = a["sentiment_score"]
        weighted = s * 1.2 if s < 0 else s
        for code in a["industries"]:
            industry_scores[code].append(weighted)

    print("\n=== 新聞情緒評分結果 ===")
    for code, scores in sorted(industry_scores.items()):
        avg = sum(scores) / len(scores)
        normalized = round((avg + 1.2) / 2.2 * 100, 1)
        bar = "█" * int(normalized / 5)
        print(f"  {code:6} {normalized:5.1f}  {bar}")
