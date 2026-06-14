@echo off
cd /d "%~dp0\.."

rem Build the frontend and copy the static export into the backend
cd frontend
call npm install || exit /b 1
call npm run build || exit /b 1
cd ..
if exist backend\static rmdir /s /q backend\static
xcopy /e /i /q frontend\out backend\static >nul

rem Load .env and point the backend at the repo-level data dir
for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
set "DB_PATH=%cd%\data\kanban.db"

cd backend
uv sync || exit /b 1
start "pm-app" /b uv run uvicorn main:app --port 8000 > ..\data\server.log 2>&1

echo App running at http://localhost:8000
