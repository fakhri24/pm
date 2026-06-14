# Project Plan — Project Management MVP

---

## Part 1: Plan ✅

**Goal**: Document the full plan with detailed steps and get user approval.

### Steps

- [x] Explore existing frontend codebase
- [x] Create `frontend/AGENTS.md` describing the existing code
- [x] Enrich this PLAN.md with detailed steps, checklists, and success criteria
- [ ] User approves plan

### Success Criteria

- Plan is detailed enough that each part can be executed without ambiguity
- `frontend/AGENTS.md` accurately describes the existing codebase
- User has approved the plan

---

## Part 2: Scaffolding

**Goal**: Docker infrastructure + FastAPI backend + start/stop scripts. Confirm a "hello world" that serves static HTML and makes a backend API call.

### Steps

- [x] Create `backend/main.py` — FastAPI app with a `GET /api/health` route returning `{"status": "ok"}`
- [x] Create `backend/pyproject.toml` (uv-managed) with `fastapi`, `uvicorn[standard]` dependencies
- [x] Create `Dockerfile` — single container: installs Python deps with uv, copies backend, runs uvicorn
- [x] Create `docker-compose.yml` — maps port 8000, mounts `.env`, sets working dir
- [x] Create `scripts/start.sh` (Mac/Linux) — `docker compose up --build -d`
- [x] Create `scripts/stop.sh` (Mac/Linux) — `docker compose down`
- [x] Create `scripts/start.bat` and `scripts/stop.bat` (Windows)
- [x] Create `backend/static/index.html` — minimal "Hello World" HTML served at `/`
- [x] Configure FastAPI to serve `static/` at `/` using `StaticFiles` mount
- [x] Update `backend/AGENTS.md` to describe the backend structure
- [x] Manually verify: `./scripts/start.sh` → `http://localhost:8000` shows HTML, `/api/health` returns JSON
- [x] Write backend unit test for `/api/health` endpoint

### Tests

- `GET /api/health` → `200 {"status": "ok"}`
- `GET /` → `200` with HTML content

### Success Criteria

- Docker container builds and runs cleanly
- Hello World HTML visible at `http://localhost:8000`
- Health API endpoint returns correct JSON
- Start and stop scripts work on Mac/Linux and Windows

---

## Part 3: Add in Frontend

**Goal**: Statically build the Next.js frontend and serve it from FastAPI, replacing the hello world HTML.

### Steps

- [x] Configure `next.config.ts` for static export (`output: 'export'`)
- [x] Update `Dockerfile` to: install Node deps, run `npm run build`, copy `out/` into the backend image
- [x] Update FastAPI `StaticFiles` mount to serve the built Next.js `out/` directory
- [x] Ensure Next.js `assetPrefix` and `basePath` are correct for serving at `/`
- [x] Verify all existing frontend unit tests still pass (`npm run test:unit`)
- [x] Verify Playwright E2E tests pass against the Docker-served app
- [x] Add/update E2E test to verify Kanban loads at `http://localhost:8000`

### Tests

- All existing Vitest unit + component tests pass
- Playwright E2E: Kanban board visible at root URL
- All 5 columns render with correct names

### Success Criteria

- `http://localhost:8000` shows the full Kanban demo app
- No broken assets (JS, CSS, fonts)
- All existing tests green

---

## Part 4: Add in a Fake User Sign-in Experience

**Goal**: Protect the Kanban behind a login page. Credentials: `user` / `password`. Users can log out.

### Steps

- [x] Add `POST /api/auth/login` FastAPI route — accepts `{username, password}`, returns `{token}` (simple signed JWT or opaque session token, hardcoded credentials)
- [x] Add `POST /api/auth/logout` route — clears session
- [x] Add `GET /api/auth/me` route — returns current user or 401
- [x] Create `src/components/LoginForm.tsx` in frontend — username + password fields, submit button, error message
- [x] Update `src/app/page.tsx` — check auth state on load; show LoginForm if not authenticated, KanbanBoard if authenticated
- [x] Add logout button to KanbanBoard header
- [x] Manage auth token in `localStorage` (or cookie) on the frontend
- [x] Add frontend unit tests for LoginForm (renders, validation, submit)
- [x] Add E2E tests: unauthenticated user sees login, login with wrong credentials shows error, login with correct credentials shows Kanban, logout returns to login

