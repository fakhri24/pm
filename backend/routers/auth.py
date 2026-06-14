from fastapi import APIRouter, Depends, HTTPException

from auth import create_token, hash_password, verify_password
from database import db, _create_board_with_defaults
from dependencies import get_current_user
from models import LoginRequest, RegisterRequest

router = APIRouter()


@router.get("/api/health")
def health():
    return {"status": "ok"}


@router.post("/api/auth/register")
def register(body: RegisterRequest):
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (body.username, hash_password(body.password)),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()["id"]
        _create_board_with_defaults(conn, user_id, "My Board", with_samples=True)
    return {"token": create_token(body.username)}


@router.post("/api/auth/login")
def login(body: LoginRequest):
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (body.username,)
        ).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(body.username)}


@router.post("/api/auth/logout")
def logout(_: str = Depends(get_current_user)):
    return {"ok": True}


@router.get("/api/auth/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}
