# SonaSNS — 三品牌社媒內容管理系統

管理 OKIBLUES、OKIPLAYGROUND、The Blues 的內容排程、帖文預覽與媒體。

## 📁 資料夾結構

```
SonaSNS/
├── README.md                  ← 本文件
├── index.html                 ← GitHub Pages 首頁（每日預覽）
├── schedules/
│   ├── 2026-06.md            ← 6月排程表
│   ├── 2026-07.md            ← 7月排程表
│   └── ...
├── media/
│   └── [媒體文件連結]
└── assets/
    └── style.css             ← 樣式表
```

## 🚀 工作流程

### 1️⃣ 查看每日預覽
打開 **[GitHub Pages](https://sssunwl.github.io/SonaSNS/)** → 看當月排程 + 每日帖文預覽

### 2️⃣ 上傳媒體
將媒體文件上傳到 **Google Drive**：
```
/OkiMac/SonaSNS_Media/
├── 2026-06-14_OB_Serena.mp4
├── 2026-06-16_OB_Noah.mp4
└── ...
```

### 3️⃣ 編輯帖文
在 **[Google Sheet](https://docs.google.com/spreadsheets/d/1gTbG5il6CtomkTfRXmFXwx7_4AIG8CjOnfsdoRynuS4)** 編輯：
- 帖文文案
- Hashtags
- 發佈狀態
- Post URL

### 4️⃣ 更新預覽
我每日同步 Google Sheet → GitHub Pages 預覽

### 🌦️ OKIPLAYGROUND 每週天氣速報

每週二 **01:58 JST**，GitHub Actions 會在雲端以 Open-Meteo 的沖繩市預報，自動產生與既有範本一致的「週三到週二」7 日 PNG 圖與繁中帖文，並更新 GitHub Pages：

**[下載最新天氣圖與帖文](https://sssunwl.github.io/SonaSNS/weather/)**

此流程不使用 ChatGPT／Claude API，也不需要本機電腦開著。若天氣 API 暫時無法回應，工作流程會失敗而不覆蓋上一次成功版本，可在 GitHub Actions 的執行紀錄重新執行。

## 📋 Google Sheet 欄位說明

| 欄位 | 說明 |
|------|------|
| 日期 | 發佈日期 |
| 星期 | 週幾 |
| 平台 | OB / OKIP / The Blues |
| 車款/主題 | 具體內容 |
| 帖文類型 | YT / FB帖文 / 規格帖 / 天氣速報 / ... |
| IG/FB文案 | 正文內容 |
| Threads文案 | Threads 專用版本（可選） |
| 媒體路徑 | Google Drive 或本地路徑 |
| YouTube連結 | YT 影片連結 |
| Hashtags | 標籤（最多5個） |
| 發佈狀態 | 待起稿 / 待確認 / 已確認 / 已發佈 |
| Post URL | 發佈後的貼文連結 |
| 備註 | 其他說明 |

## 📖 快速開始

1. **查看預覽**：[SonaSNS GitHub Pages](https://sssunwl.github.io/SonaSNS/)
2. **編輯內容**：[Google Sheet](https://docs.google.com/spreadsheets/d/1gTbG5il6CtomkTfRXmFXwx7_4AIG8CjOnfsdoRynuS4)
3. **上傳媒體**：Google Drive `/OkiMac/SonaSNS_Media/`

---

**管理員**：Claude + SS  
**更新頻率**：每日 / 每週  
**最後更新**：2026-06-18
