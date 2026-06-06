"""
JSON 資料匯出器
將每日 Dashboard 結果整理成前端可讀取的 JSON 格式
"""
import json
import os
from datetime import date
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "public_data"


def ensure_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def export_dashboard(
    indices: list[dict],
    news: list[dict],
    impacts: list[dict],
    sentiment: str,
    summary: str,
    daily_summary: str,
):
    """
    匯出每日 Dashboard JSON

    Args:
        indices: 六大指數資料
        news: 今日新聞列表
        impacts: 台股影響分析
        sentiment: 市場情緒（例：▲ 偏多　+72）
        summary: 市場摘要文字
        daily_summary: 本日操作重點
    """
    ensure_output_dir()

    data = {
        "date": date.today().strftime("%Y-%m-%d"),
        "sentiment": sentiment,
        "summary": summary,
        "indices": indices,
        "news": news,
        "impacts": impacts,
        "dailySummary": daily_summary,
    }

    output_path = OUTPUT_DIR / "dashboard.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[Export] dashboard.json 已匯出至 {output_path}")
    return output_path


def export_weekly(weekly_data: dict):
    """
    匯出每週選股 JSON

    Args:
        weekly_data: { '1m': [...], '3m': [...], '1y': [...] }
    """
    ensure_output_dir()

    data = {
        "updatedAt": date.today().strftime("%Y-%m-%d"),
        "periods": weekly_data,
    }

    output_path = OUTPUT_DIR / "weekly.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[Export] weekly.json 已匯出至 {output_path}")
    return output_path


def export_institution(buy: list[dict], sell: list[dict]):
    """
    匯出三大法人共識 JSON

    Args:
        buy:  三大法人同時買超的個股清單
        sell: 三大法人同時賣超的個股清單
    """
    ensure_output_dir()

    data = {
        "updatedAt": date.today().strftime("%Y-%m-%d"),
        "buy": buy,
        "sell": sell,
    }

    output_path = OUTPUT_DIR / "institution.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[Export] institution.json 已匯出至 {output_path}")
    return output_path