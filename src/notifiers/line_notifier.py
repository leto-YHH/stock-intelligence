"""
LINE Messaging API 通知器
需要環境變數：
  LINE_CHANNEL_TOKEN  → Channel access token
  LINE_USER_ID        → 接收訊息的使用者 ID
"""
import os
import requests

def send_line(message: str):
    token   = os.environ["LINE_CHANNEL_TOKEN"]
    user_id = os.environ["LINE_USER_ID"]

    if len(message) > 5000:
        message = message[:4997] + "..."

    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
