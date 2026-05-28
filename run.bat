@echo off
chcp 65001 >nul
title He thong theo doi Tam ung - Server
cd /d "%~dp0"

echo ============================================================
echo  KHOI DONG SERVER
echo  Truy cap qua: http://localhost:8501
echo  Cac may khac trong mang LAN: http://[IP_MAY_NAY]:8501
echo  De biet IP, mo cmd va go: ipconfig
echo ============================================================

streamlit run app.py --server.address 0.0.0.0 --server.port 8501

pause
