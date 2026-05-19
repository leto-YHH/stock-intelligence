"""
Email 通知器（Gmail SMTP）
需要環境變數：
  GMAIL_USER      → 你的 Gmail 帳號
  GMAIL_APP_PASS  → Gmail 應用程式密碼
  REPORT_TO_EMAIL → 收件人 Email
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(subject: str, html_body: str, to_addr: str = None):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASS"]
    to_addr    = to_addr or os.environ["REPORT_TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, to_addr, msg.as_string())