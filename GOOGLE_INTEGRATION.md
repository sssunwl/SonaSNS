# Google 數據串接 — OKIBLUES 客戶數據頁

把 OKIBLUES 的 Google 側數據(YouTube / Maps / 之後 Ads)拉進 `okiblues.html` 客戶數據頁。
架構同 Meta：**腳本 Pull → 靜態寫入 HTML → GitHub Pages 顯示**。金鑰只在 `~/.config/sonasns/`,絕不進 repo(頁面只含數字)。

---

## 目前狀態(2026-07-13)

| 來源 | 層級 | 狀態 | 腳本 | 金鑰 | 需要 billing |
|---|---|---|---|---|---|
| 🔴 YouTube 頻道成效 | 公開 | ✅ 上線 | `sync_youtube.py` | `~/.config/sonasns/youtube.json` | 否 |
| ⭐ Google 商家評價 | 公開 | ✅ 上線 | `sync_maps.py` | `~/.config/sonasns/gmaps.json` | 是(Places API) |
| 📈 Google Ads | 付費 | ⏸️ 暫緩 | — | — | — |

- YouTube:@okiblues → 訂閱/總觀看/影片數 + 近期 6 支影片觀看與讚(YouTube Data API v3)
- Maps:place_id `ChIJ-5MCoQhp5TQRqDzEKluJwss` → 星等/評論數 + Google 自選最多 5 則評論(Places API New)
- 兩張都是 **Organic**,依規則與 Paid 分開,不互比。

手動更新指令:
```bash
cd SonaSNS-Platform
python3 sync_youtube.py okiblues
python3 sync_maps.py okiblues
```

---

## 每日自動更新(GitHub Actions)

已加進 `.github/workflows/sync-posts.yml`,每天 UTC 22:00(台灣 06:00)連同帖文一起同步、commit、push。

**SS 待辦 — 加兩個 GitHub Secret(缺了 YouTube/Maps 步驟會跳過,不會壞掉):**
1. GitHub repo → Settings → Secrets and variables → Actions → New repository secret
2. 加 `YOUTUBE_API_KEY` = 你的 YouTube 金鑰
3. 加 `GMAPS_API_KEY` = 你的 Places 金鑰
(帖文用的 `GOOGLE_SERVICE_ACCOUNT_JSON` 已存在。)

---

## 金鑰安全(SS 待辦,只能在 Console 操作)

- 兩把金鑰各自「API 限制」收到只放行自己那一個:YouTube 金鑰只勾 **YouTube Data API v3**;Maps 金鑰只勾 **Places API (New)**。
- 帳單 → 設「預算與快訊」($1 美金)當保險絲,被盜刷當天就收到 email。
- 開 Maps Platform 會一次亮約 31 個 API;**未呼叫不計費**,不用管,重點是金鑰只放行一個。

---

## 下一階段:擁有者授權層(門面 → 決策儀表板)

公開層只拿得到「外人視角」。要「老闆後台視角」(維持率、多少人在 Map 找到你、全部評論)需**擁有者/管理員授權 + OAuth**。OKIBLUES 老闆已同意配合。

### A. YouTube Analytics(觀看維持率、流入來源、每支帶來多少訂閱)
需求:對 @okiblues 頻道有**擁有者或管理員**權限,並跑一次 OAuth 同意。
1. 同一個 Google Cloud 專案 → 啟用 **YouTube Analytics API**。
2. OAuth 同意畫面 → **務必發佈成 Production**(測試模式的 refresh token 7 天過期,是踩過的坑)。scope 加 `https://www.googleapis.com/auth/yt-analytics.readonly`。
3. 建 OAuth 用戶端 ID(類型選 **桌面應用程式** 最簡單)。
4. 頻道擁有者本人跑一次授權登入 → 拿到 refresh token → 存 `~/.config/sonasns/`。
5. 之後腳本用 refresh token 拉 Analytics(不用每次登入)。
- ⚠️ 關鍵:誰的 Google 帳號擁有 @okiblues 頻道?若是客戶的帳號,授權那步要**客戶本人登入同意**(或把 SS 加為頻道管理員)。

### B. Business Profile(Map 發現數/路線查詢/來電、全部評論、回覆評論)
需求:SS 的 Google 帳號被加為該商家的**擁有者/管理員**,且 Google **核准 API 存取**。
1. 客戶在 [business.google.com](https://business.google.com) 把 SS 的 Google 帳號加為 **管理員**。
2. 啟用 **Business Profile Performance API** + **My Business Account Management API**。
   - ⚠️ 這組 API 是**存取受限**的:要填 Google 的[存取申請表](https://developers.google.com/my-business/content/prereqs)並等核准(可能數天),不是啟用就能用。
3. OAuth 同意畫面同上發 Production,scope `https://www.googleapis.com/auth/business.manage`。
4. 核准 + 授權後可拉:搜尋曝光、路線查詢、來電、官網點擊、**全部評論 + 回覆**。

### 建議順序
先做 **A(YouTube Analytics)**——只要頻道權限 + OAuth,無需 Google 額外審核,較快見效。
**B(Business Profile)**卡在 Google 審核申請表,平行送出、等核准期間先用現有公開評價頂著。

---

## Google Ads(最後再做)
最重:需 **Developer Token 審核**(數天)+ OAuth 發 Production + 把客戶帳戶掛在你的 MCC 下。
在那之前若要數字,同 Meta:後台手動匯出 → 靜態報告 `reports/okiblues/`。
