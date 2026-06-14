@echo off
taskkill /f /fi "WINDOWTITLE eq pm-app" >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo App stopped
