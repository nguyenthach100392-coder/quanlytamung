@echo off
chcp 65001 >nul
title Cai dat thu vien
cd /d "%~dp0"

echo Dang cai thu vien Python...
pip install -r requirements.txt

echo.
echo Hoan tat. Bay gio chay file "run.bat" de khoi dong server.
pause
