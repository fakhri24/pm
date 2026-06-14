from typing import Optional

from fastapi import APIRouter, Depends, Query

from ai import chat_ai
from board_helpers import apply_board_update, fetch_board, validate_actions
from database import db
from dependencies import get_board_id, get_current_user
from models import ChatRequest

router = APIRouter()


@router.post("/api/ai/chat")
def ai_chat(
    body: ChatRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        board_dict = fetch_board(conn, bid).model_dump()

    history = [{"role": m.role, "content": m.content} for m in body.history]
    try:
        ai_response = chat_ai(board_dict, history, body.message)
    except Exception:
        return {"message": "Sorry, I couldn't process that request.", "board_update": None, "board": None}

    message = ai_response.get("message", "")
    board_update = validate_actions(ai_response.get("board_update")) or None

    if board_update:
        try:
            with db() as conn:
                apply_board_update(conn, get_board_id(conn, username, board_id), board_update)
        except Exception:
            board_update = None

    with db() as conn:
        updated_board = fetch_board(conn, get_board_id(conn, username, board_id)).model_dump()

    return {"message": message, "board_update": board_update, "board": updated_board}