### Tests

- `POST /api/auth/login` with correct creds → `200 {token}`
- `POST /api/auth/login` with wrong creds → `401`
- `GET /api/auth/me` with valid token → `200 {username}`
- `GET /api/auth/me` without token → `401`
- Frontend E2E: full login/logout flow

### Success Criteria

- Unauthenticated users cannot see the Kanban board
- Login with `user` / `password` succeeds
- Incorrect credentials show an error
- Logout returns to login screen
- All tests green

---

## Part 5: Database Modeling ✅

**Goal**: Design and document the SQLite schema for the Kanban. Get user sign-off before implementation.

### Steps

- [x] Design SQLite schema for: users, boards, columns, cards
- [x] Save schema as `docs/schema.md` with table definitions and rationale
- [x] Confirm the schema supports: multiple users (future), 1 board per user (MVP), ordered columns, ordered cards within columns, card title + details
- [x] User reviews and approves schema

### Tables (proposed)

- `users` — id, username, password_hash
- `boards` — id, user_id (FK), name
- `columns` — id, board_id (FK), title, position (int)
- `cards` — id, column_id (FK), title, details, position (int)

### Success Criteria

- Schema documented clearly in `docs/schema.md`
- User has approved the schema

---

## Part 6: Backend API ✅

**Goal**: Full CRUD API for the Kanban board backed by SQLite. Database is created automatically if it doesn't exist.

### Steps

- [x] Create `backend/database.py` — SQLite connection, table creation on startup (if not exists)
- [x] Create `backend/models.py` — Pydantic models for request/response
- [x] Seed the database with the `user` / `password` user and their initial Kanban board (5 columns, sample cards) on first run
- [x] Add `GET /api/board` — returns full board JSON for authenticated user
- [x] Add `PUT /api/board/columns/{id}` — rename a column
- [x] Add `POST /api/board/cards` — create a card in a column
- [x] Add `PUT /api/board/cards/{id}` — update card title/details
- [x] Add `DELETE /api/board/cards/{id}` — delete a card
- [x] Add `PUT /api/board/cards/{id}/move` — move card to column at position
- [x] Write backend unit tests for all routes (with test database)
- [x] Update `backend/AGENTS.md`

### Tests

- Each API route has at minimum: success case, auth-required case
- Move card: within-column reorder, cross-column move
- All tests use an isolated in-memory or temp test database

### Success Criteria

- All API routes behave correctly and are protected by auth
- Database is created automatically on first run
- All backend tests green

---

## Part 7: Frontend + Backend Integration ✅

**Goal**: Frontend uses the backend API for all Kanban operations. Board state is persistent across reloads.

### Steps

- [x] Create `src/lib/api.ts` — typed fetch wrappers for all backend API routes (with auth header)
- [x] Replace `initialData` in `KanbanBoard` with `GET /api/board` on load
- [x] Wire `handleRenameColumn` → `PUT /api/board/columns/{id}`
- [x] Wire `handleAddCard` → `POST /api/board/cards`
- [x] Wire `handleDeleteCard` → `DELETE /api/board/cards/{id}`
- [x] Wire `handleDragEnd` (card move) → `PUT /api/board/cards/{id}/move`
- [x] Handle loading and error states in the UI
- [x] Update existing component tests to mock API calls
- [x] Add E2E tests: add card persists after page reload, move card persists, rename column persists

### Tests

- E2E: Add card → reload → card still present
- E2E: Move card → reload → card in new column
- E2E: Rename column → reload → new name shown
- Unit: API fetch wrappers handle 401 and redirect to login

### Success Criteria

- Board state persists across page reloads
- All CRUD operations update the database
- All tests green

---

