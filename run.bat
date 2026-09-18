@echo off
title Unificador de Videos Local
echo ===================================================
echo           UNIFICADOR DE VIDEOS LOCAL
echo ===================================================
echo.
echo Iniciando el servidor local...
echo.

cd /d "%~dp0"

py -m pip install -r requirements.txt >nul 2>&1

start http://127.0.0.1:8000/

py app.py

pause
