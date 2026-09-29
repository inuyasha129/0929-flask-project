# Flask Hello World 一頁式網站

這是一個基於 Python Flask 輕量級網頁框架所建立的現代化一頁式 (Single-Page) 網站示範專案。

---

## 專案目錄結構

```text
0929季老師/
├── app.py                # Flask 主程式 (含首頁路由與問候 API)
├── requirements.txt      # 專案相依套件清單
├── run.bat               # Windows 一鍵啟動腳本
├── templates/
│   └── index.html        # 前端一頁式網站模板 (Bootstrap 5 響應式排版)
└── README.md             # 本說明文件
```

---

## 功能亮點

1. **Hello World 現代單頁設計**：採用 Bootstrap 5 響應式佈局，支援手機與電腦螢幕。
2. **動態伺服器渲染**：透過 Flask Jinja2 模板動態渲染伺服器連線時間。
3. **即時互動 API (`/api/greet`)**：前端藉由 Fetch API (AJAX) 向 Flask 後端送出使用者名稱，後端回傳專屬問候訊息並即時展示於畫面。
4. **流暢錨點跳轉**：導覽列支援平滑滾動（Smooth Scrolling）至各功能區塊。

---

## 啟動方式

### 方法一：直接執行啟動腳本（最簡單）
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
