@echo off
title Kick Chat Webhook Monitor Setup

echo ===============================================
echo 🥩 KICK CHAT WEBHOOK MONITOR SETUP
echo ===============================================

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ===============================================
echo 🚀 STARTING SERVER...
echo ===============================================
echo.
echo Your Kick API credentials are configured!
echo Client ID: 01K49YM1DQK8CMAF1MNRQ6Z781
echo.
echo Dashboard will open at: http://localhost:5000
echo.
echo ⚠️  IMPORTANT FOR WEBHOOKS TO WORK:
echo 1. Install ngrok from https://ngrok.com/download
echo 2. In another terminal, run: ngrok http 5000
echo 3. Copy the https://xxx.ngrok.io URL
echo 4. Use that URL for webhook setup instead of localhost
echo.
echo Starting server in 3 seconds...
timeout /t 3 /nobreak >nul

python kick-webhook-server.py
pause