import sqlite3

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import verify_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    token = credentials.credentials if credentials else None
    username = verify_token(token) if token else None
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return username


def get_board_id(conn: sqlite3.Connection, username: str, board_id: int | None = None) -> int:
    if board_id is not None:
        row = conn.execute(
            """SELECT b.id FROM boards b
               JOIN users u ON b.user_id = u.id
               WHERE b.id = ? AND u.username = ?""",
            (board_id, username),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT b.id FROM boards b
               JOIN users u ON b.user_id = u.id
               WHERE u.username = ?
               ORDER BY b.id ASC LIMIT 1""",
            (username,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Board not found")
    return row["id"]
