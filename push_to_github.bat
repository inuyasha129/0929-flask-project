@echo off
title Push to GitHub - inuyasha129/0929-flask-project

echo ==================================================
echo   Pushing code to GitHub...
echo   Repository: inuyasha129/0929-flask-project
echo ==================================================
echo.

set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%LOCALAPPDATA%\Programs\Git\ucrt64\bin;%PATH%"

git push -u origin main

echo.
echo ==================================================
if %ERRORLEVEL% EQU 0 (
    echo   [SUCCESS] Upload complete! Code has been pushed to GitHub.
    echo   URL: https://github.com/inuyasha129/0929-flask-project
) else (
    echo   [FAILED] Push failed. Please check the error message above.
)
echo ==================================================
echo.
pause
