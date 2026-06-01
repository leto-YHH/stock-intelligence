# Stock Intelligence System

每日財金 Dashboard + 每週智慧選股推薦系統

> 每天早上自動整理大盤、新聞、情緒摘要；每週一自動推薦最具潛力的產業與個股。

---

## 系統概覽

```
輸入資料（每日）
  ├── 四大股市大盤（台 / 美 / 日 / 港）
  ├── 台美財經新聞 → AI 情緒摘要
  └── 美國連動指數（費半 / BDI / KBW 等）
         │
         ▼
  ┌─────────────────────────────┐
  │     每週產業評分模型         │
  │  資金 / 新聞 / 強度 /        │
  │  連動指數 / 基本面           │
  └─────────────┬───────────────┘
                │ 篩選 3–5 大潛力產業
                ▼
  ┌─────────────────────────────┐
  │     個股三層篩選             │
  │  硬條件 → 動能評分 →         │
  │  週期適配回測（滾動 N 天）    │
  └─────────────┬───────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
  每日 Dashboard     每週推薦清單
  大盤 / 新聞摘要    Email / LINE / Telegram
```

---

## 核心功能

### 每日 Dashboard（每天收到）
- 台 / 美 / 日 / 港 四大股市大盤指數
- AI 彙整當日財經新聞摘要（台股 + 美股）
- 市場情緒指標（正面 / 中性 / 負面）
- 美國連動指數狀況（費城半導體、BDI 等）

### 每週選股推薦（每週一收到）
- 依照 **目標持股週期** 推薦不同股票
  - `1 個月`：短線，著重資金動向和新聞情緒
  - `3 個月`：中線，著重相對強度和連動指數
  - `1 年`：長線，著重基本面趨勢
- 推薦流程：潛力產業評分 → 產業內個股篩選 → 週期適配回測
- 每檔推薦股附上：評分理由、建議持有天數（滾動 N 天回測結果）

---

## 產業評分模型

系統每週對台灣所有主要產業計算綜合評分，找出 3–5 個最具潛力的產業。

評分由五個維度組成，依持股週期給予不同權重：

| 維度 | 1 個月 | 3 個月 | 1 年 | 資料來源 |
|------|--------|--------|------|----------|
| 資金流向（外資 / 投信買超）| 35% | 20% | 10% | 台灣證交所、FinMind |
| 新聞情緒（AI 情緒分析）| 30% | 15% | 5% | RSS + Claude API |
| 相對強度（vs 大盤）| 20% | 30% | 20% | yfinance |
| 美國連動指數 | 15% | 20% | 15% | yfinance |
| 基本面趨勢（月營收年增率）| 0% | 15% | 50% | 公開資訊觀測站 |

> 理論依據：動能效應（Momentum Effect）在台股、美股均有實證；機構資金買超行為在 4–8 週內對股價有顯著預測力；月營收年增率加速是長線最可靠的領先訊號。

---

## 個股篩選邏輯

選出潛力產業後，進行三層篩選：

**第一層：硬條件過濾**（不符合直接排除）
- 日均成交額 ≥ 3,000 萬
- 近兩季不虧損
- 負債比 ≤ 60%

**第二層：動能評分**（0–100 分排名）
- 價格動能：近 1 個月、3 個月漲幅相對產業平均
- 籌碼集中度：外資 / 投信近期買超狀況
- 營收動能：月營收年增率加速 or 減速

**第三層：週期適配回測**
- 對每檔個股計算滾動持有 N 天的歷史勝率與平均報酬
- 依使用者選定的週期，只推薦該週期歷史表現佳的股票
- 使用滾動視窗（非全期固定值）避免過擬合

---

## 技術架構

| 元件 | 技術 |
|------|------|
| 排程執行 | GitHub Actions（cron） |
| 程式語言 | Python 3.11 |
| 市場資料 | yfinance、FinMind API |
| 台股基本面 | 公開資訊觀測站、台灣證交所 API |
| 新聞來源 | RSS Feed（鉅亨網、經濟日報）|
| 情緒分析 | Claude API |
| 通知管道 | Email（Gmail）/ LINE Notify / Telegram Bot |

