@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==============================================
echo   Flask Hello World 一頁式網站伺服器
echo ==============================================
echo.
echo 伺服器啟動中，請於瀏覽器開啟：
echo   👉 http://127.0.0.1:5000
echo.
echo 提示：欲關閉伺服器請按 Ctrl + C
echo ==============================================
echo.
if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" app.py
) else (
    python app.py
)
pause
