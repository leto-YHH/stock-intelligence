"""
LINE Notify 通知器
需要環境變數：LINE_NOTIFY_TOKEN
申請：https://notify-bot.line.me/
"""

import os
import requests


def send_line(message: str):
    token = os.environ["LINE_NOTIFY_TOKEN"]
    if len(message) > 1000:
        message = message[:997] + "..."
    requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {token}"},
        data={"message": "\n" + message},
        timeout=10,
    ).raise_for_status()