**所有資料來源均為免費，無需付費訂閱。**

---

## 目錄結構

```
stock-intelligence/
├── .github/
│   └── workflows/
│       ├── daily_dashboard.yml     # 每日 Dashboard（每天早上）
│       └── weekly_report.yml       # 每週選股（每週一）
├── src/
│   ├── dashboard/                  # 每日 Dashboard 模組
│   │   ├── market.py               # 四大股市大盤
│   │   ├── news.py                 # 新聞抓取
│   │   └── sentiment.py            # AI 情緒分析
│   ├── weekly_report/              # 每週選股模組
│   │   ├── runner.py               # 主流程
│   │   └── backtest.py             # 滾動 N 天回測
│   ├── scorers/                    # 產業評分五個維度
│   │   ├── capital_flow.py         # 資金流向
│   │   ├── news_sentiment.py       # 新聞情緒
│   │   ├── relative_strength.py    # 相對強度
│   │   ├── us_correlation.py       # 美國連動指數
│   │   └── fundamentals.py         # 基本面趨勢
│   ├── fetchers/                   # 資料抓取層
│   │   ├── tw_stock.py             # 台股資料
│   │   ├── us_stock.py             # 美股資料
│   │   ├── finmind.py              # FinMind API
│   │   └── news.py                 # 新聞 RSS
│   ├── notifiers/                  # 通知發送
│   │   ├── email_notifier.py
│   │   ├── line_notifier.py
│   │   └── telegram_notifier.py
│   └── report.py                   # 報告格式化（HTML / Markdown）
├── config/
│   ├── industries.json             # 產業分類與個股對應
│   ├── us_correlations.json        # 台灣產業 ↔ 美國指數對應表
│   └── settings.json               # 系統參數設定
├── docs/
│   ├── ARCHITECTURE.md             # 系統架構詳細說明
│   ├── SCORING_MODEL.md            # 產業評分模型說明
│   ├── STOCK_SELECTION.md          # 個股篩選邏輯說明
│   └── SETUP.md                    # 完整部署教學
├── requirements.txt
└── README.md
```

---

## 快速開始

### 1. Clone 專案
```bash
git clone https://github.com/你的帳號/stock-intelligence.git
cd stock-intelligence
```

### 2. 安裝套件
```bash
pip install -r requirements.txt
```

### 3. 設定 GitHub Secrets

前往 `Settings → Secrets and variables → Actions`：

| Secret | 說明 | 必填 |
|--------|------|------|
| `GMAIL_USER` | Gmail 帳號 | Email 通知用 |
| `GMAIL_APP_PASS` | Gmail 應用程式密碼 | Email 通知用 |
| `REPORT_TO_EMAIL` | 收件人信箱 | Email 通知用 |
| `LINE_NOTIFY_TOKEN` | LINE Notify Token | LINE 通知用 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | Telegram 用 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | Telegram 用 |
| `ANTHROPIC_API_KEY` | Claude API Key | 新聞情緒分析用 |
| `FINMIND_TOKEN` | FinMind API Token（選填）| 更完整的籌碼資料 |

> 三種通知管道可以同時啟用，也可以只選一種，系統會自動判斷。

### 4. 自訂設定

編輯 `config/settings.json` 調整持股週期偏好與評分權重。

### 5. 手動測試

GitHub → Actions → 選擇 workflow → Run workflow

---

## 開發路線圖

- [x] 系統架構設計
- [x] 產業評分模型設計
- [x] 個股篩選邏輯設計
- [x] 每日 Dashboard 實作
- [x] 產業評分五維度實作
- [x] 個股篩選與回測模組實作
- [x] 每週報告產生與發送
- [ ] 個人持股追蹤（持股建議買賣）
- [ ] Web Dashboard UI

---

## 免責聲明

本系統所有資訊僅供參考，不構成任何投資建議。投資有風險，請自行評估。
