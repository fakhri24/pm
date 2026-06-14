# Backend — Description

## Tech Stack

- **Python 3.12**
- **FastAPI** — web framework
- **uvicorn** — ASGI server
- **uv** — package manager (pyproject.toml)
- **python-jose[cryptography]** — JWT auth (HS256, 24-hour expiry, `SECRET_KEY` from env)
- **pytest + httpx** — testing (dev deps)

## Structure

```
backend/
  main.py          — FastAPI app: all API routes + StaticFiles mount
  auth.py          — JWT token create/verify, hardcoded credentials
  database.py      — SQLite init, connection helpers, seed data
  models.py        — Pydantic request/response models
  pyproject.toml   — uv-managed dependencies
  static/          — built Next.js frontend (copied in by scripts/start.sh, gitignored)
  tests/
    test_api.py    — Full integration tests (health, auth, board, columns, cards) with isolated temp DB
    test_health.py — Basic health and auth smoke tests (uses default test client)
```

## Running Locally

```bash
./scripts/start.sh   # builds frontend and starts uvicorn at http://localhost:8000
./scripts/stop.sh    # stops the server
```

## API Routes

| Method | Path                         | Auth | Description                        |
| ------ | ---------------------------- | ---- | ---------------------------------- |
| GET    | `/api/health`                | No   | Returns `{"status": "ok"}`         |
| POST   | `/api/auth/login`            | No   | `{username, password}` → `{token}` |
| POST   | `/api/auth/logout`           | No   | Returns `{"ok": true}`             |
| GET    | `/api/auth/me`               | Yes  | Returns `{username}`               |
| GET    | `/api/board`                 | Yes  | Full board with columns and cards  |
| PUT    | `/api/board/columns/{id}`    | Yes  | Rename a column                    |
| POST   | `/api/board/cards`           | Yes  | Create a card in a column          |
| PUT    | `/api/board/cards/{id}`      | Yes  | Update card title/details          |
| DELETE | `/api/board/cards/{id}`      | Yes  | Delete a card                      |
| PUT    | `/api/board/cards/{id}/move` | Yes  | Move card to column at position    |
| GET    | `/`                          | No   | Serves static Next.js frontend     |

## Database

SQLite at `data/kanban.db` in the repo root (path set via `DB_PATH`). Created automatically on startup with seed data: user `user`/`password`, board "My Board", 5 columns (Backlog, Discovery, In Progress, Review, Done), 8 cards spread across columns.

## Running Tests

From `backend/`:

```bash
uv run pytest tests/ -v
```
