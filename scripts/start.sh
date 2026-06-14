#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# Build the frontend and copy the static export into the backend
(cd frontend && npm install && npm run build)
rm -rf backend/static
cp -R frontend/out backend/static

# Load .env (OPENROUTER_API_KEY) and point the backend at the repo-level data dir
set -a
source .env
set +a
export DB_PATH="$PWD/data/kanban.db"

cd backend
uv sync
nohup uv run uvicorn main:app --port 8000 > ../data/server.log 2>&1 &
echo $! > ../data/server.pid

echo "App running at http://localhost:8000"
