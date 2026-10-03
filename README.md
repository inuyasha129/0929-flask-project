# Flask Hello World 一頁式網站

這是一個基於 Python Flask 輕量級網頁框架所建立的現代化一頁式 (Single-Page) 網站示範專案，並整合 **GitHub Actions 自動化測試 (CI)** 與 **Render 雲端自動部署 (CD)**。

---

## 專案目錄結構

```text
0929季老師/
├── .github/workflows/
│   └── deploy.yml        # GitHub Actions CI/CD 流程設定檔
├── templates/
│   └── index.html        # 前端一頁式網站模板 (Bootstrap 5 響應式排版)
├── app.py                # Flask 主程式 (含首頁路由與問候 API)
├── test_app.py           # 單元測試 (供 CI 自動檢驗)
├── render.yaml           # Render 雲端服務配置檔 (Blueprint)
├── requirements.txt      # 專案相依套件清單 (含 Flask, Gunicorn)
├── run.bat               # Windows 本機一鍵啟動腳本
├── push_to_github.bat    # Windows 一鍵推送 GitHub 腳本
└── README.md             # 本說明文件
```

---

## 功能亮點

1. **Hello World 現代單頁設計**：採用 Bootstrap 5 響應式佈局，支援手機與電腦螢幕。
2. **動態伺服器渲染**：透過 Flask Jinja2 模板動態渲染伺服器連線時間。
3. **即時互動 API (`/api/greet`)**：前端藉由 Fetch API (AJAX) 向 Flask 後端送出使用者名稱，後端回傳專屬問候訊息並即時展示於畫面。
4. **CI/CD 自動化流程**：
   - 每次 Push / PR 自動執行 Python 語法檢驗與單元測試。
   - 測試全數通過後，自動透過 Deploy Hook 部署至 Render 平台。

---

## 本機啟動方式

### 方法一：直接執行啟動腳本
直接雙擊執行目錄中的 `run.bat`，或在終端機執行：
```powershell
.\run.bat
```

### 方法二：手動執行
1. 啟動虛擬環境中的 Python 運行主程式：
```powershell
.\.venv\Scripts\python.exe app.py
```
2. 在瀏覽器打開以下網址：
👉 **http://127.0.0.1:5000**

---

## Render CI/CD 部署設定教學

### 步驟 1：在 Render 上建立 Web Service
1. 註冊/登入 [Render](https://render.com/)。
2. 點擊 **New +** 選擇 **Web Service**。
3. 連結你的 GitHub 儲存庫：`inuyasha129/0929-flask-project`。
4. 設定基本參數：
   - **Name**: `0929-flask-project`
   - **Region**: 建議選擇 `Singapore` 或鄰近區域
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: `Free`
5. （建議）將 **Auto-Deploy** 設為 `No`，由 GitHub Actions 測試通過後再觸發部署。

### 步驟 2：取得 Render Deploy Hook
1. 在建立好的 Render Web Service 頁面中，點擊左側選單的 **Settings**。
2. 往下滾動找到 **Deploy Hook** 區塊。
3. 點擊 **Add Deploy Hook** 或複製現有的 URL（格式類似：`https://api.render.com/deploy/srv-xxxxxxx?key=yyyyyy`）。

### 步驟 3：在 GitHub 設定 Secret
1. 開啟 GitHub 倉庫：[inuyasha129/0929-flask-project](https://github.com/inuyasha129/0929-flask-project)
2. 依序點擊：**Settings** -> **Secrets and variables** -> **Actions**。
3. 點擊 **New repository secret**：
   - **Name**: `RENDER_DEPLOY_HOOK_URL`
   - **Secret**: 貼上剛才從 Render 複製的 Deploy Hook 完整網址。
4. 點擊 **Add secret** 儲存。

完成後，未來每次推送至 `main` 分支，GitHub Actions 將會先執行自動測試，確認完全無誤後自動觸發 Render 部署上線！
