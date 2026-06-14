#!/bin/bash
set -e
cd "$(dirname "$0")/.."

if [ -f data/server.pid ]; then
    kill "$(cat data/server.pid)" 2>/dev/null || true
    rm -f data/server.pid
fi
echo "App stopped"