## Part 8: AI Connectivity ✅

**Goal**: Backend can make an AI call via OpenRouter. Validate with a simple test.

### Steps

- [x] Add `openai` (or `httpx`) to backend dependencies for OpenRouter calls
- [x] Create `backend/ai.py` — `call_ai(messages)` function using OpenRouter API (`deepseek/deepseek-v4-flash`)
- [x] Load `OPENROUTER_API_KEY` from environment variable (via `.env`)
- [x] Add `POST /api/ai/test` route — sends "What is 2+2?" and returns the AI response
- [x] Write backend test for AI connectivity (can use mock or real key)
- [x] Manually verify the `/api/ai/test` endpoint returns a sensible response

### Tests

- `POST /api/ai/test` → `200` with a response containing "4"
- Unit test for `call_ai()` using a mocked HTTP response

### Success Criteria

- Backend can call OpenRouter and get a valid response
- API key is never hardcoded — read from env only
- Test endpoint works end-to-end

---

## Part 9: AI Kanban Integration ✅

**Goal**: AI receives the full board state + conversation history and can optionally update the Kanban via Structured Outputs.

### Steps

- [x] Define Structured Output schema: `{message: string, board_update?: BoardUpdate}` where `BoardUpdate` describes card/column changes
- [x] Update `backend/ai.py` to: build system prompt with board JSON, append user message, request structured output
- [x] Add `POST /api/ai/chat` route — accepts `{message, history}`, returns `{message, board_update?}`
- [x] If `board_update` is present, apply it to the database within the same request
- [x] Return the updated board state alongside the AI response
- [x] Write backend tests for the chat route (mocked AI, various board update scenarios)

### Tests

- AI responds with a plain message when no board change is needed
- AI response with `board_update` is applied to the database
- Board state in response reflects any changes
- Malformed AI response is handled gracefully

### Success Criteria

- AI has full board context in every call
- Structured output reliably carries optional board updates
- Board updates are persisted immediately
- All tests green

---

## Part 10: AI Chat Sidebar ✅

**Goal**: Beautiful sidebar UI for full AI chat. Board refreshes automatically when AI makes changes.

### Steps

- [x] Create `src/components/AISidebar.tsx` — chat message list, input box, send button, loading state
- [x] Wire to `POST /api/ai/chat` — send message + history, receive reply
- [x] If response includes `board_update`, trigger board refresh (done via returned board in response)
- [x] Style using brand colors (purple submit button, navy headings, etc.)
- [x] Add toggle button to show/hide the sidebar
- [x] Add loading indicator while AI is responding
- [x] Maintain conversation history in component state (sent to backend each time)
- [x] Add E2E tests: open sidebar, send message, receive reply; AI-triggered card creation appears on board
- [x] Add component unit tests for AISidebar (render, send message, loading state)

### Tests

- E2E: Open chat → send "add a card to Backlog called Test Task" → card appears on board
- E2E: Chat history is preserved across multiple messages in session
- Unit: Sidebar renders correctly, submit disables input while loading

### Success Criteria

- AI chat is functional and visually polished
- Board updates from AI are reflected immediately without full reload
- Conversation history is maintained per session
- All tests green

---

## Post-MVP Iterations ✅

Features added after the 10-part MVP plan, one commit per iteration:

1. **Iteration 1** — registration, multiple boards per user, column management, card priority/due date
2. **Iteration 2** — card labels, edit modal, board stats bar, search
3. **Iteration 3** — card comments, column drag-to-reorder
4. **Iteration 4** — card checklists, activity log
5. **Iteration 5** — CSV export, overdue filter, `/` search shortcut
6. **Iteration 6** — filter cards by label and priority (FilterBar)
7. **Iteration 7** — card archiving with restore; permanent delete moved behind the Archived panel
8. **Iteration 8** — AI can set priority, due date, and labels; partial `update_card` action
9. **Iteration 9** — board templates (kanban, todo, sprint); new boards start empty
10. **Iteration 10** — hardening pass: full test suites, E2E run, docs updated
