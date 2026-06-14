# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Kanban board app with AI chat. Key features:

- Sign-in and registration (seeded default account: username `user`, password `password`)
- Multiple boards per user, created from templates (kanban, todo, sprint); boards renameable and deletable
- Drag-and-drop cards and columns; card editing with priority, due date, labels, checklist, and comments
- Card archiving with restore (permanent delete only from the Archived panel)
- Board search, stats bar, label/priority/overdue filtering, CSV export, activity log
- AI chat sidebar that can create, edit, move, and label cards (including priority and due dates)

Runs locally on the host (no Docker).

## Technical Decisions

- Next.js frontend, Python FastAPI backend
- FastAPI serves both the REST API and the built Next.js static export from one uvicorn process
- `uv` as the Python package manager
- SQLite local database (`data/kanban.db`), created automatically on first run
- OpenRouter for AI calls (`deepseek/deepseek-v4-flash` model); `OPENROUTER_API_KEY` in `.env`
- Start/stop scripts for Mac, PC, Linux in `scripts/`

## Commands

**Start / Stop** (requires `uv` and Node.js)

```bash
./scripts/start.sh   # builds frontend into backend/static and starts uvicorn at http://localhost:8000
./scripts/stop.sh    # stops the server (kills pid in data/server.pid)
```

Server log: `data/server.log`.

**Backend tests** (from `backend/`)

```bash
uv run pytest tests/ -v
uv run pytest tests/test_api.py -v  # single file
```

**Frontend** (from `frontend/`)

```bash
npm run dev           # dev server (standalone, no backend)
npm run build         # production build (static export in out/)
npm run test:unit     # Vitest unit + component tests
npm run test:e2e      # Playwright E2E tests
npm run test:all      # both
```

E2E tests must run against the served app (backend + built frontend), not the
standalone dev server — without a backend most tests fail. Start the app first,
then:

```bash
BASE_URL=http://localhost:8000 npx playwright test
```

## Architecture

### Request flow

Browser → FastAPI (`/api/*`) for data, FastAPI serves `/` from `backend/static/` (the compiled Next.js export copied in by `scripts/start.sh`).

Auth: JWT (HS256, 24h expiry) issued at `/api/auth/login`, stored in `localStorage`, sent as `Authorization: Bearer <token>` on every authenticated request.

### Backend (`backend/`)

| File          | Role                                                                                                        |
| ------------- | ----------------------------------------------------------------------------------------------------------- |
| `main.py`     | All routes + `StaticFiles` mount; `_fetch_board()` and `_apply_board_update()` are the central data helpers |
| `auth.py`     | `create_token` / `verify_token`, hardcoded credentials                                                      |
| `database.py` | SQLite init + `db()` context manager; `data/kanban.db` in the repo root (via `DB_PATH`)                     |
| `models.py`   | Pydantic request/response models                                                                            |
| `ai.py`       | OpenRouter client (OpenAI SDK), `chat_ai()` returns `{message, board_update}`                               |

Board state in SQLite: `users → boards → columns → cards`, all with integer `position` fields. Card move logic deletes and re-inserts the card to maintain position integrity.

### Frontend (`frontend/src/`)

| File                         | Role                                                                            |
| ---------------------------- | ------------------------------------------------------------------------------- |
| `app/page.tsx`               | Auth gate: checks `localStorage` token → shows `LoginForm` or `KanbanBoard`     |
| `components/KanbanBoard.tsx` | Single state container (`BoardData`), all CRUD handlers, dnd orchestration      |
| `lib/kanban.ts`              | `BoardData` types, `moveCard()` pure utility                                    |
| `lib/api.ts`                 | All `fetch` calls to `/api/*`                                                   |
| `components/AISidebar.tsx`   | Chat UI; calls `/api/ai/chat`, receives updated board and calls `onBoardUpdate` |

`BoardData` shape: `{ columns: Column[], cards: Record<string, Card> }` where `Column.cardIds` is the ordered list of card ids. The frontend mirrors this from the backend on load; mutations are optimistic (local state updated immediately, API called in background).

### AI chat

`POST /api/ai/chat` sends the full board state + conversation history to `deepseek/deepseek-v4-flash` via OpenRouter. The model returns `{ message, board_update: Action[] | null }`. The backend applies actions via `_apply_board_update()` and returns the refreshed board. `OPENROUTER_API_KEY` must be set in `.env`.

## Brand Colors

```
--color-yellow:  #ecad0a   accent lines, highlights
--color-blue:    #209dd7   links, key sections
--color-purple:  #753991   submit buttons, important actions
--color-navy:    #032147   main headings
--color-gray:    #888888   supporting text, labels
```

## Coding Standards

- No over-engineering, no unnecessary defensive programming, no extra features
- No emojis anywhere
- Identify root cause before fixing; prove with evidence first
- Latest library versions and idiomatic patterns

## DETAILED PLAN

@docs/PLAN.md
