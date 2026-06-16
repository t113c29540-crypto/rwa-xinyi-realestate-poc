# RWA 不動產分割代幣化 PoC — Vercel 全端部署包

「信義之星 XYRE」不動產分割代幣化與收益分配 PoC。本 repo 同時部署**互動原型（靜態）**＋**真功能後端（Python Serverless）**，部署後即為可點擊、可即時運算的完整 demo。

| 路徑 | 檔案 | 內容 |
|---|---|---|
| `/` | `public/index.html` | 五頁式互動原型：標的上架/Oracle → ERC-20 分割發行/PoR → 白名單認購 → 自動租金分配 → ROI 視覺化（純前端、可獨立展示） |
| `/app` | `public/app.html` | 呼叫即時 API 的護眼 UI（估值、PoR 對帳、代幣化、租金分配、ROI、投資人適配推薦、一鍵 PDF 報告） |
| `/api/*` | `api/index.py` | FastAPI（純 Python、無 pandas/numpy），ASGI app 由 Vercel Python Runtime 託管 |

> 結構：靜態檔放 `public/`（Vercel 靜態輸出根）、Serverless 函式放 `api/`、`vercel.json` 把 `/api/*` rewrite 到單一函式。此為 Vercel「靜態站 + Python 函式」標準結構。

### API 端點
- `GET /api/health`
- `GET /api/asset` — 主標的（信義之星）估值（市場可比 6,000,000/坪 × 80 坪 = NT$4.8 億，殖利率 1.25%）
- `POST /api/tokenize`、`POST /api/distribute-rent`、`GET /api/roi`
- `POST /api/recommend` — 投資人適配推薦（`{"profile":"保守|穩健|積極","budget":1000000}`）
- `GET /api/report/{asset_id}?format=pdf|html|json` — AI 三法估值＋風險＋PoR＋代幣化報告；**PDF 內嵌粉圓 OFL 繁中字型**（Vercel Linux 無 macOS 系統字型，故隨包附帶）

---

## 部署方式（GitHub → Vercel Import，推薦）

1. 登入 https://vercel.com → **Add New… → Project → Import** 本 repo
   （`t113c29540-crypto/rwa-xinyi-realestate-poc`，已公開）。
2. **Framework Preset：Other**；**Root Directory：保持根目錄**（`vercel.json`、`requirements.txt`、`api/` 都在根）。
3. 其餘設定不用改，按 **Deploy**。Vercel 會：
   - 以靜態方式服務 `index.html`、`app.html`；
   - 自動偵測 `api/index.py` + `requirements.txt`，建立 **Python Serverless Function**；
   - 套用 `vercel.json` 的 rewrite：`/api/(.*)` → `/api/index`。
4. 約 1–2 分鐘後取得網址，例如 `https://rwa-xinyi-realestate-poc.vercel.app`
   - 原型：`/`　·　即時 API UI：`/app`　·　健康檢查：`/api/health`

> 已部署過「靜態版」者：Vercel 會在偵測到本次 push 後**自動重新部署**；
> 首次出現 `/api/*` 時，確認專案 **Root Directory** 為根目錄即可（無需改 Framework）。

---

## 本機測試（可選）
```bash
pip install -r requirements.txt
python -c "import importlib.util as u; s=u.spec_from_file_location('a','api/index.py'); \
m=u.module_from_spec(s); s.loader.exec_module(m); \
from fastapi.testclient import TestClient; c=TestClient(m.app); \
print(c.get('/api/health').json())"
```

---

## 免責
本 PoC 之上鏈／Oracle／KYC 為**模擬示意**，輸入為模擬資料，估值與對帳為程式即時計算結果，**非真實上鏈、不構成投資建議或證券要約**。RWA 具證券性質，台灣 STO 限專業投資人。字型 jf-openhuninn（粉圓）採 OFL 授權，授權書見 `api/fonts/LICENSE.txt`。
