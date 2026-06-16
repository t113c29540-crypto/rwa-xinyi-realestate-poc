# RWA 不動產代幣化 PoC — Vercel 部署包

本資料夾是「信義地產通 XinyiRealEstate」不動產分割代幣化 PoC 的**互動原型靜態網站**，
已可直接部署到 Vercel（純前端、零相依、零後端，部署後即為完整可點擊 demo）。

- `index.html`：五頁式互動原型（標的上架/Oracle → ERC-20 分割發行/PoR → 白名單認購 → 自動租金分配 → ROI 視覺化）
- `vercel.json`：靜態站設定（cleanUrls、安全標頭）

---

## 部署方式（擇一）

### 方式 A｜GitHub → Vercel Import（推薦，本機免裝工具）
1. 把本資料夾推上一個 GitHub repo（可由我代為建立並推送）。
2. 登入 https://vercel.com → **Add New… → Project → Import** 該 repo。
3. Framework Preset 選 **Other**（靜態）；Root Directory 指到本資料夾；按 **Deploy**。
4. 約 30 秒後取得網址，例如 `https://rwa-xinyi-poc.vercel.app`。

### 方式 B｜Vercel CLI（需先裝 Node.js）
```bash
npm i -g vercel          # 需 Node.js 18+
cd RWA_Vercel_Deploy
vercel                   # 首次會開瀏覽器登入；一路 Enter
vercel --prod            # 正式部署，輸出 production 網址
```

### 方式 C｜Vercel 網站「部署資料夾」
登入 Vercel → 新專案 → 依指示上傳/連結本資料夾即可（靜態自動識別）。

---

## 之後若要連同「真功能後端」一起上線
原型為純前端展示；若要讓 `/api/recommend`、`/api/report`（PDF）等**真實運算端點**也上線，
需把 `RWA_不動產代幣化_POC/backend` 的 FastAPI 改為 Vercel Python Serverless（`api/index.py` 匯出 `app`），
並注意：pandas/numpy/reportlab 體積與冷啟動、PDF 需**內嵌一份 CJK 字型**（Vercel Linux 無 macOS 系統字型）。
此為可選的進階步驟，靜態原型已能完整展示流程。

---

*PoC：上鏈/Oracle/KYC 為模擬示意，非真實上鏈，不構成投資招攬。*
