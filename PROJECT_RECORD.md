# Stock Intelligence System — 專案記錄

**日期：** 2026-06-02  
**GitHub：** https://github.com/leto-YHH/stock-intelligence  
**本地路徑：** `C:\Users\PC\Desktop\專案\stock_bot\stock-intelligence-v4\stock-intelligence`

---

## 一、專案目標

建立一個自動化財金資訊系統，包含兩個核心功能：

1. **每日 Dashboard**（每天台灣時間下午 2:10，週一至週五）
   - 四大股市大盤（台股、美股、日股、港股）
   - AI 財經新聞摘要（Claude 分析）
   - 市場情緒指標
   - 美國連動指數（費城半導體、BDI 等）
   - 今日財經新聞列表

2. **每週選股推薦**（每週一早上 8:00）
   - 依目標持股週期（1個月 / 3個月 / 1年）
   - 篩選 3–5 大潛力產業
   - 在產業內找出推薦個股

---

## 二、系統架構

### 選股邏輯（三層）

**第一層：產業評分（五個維度）**

| 維度 | 1個月權重 | 3個月權重 | 1年權重 | 資料來源 |
|---|---|---|---|---|
| 資金流向（外資/投信買超）| 35% | 20% | 10% | FinMind API（真實） |
| 新聞情緒（AI分析）| 30% | 15% | 5% | RSS + Claude API（真實） |
| 相對強度（vs 大盤）| 20% | 30% | 20% | yfinance（真實） |
| 美國連動指數 | 15% | 20% | 15% | yfinance（真實） |
| 基本面趨勢（月營收YoY）| 0% | 15% | 50% | FinMind API（真實） |

**第二層：個股篩選**
- 硬條件過濾（流動性、財務健康、市值）
- 動能評分（價格動能、籌碼、營收）
- 週期適配回測（滾動 N 天歷史勝率）

**第三層：回測門檻**
- 1個月：勝率 ≥ 55%，均報 ≥ 3%
- 3個月：勝率 ≥ 55%，均報 ≥ 6%
- 1年：勝率 ≥ 60%，均報 ≥ 12%

---

## 三、已完成的程式模組

### 評分器（scorers/）
- `relative_strength.py` — 相對強度（4週60% + 12週40%）✅ 真實資料
- `news_sentiment.py` — Claude API 新聞情緒分析 ✅ 真實資料
- `us_correlation.py` — 美國連動指數超額報酬 ✅ 真實資料
- `capital_flow.py` — 外資/投信買超（含連續買超獎勵）✅ 真實資料
- `fundamentals.py` — 月營收YoY加速/減速 ✅ 真實資料

### 資料抓取（fetchers/）
- `us_stock.py` — 美股大盤 + 八個產業連動指數（yfinance）✅
- `tw_stock.py` — 台股大盤 + 個股歷史價格（yfinance）✅
- `news.py` — RSS 新聞抓取（經濟日報等）+ 產業標記 ✅
- `finmind.py` — FinMind API 三大法人資料 + 月營收 ✅

### 通知器（notifiers/）
- `email_notifier.py` — Gmail SMTP ✅ 支援多收件人
- `line_notifier.py` — LINE Messaging API ✅（已從 LINE Notify 升級）
- `telegram_notifier.py` — 停用

### 主流程
- `dashboard/runner.py` — 每日 Dashboard 主程式 ✅
- `weekly_report/runner.py` — 每週選股主程式（五維度整合）✅
- `weekly_report/backtest.py` — 個股回測模組 ✅

### 設定檔
- `config/industries.json` — 8個產業 + 個股清單 + 連動指數
- `config/settings.json` — 評分權重、篩選門檻、回測參數、收件人清單

---

## 四、GitHub Actions 排程

| Workflow | 執行時間（台灣）| 說明 |
|---|---|---|
| `daily_dashboard.yml` | 週一至週五 14:10 | 每日報告 |
| `weekly_report.yml` | 每週一 08:00 | 週選股 |

---

## 五、已設定的 GitHub Secrets

| Secret | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude AI 新聞摘要 |
| `GMAIL_USER` | Gmail 帳號 |
| `GMAIL_APP_PASS` | Gmail 應用程式密碼 |
| `REPORT_TO_EMAIL` | 收件人信箱（備用）|
| `FINMIND_TOKEN` | FinMind API token |
| `LINE_CHANNEL_TOKEN` | LINE Messaging API token |
| `LINE_USER_ID` | LINE 接收用戶 ID |
| `TELEGRAM_BOT_TOKEN` | 停用 |
| `TELEGRAM_CHAT_ID` | 停用 |

---

## 六、系統運作狀態（2026-06-02）

| 功能 | 狀態 | 備註 |
|---|---|---|
| 台股大盤 | ✅ 正常 | |
| 美股大盤 | ✅ 正常 | |
| 美國連動指數 | ✅ 正常 | |
| 財經新聞 | ✅ 正常 | 目前只有經濟日報，其他RSS被擋 |
| AI 新聞摘要 | ✅ 正常 | Claude claude-sonnet-4-6 |
| Email 發送 | ✅ 正常 | 支援多收件人（settings.json） |
| LINE 發送 | ✅ 正常 | LINE Messaging API |
| Telegram 發送 | ❌ 停用 | 改用 LINE |
| 每週選股 | ✅ 正常 | 五維度全真實資料 |
| 資金流向（FinMind）| ✅ 正常 | 三大法人真實資料 |
| 基本面（月營收）| ✅ 正常 | FinMind 真實資料 |
| 相對強度 | ✅ 正常 | yfinance 真實資料 |

---

## 七、待完成事項

### 短期
1. 新聞來源擴充 — 鉅亨網等 RSS 在 GitHub Actions 被擋，需要替代方案
2. 清理診斷用 print 訊息（finmind.py、backtest.py）

### 中期
3. B+C 短期選股邏輯 — 中小型股（市值篩選）+ Beta > 1.0 篩選
4. 個人持股追蹤 — 輸入持股，系統判斷是否該出售

### 長期
5. Web Dashboard UI — 網頁版即時看板

---

## 八、常用指令

```bash
# 進到正確的專案資料夾
cd C:\Users\PC\Desktop\專案\stock_bot\stock-intelligence-v4\stock-intelligence

# 推上 GitHub
git add .
git commit -m "說明改了什麼"
git push

# 如果 GitHub 上有新的 commit 需要先同步
git pull
```

---

## 九、關鍵技術決策記錄

1. **模型名稱**：Claude API 使用 `claude-sonnet-4-6`
2. **漲跌顏色**：台灣慣例，漲紅跌綠（`#e03c3c` / `#16a34a`）
3. **回測方式**：滾動視窗（非全期固定值），避免過擬合
4. **產業評分**：每個維度 0-100 分，依週期加權合併
5. **新聞情緒**：負面新聞權重 × 1.2（損失趨避效應）
6. **基本面**：台股每月 10 號強制公告月營收，FinMind API 抓取
7. **LINE 通知**：使用 LINE Messaging API（LINE Notify 已於 2024 年關閉）
8. **多收件人**：收件人清單存在 `config/settings.json` 的 `recipients` 欄位
9. **FinMind 月營收欄位**：`revenue_year`、`revenue_month`（非 `year`、`month`）
10. **yfinance NaN 處理**：回測時需過濾 NaN 值，否則均報會變成 nan 導致所有個股被過濾
