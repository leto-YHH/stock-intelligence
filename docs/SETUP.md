# 部署教學

## 前置需求

- GitHub 帳號
- Python 3.11+（本機測試用）
- 至少一種通知管道的帳號（Gmail / LINE / Telegram 擇一即可）
- Anthropic API Key（新聞情緒分析用）

---

## Step 1：建立 GitHub Repository

1. Fork 或 Clone 此專案
2. 在自己的 GitHub 建立新的 **Private** repository（建議設為私人，因為包含個人設定）
3. 將專案推送上去

```bash
git clone https://github.com/原作者/stock-intelligence.git
cd stock-intelligence
git remote set-url origin https://github.com/你的帳號/stock-intelligence.git
git push -u origin main
```

---

## Step 2：設定 GitHub Secrets

前往你的 repository → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

### 必填（通知管道擇一或全填）

**Email 通知（Gmail）**

| Secret 名稱 | 說明 |
|------------|------|
| `GMAIL_USER` | 你的 Gmail 帳號（xxx@gmail.com）|
| `GMAIL_APP_PASS` | Gmail 應用程式密碼（見下方說明）|
| `REPORT_TO_EMAIL` | 收件人 Email |

> Gmail 應用程式密碼申請步驟：
> 1. Google 帳戶 → 安全性 → 開啟兩步驟驗證
> 2. 搜尋「應用程式密碼」→ 選擇「郵件」→ 產生
> 3. 複製 16 位密碼填入 Secret

**LINE Notify**

| Secret 名稱 | 說明 |
|------------|------|
| `LINE_NOTIFY_TOKEN` | 至 https://notify-bot.line.me/ 登入後申請 Token |

**Telegram Bot**

| Secret 名稱 | 說明 |
|------------|------|
| `TELEGRAM_BOT_TOKEN` | 向 @BotFather 申請（指令：/newbot）|
| `TELEGRAM_CHAT_ID` | 向 @userinfobot 查詢你的 ID |

### 必填（系統功能）

| Secret 名稱 | 說明 |
|------------|------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ 申請 |

### 選填（提升資料完整度）

| Secret 名稱 | 說明 |
|------------|------|
| `FINMIND_TOKEN` | https://finmind.github.io/ 免費註冊取得，用於更完整的籌碼資料 |

---

## Step 3：自訂追蹤設定

### 調整個股清單

編輯 `config/industries.json`，加入你想追蹤的個股：

```json
{
  "SEMI": {
    "name": "半導體",
    "stocks": [
      {"symbol": "2330", "name": "台積電"},
      {"symbol": "2454", "name": "聯發科"},
      {"symbol": "2379", "name": "瑞昱"}
    ],
    "us_correlation": "^SOX"
  }
}
```

### 調整系統參數

編輯 `config/settings.json`：

```json
{
  "default_period": "3m",
  "top_industries_count": 5,
  "top_stocks_per_industry": 2,
  "backtest_window_weeks": 52,
  "min_daily_volume_twd": 30000000,
  "daily_report_time": "14:00",
  "weekly_report_day": "monday"
}
```

---

## Step 4：執行時間確認

系統有兩個自動排程：

| Workflow | 執行時間（台灣）| 說明 |
|---------|--------------|------|
| `daily_dashboard.yml` | 週一至週五 14:10 | 台股收盤後發送每日報告 |
| `weekly_report.yml` | 每週一 08:00 | 開盤前發送本週選股建議 |

若要修改時間，編輯對應的 `.github/workflows/*.yml` 檔案中的 `cron` 設定。

---

## Step 5：手動測試

GitHub → Actions → 選擇要測試的 Workflow → `Run workflow` 按鈕

建議測試順序：
1. 先跑 `daily_dashboard.yml` 確認資料抓取和通知都正常
2. 再跑 `weekly_report.yml` 確認選股邏輯正常

---

## 本機開發測試

```bash
# 安裝套件
pip install -r requirements.txt

# 設定環境變數
export ANTHROPIC_API_KEY="your_key"
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASS="your_app_password"
export REPORT_TO_EMAIL="recipient@email.com"

# 測試每日 Dashboard
cd src
python -m dashboard.runner

# 測試每週選股
python -m weekly_report.runner --period 3m
```

---

## 常見問題

**Q：收不到 Email？**
確認 Gmail 已開啟兩步驟驗證，且使用的是應用程式密碼而非登入密碼。

**Q：LINE 沒有收到訊息？**
確認 Token 是從 notify-bot.line.me 申請，且已選擇要推播到哪個聊天室或群組。

**Q：Actions 執行失敗？**
到 GitHub → Actions → 對應的 Run → 查看 log，通常是 Secret 設定問題或套件版本問題。

**Q：想新增一個產業？**
在 `config/industries.json` 加入新的產業和對應個股，系統下次執行時會自動納入評分。
