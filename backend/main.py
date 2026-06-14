from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import auth, board
from routers.ai_router import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

# Same-origin in production (FastAPI serves the built frontend). Allow the Next.js
# dev server origin so the standalone dev workflow can call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(board.router)
app.include_router(ai_router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
