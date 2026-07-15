@echo off
chcp 936 >nul 2>&1
title CandleCast - AI K线分析助手
cd /d "%~dp0"
S:\Anaconda\python.exe run.py
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，请查看上方错误信息。
    pause
)
