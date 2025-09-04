@echo off
title Ngrok Tunnel for Kick Webhooks

echo ===============================================
echo 🌐 NGROK TUNNEL FOR KICK WEBHOOKS
echo ===============================================
echo.
echo This will create a public URL for your local webhook server
echo Run this AFTER starting the main server (setup-webhook.bat)
echo.
echo If you don't have ngrok:
echo 1. Download from https://ngrok.com/download
echo 2. Extract ngrok.exe to this folder
echo 3. Run this script again
echo.

if not exist ngrok.exe (
    echo ❌ ngrok.exe not found in current directory
    echo Please download from https://ngrok.com/download
    pause
    exit /b
)

echo ✅ Starting ngrok tunnel...
echo.
echo Copy the HTTPS URL (https://xxx.ngrok.io) and use it for webhook setup
echo.

ngrok http 5000