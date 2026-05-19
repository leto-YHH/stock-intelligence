"""
Telegram Bot 通知器
需要環境變數：
  TELEGRAM_BOT_TOKEN → BotFather 給的 token
  TELEGRAM_CHAT_ID   → 你的 chat_id
"""

import os
import requests


def send_telegram(markdown_text: str):
    token   = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    if len(markdown_text) > 4000:
        markdown_text = markdown_text[:3997] + "\\.\\.\\."
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id":    chat_id,
            "text":       markdown_text,
            "parse_mode": "MarkdownV2",
        },
        timeout=10,
    ).raise_for_status()