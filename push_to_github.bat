@echo off
chcp 65001 >nul
title 推送專案至 GitHub - inuyasha129/0929-flask-project

echo ==================================================
echo   正在推送程式碼至 GitHub...
echo   儲存庫: https://github.com/inuyasha129/0929-flask-project.git
echo ==================================================
echo.

set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%LOCALAPPDATA%\Programs\Git\ucrt64\bin;%PATH%"

git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==================================================
    echo   [成功] 程式碼已成功推送至 GitHub！
    echo   儲存庫網址: https://github.com/inuyasha129/0929-flask-project
    echo ==================================================
) else (
    echo.
    echo ==================================================
    echo   [提示] 推送失敗，請確認：
    echo   1. 是否已在 GitHub 上建立名稱為 0929-flask-project 的儲存庫？
    echo      建立網址: https://github.com/new
    echo   2. 是否已在瀏覽器彈出視窗中登入或授權 GitHub 帳號？
    echo ==================================================
)

echo.
pause
