@echo off
cd /d "%~dp0"
title FabLab Management System
start "FabLab Server" /b python app.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5000
