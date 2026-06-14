import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from activity import log_activity
from board_helpers import fetch_board, parse_labels
from database import db, _create_board_with_defaults, BOARD_TEMPLATES
from dependencies import get_board_id, get_current_user
from models import (
    ActivityEntry, ArchivedCardOut, BoardOut, BoardSummary, CardOut,
    ChecklistItemOut, CommentOut, CreateBoardRequest, CreateCardRequest,
    CreateChecklistItemRequest, CreateColumnRequest, CreateCommentRequest,
    MoveCardRequest, MoveColumnRequest, RenameBoardRequest,
    RenameColumnRequest, UpdateCardRequest, UpdateChecklistItemRequest,
)

router = APIRouter()


def _require_card(conn, card_id: int, board_id: int):
    card = conn.execute(
        "SELECT id FROM cards WHERE id = ? AND column_id IN (SELECT id FROM columns WHERE board_id = ?)",
        (card_id, board_id),
    ).fetchone()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _checklist_row_to_out(row) -> "ChecklistItemOut":
    d = dict(row)
    return ChecklistItemOut(checked=bool(d.pop("checked")), **d)


# --- Boards ---

@router.get("/api/boards", response_model=list[BoardSummary])
def list_boards(username: str = Depends(get_current_user)):
    with db() as conn:
        rows = conn.execute(
            """SELECT b.id, b.name,
                      (SELECT COUNT(*) FROM cards ca
                       JOIN columns co ON ca.column_id = co.id
                       WHERE co.board_id = b.id) AS card_count
               FROM boards b JOIN users u ON b.user_id = u.id
               WHERE u.username = ?
               ORDER BY b.id ASC""",
            (username,),
        ).fetchall()
    return [BoardSummary(**dict(r)) for r in rows]


@router.post("/api/boards", response_model=BoardSummary)
def create_board(body: CreateBoardRequest, username: str = Depends(get_current_user)):
    if body.template not in BOARD_TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")
    with db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        board_id = _create_board_with_defaults(conn, user["id"], body.name, body.template)
        card_count = conn.execute(
            """SELECT COUNT(*) FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ?""",
            (board_id,),
        ).fetchone()[0]
    return BoardSummary(id=board_id, name=body.name, card_count=card_count)


@router.put("/api/boards/{board_id_path}", response_model=BoardSummary)
def rename_board(
    board_id_path: int,
    body: RenameBoardRequest,
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id_path)
        conn.execute("UPDATE boards SET name = ? WHERE id = ?", (body.name, bid))
        card_count = conn.execute(
            """SELECT COUNT(*) FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ?""",
            (bid,),
        ).fetchone()[0]
    return BoardSummary(id=bid, name=body.name, card_count=card_count)


@router.delete("/api/boards/{board_id_path}")
def delete_board(
    board_id_path: int,
    username: str = Depends(get_current_user),
):
    with db() as conn:
        # Ensure user owns the board
        get_board_id(conn, username, board_id_path)
        # Prevent deleting the last board
        count = conn.execute(
            """SELECT COUNT(*) FROM boards b
               JOIN users u ON b.user_id = u.id
               WHERE u.username = ?""",
            (username,),
        ).fetchone()[0]
        if count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last board")
        conn.execute("DELETE FROM boards WHERE id = ?", (board_id_path,))
    return {"ok": True}


# --- Search ---

@router.get("/api/board/search")
def search_cards(
    q: str = Query(min_length=1),
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        rows = conn.execute(
            """SELECT ca.id, ca.title, ca.details, ca.position, ca.priority, ca.due_date, ca.labels,
                      co.id AS column_id, co.title AS column_title
               FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ? AND ca.archived = 0
                 AND (LOWER(ca.title) LIKE ? OR LOWER(ca.details) LIKE ?)
               ORDER BY co.position, ca.position""",
            (bid, f"%{q.lower()}%", f"%{q.lower()}%"),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "details": r["details"],
            "position": r["position"],
            "priority": r["priority"],
            "due_date": r["due_date"],
            "labels": parse_labels(r["labels"]),
            "column_id": r["column_id"],
            "column_title": r["column_title"],
        }
        for r in rows
    ]


# --- Board stats ---

@router.get("/api/board/stats")
def board_stats(
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        col_stats = conn.execute(
            """SELECT co.id, co.title, COUNT(ca.id) AS card_count
               FROM columns co
               LEFT JOIN cards ca ON ca.column_id = co.id AND ca.archived = 0
               WHERE co.board_id = ?
               GROUP BY co.id
               ORDER BY co.position""",
            (bid,),
        ).fetchall()
        agg = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN ca.due_date IS NOT NULL AND ca.due_date < date('now') THEN 1 ELSE 0 END) AS overdue,
                      SUM(CASE WHEN ca.priority = 'urgent' THEN 1 ELSE 0 END) AS urgent
               FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ? AND ca.archived = 0""",
            (bid,),
        ).fetchone()
        total, overdue, urgent = agg["total"], agg["overdue"] or 0, agg["urgent"] or 0
    return {
        "total": total,
        "overdue": overdue,
        "urgent": urgent,
        "columns": [
            {"id": r["id"], "title": r["title"], "card_count": r["card_count"]}
            for r in col_stats
        ],
    }


# --- Export ---

@router.get("/api/board/export")
def export_board(
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        board_name = conn.execute("SELECT name FROM boards WHERE id = ?", (bid,)).fetchone()["name"]
        rows = conn.execute(
            """SELECT ca.id, ca.title, ca.details, ca.priority, ca.due_date, ca.labels,
                      co.title AS column_title, ca.position
               FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ? AND ca.archived = 0
               ORDER BY co.position, ca.position""",
            (bid,),
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Details", "Column", "Priority", "Due Date", "Labels"])
    for r in rows:
        labels = ", ".join(parse_labels(r["labels"]))
        writer.writerow([
            r["id"], r["title"], r["details"], r["column_title"],
            r["priority"] or "", r["due_date"] or "", labels,
        ])

    output.seek(0)
    filename = f"{board_name.replace(' ', '_')}_export.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Single board (backwards-compatible) ---

@router.get("/api/board", response_model=BoardOut)
def get_board(
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        return fetch_board(conn, bid)


# --- Columns ---

@router.post("/api/board/columns")
def add_column(
    body: CreateColumnRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM columns WHERE board_id = ?", (bid,)
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO columns (board_id, title, position) VALUES (?, ?, ?)",
            (bid, body.title, max_pos + 1),
        )
        col = conn.execute(
            "SELECT id, title, position FROM columns WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        log_activity(conn, bid, username, "column_added", f"Added column '{body.title}'")
    return {"id": col["id"], "title": col["title"], "position": col["position"], "cards": []}


@router.put("/api/board/columns/{column_id}")
def rename_column(
    column_id: int,
    body: RenameColumnRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        result = conn.execute(
            "UPDATE columns SET title = ? WHERE id = ? AND board_id = ?",
            (body.title, column_id, bid),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Column not found")
    return {"ok": True}


@router.delete("/api/board/columns/{column_id}")
def delete_column(
    column_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        col = conn.execute(
            "SELECT id, title FROM columns WHERE id = ? AND board_id = ?", (column_id, bid)
        ).fetchone()
        if not col:
            raise HTTPException(status_code=404, detail="Column not found")
        col_count = conn.execute(
            "SELECT COUNT(*) FROM columns WHERE board_id = ?", (bid,)
        ).fetchone()[0]
        if col_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last column")
        log_activity(conn, bid, username, "column_deleted", f"Deleted column '{col['title']}'")
        conn.execute("DELETE FROM columns WHERE id = ?", (column_id,))
        # Recompact positions for remaining columns
        remaining = conn.execute(
            "SELECT id FROM columns WHERE board_id = ? ORDER BY position ASC", (bid,)
        ).fetchall()
        for idx, row in enumerate(remaining):
            conn.execute("UPDATE columns SET position = ? WHERE id = ?", (idx, row["id"]))
    return {"ok": True}


@router.put("/api/board/columns/{column_id}/move")
def move_column(
    column_id: int,
    body: MoveColumnRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        col = conn.execute(
            "SELECT id, position FROM columns WHERE id = ? AND board_id = ?", (column_id, bid)
        ).fetchone()
        if not col:
            raise HTTPException(status_code=404, detail="Column not found")

        total = conn.execute(
            "SELECT COUNT(*) FROM columns WHERE board_id = ?", (bid,)
        ).fetchone()[0]
        new_pos = min(body.position, total - 1)
        old_pos = col["position"]

        if old_pos == new_pos:
            return {"ok": True}

        if new_pos > old_pos:
            conn.execute(
                "UPDATE columns SET position = position - 1 WHERE board_id = ? AND position > ? AND position <= ?",
                (bid, old_pos, new_pos),
            )
        else:
            conn.execute(
                "UPDATE columns SET position = position + 1 WHERE board_id = ? AND position >= ? AND position < ?",
                (bid, new_pos, old_pos),
            )
        conn.execute("UPDATE columns SET position = ? WHERE id = ?", (new_pos, column_id))
    return {"ok": True}


# --- Activity log ---

@router.get("/api/board/activity", response_model=list[ActivityEntry])
def get_activity(
    limit: int = Query(default=30, ge=1, le=100),
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        rows = conn.execute(
            "SELECT id, board_id, username, action, description, created_at FROM activity_log WHERE board_id = ? ORDER BY created_at DESC LIMIT ?",
            (bid, limit),
        ).fetchall()
    return [ActivityEntry(**dict(r)) for r in rows]


# --- Comments ---

@router.get("/api/board/cards/{card_id}/comments", response_model=list[CommentOut])
def get_comments(
    card_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        _require_card(conn, card_id, bid)
        rows = conn.execute(
            "SELECT id, card_id, content, created_at FROM comments WHERE card_id = ? ORDER BY created_at ASC",
            (card_id,),
        ).fetchall()
    return [CommentOut(**dict(r)) for r in rows]


@router.post("/api/board/cards/{card_id}/comments", response_model=CommentOut)
def add_comment(
    card_id: int,
    body: CreateCommentRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        _require_card(conn, card_id, bid)
        cursor = conn.execute(
            "INSERT INTO comments (card_id, content) VALUES (?, ?)",
            (card_id, body.content),
        )
        row = conn.execute(
            "SELECT id, card_id, content, created_at FROM comments WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return CommentOut(**dict(row))


@router.delete("/api/board/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        row = conn.execute(
            """SELECT c.id FROM comments c
               JOIN cards ca ON c.card_id = ca.id
               JOIN columns co ON ca.column_id = co.id
               WHERE c.id = ? AND co.board_id = ?""",
            (comment_id, bid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Comment not found")
        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    return {"ok": True}


# --- Checklist ---

@router.get("/api/board/cards/{card_id}/checklist", response_model=list[ChecklistItemOut])
def get_checklist(
    card_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        _require_card(conn, card_id, bid)
        rows = conn.execute(
            "SELECT id, card_id, content, checked, position FROM checklist_items WHERE card_id = ? ORDER BY position ASC",
            (card_id,),
        ).fetchall()
    return [_checklist_row_to_out(r) for r in rows]


@router.post("/api/board/cards/{card_id}/checklist", response_model=ChecklistItemOut)
def add_checklist_item(
    card_id: int,
    body: CreateChecklistItemRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        _require_card(conn, card_id, bid)
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM checklist_items WHERE card_id = ?",
            (card_id,),
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO checklist_items (card_id, content, checked, position) VALUES (?, ?, 0, ?)",
            (card_id, body.content, max_pos + 1),
        )
        row = conn.execute(
            "SELECT id, card_id, content, checked, position FROM checklist_items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _checklist_row_to_out(row)


@router.put("/api/board/checklist/{item_id}", response_model=ChecklistItemOut)
def update_checklist_item(
    item_id: int,
    body: UpdateChecklistItemRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        item = conn.execute(
            "SELECT id, card_id FROM checklist_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        bid = get_board_id(conn, username, board_id)
        _require_card(conn, item["card_id"], bid)
        checked_val = None if body.checked is None else (1 if body.checked else 0)
        conn.execute(
            "UPDATE checklist_items SET content = COALESCE(?, content), checked = COALESCE(?, checked) WHERE id = ?",
            (body.content, checked_val, item_id),
        )
        row = conn.execute(
            "SELECT id, card_id, content, checked, position FROM checklist_items WHERE id = ?",
            (item_id,),
        ).fetchone()
    return _checklist_row_to_out(row)


@router.delete("/api/board/checklist/{item_id}")
def delete_checklist_item(
    item_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        item = conn.execute(
            "SELECT id, card_id FROM checklist_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        bid = get_board_id(conn, username, board_id)
        card = conn.execute(
            "SELECT id FROM cards WHERE id = ? AND column_id IN (SELECT id FROM columns WHERE board_id = ?)",
            (item["card_id"], bid),
        ).fetchone()
        if not card:
            raise HTTPException(status_code=403, detail="Access denied")
        conn.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
    return {"ok": True}


# --- Cards ---

@router.post("/api/board/cards", response_model=CardOut)
def create_card(
    body: CreateCardRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        col = conn.execute(
            "SELECT id FROM columns WHERE id = ? AND board_id = ?",
            (body.column_id, bid),
        ).fetchone()
        if not col:
            raise HTTPException(status_code=404, detail="Column not found")
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id = ? AND archived = 0",
            (body.column_id,),
        ).fetchone()[0]
        labels_json = json.dumps(body.labels)
        cursor = conn.execute(
            "INSERT INTO cards (column_id, title, details, position, priority, due_date, labels) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.column_id, body.title, body.details, max_pos + 1, body.priority, body.due_date, labels_json),
        )
        card = conn.execute(
            "SELECT id, title, details, position, priority, due_date, labels FROM cards WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        d = dict(card)
        d["labels"] = parse_labels(d.get("labels"))
        col_title = conn.execute("SELECT title FROM columns WHERE id = ?", (body.column_id,)).fetchone()["title"]
        log_activity(conn, bid, username, "card_created", f"Created '{body.title}' in {col_title}")
        return CardOut(**d)


@router.put("/api/board/cards/{card_id}", response_model=CardOut)
def update_card(
    card_id: int,
    body: UpdateCardRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        labels_json = json.dumps(body.labels)
        result = conn.execute(
            """UPDATE cards SET title = ?, details = ?, priority = ?, due_date = ?, labels = ?
               WHERE id = ? AND column_id IN (SELECT id FROM columns WHERE board_id = ?)""",
            (body.title, body.details, body.priority, body.due_date, labels_json, card_id, bid),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Card not found")
        card = conn.execute(
            "SELECT id, title, details, position, priority, due_date, labels FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        d = dict(card)
        d["labels"] = parse_labels(d.get("labels"))
        return CardOut(**d)


@router.delete("/api/board/cards/{card_id}")
def delete_card(
    card_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        card_row = conn.execute(
            """SELECT ca.title FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE ca.id = ? AND co.board_id = ?""",
            (card_id, bid),
        ).fetchone()
        if not card_row:
            raise HTTPException(status_code=404, detail="Card not found")
        log_activity(conn, bid, username, "card_deleted", f"Deleted '{card_row['title']}'")
        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    return {"ok": True}


@router.put("/api/board/cards/{card_id}/move")
def move_card(
    card_id: int,
    body: MoveCardRequest,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        card = conn.execute(
            """SELECT id, column_id, position, title, details, priority, due_date, labels FROM cards
               WHERE id = ? AND archived = 0
                 AND column_id IN (SELECT id FROM columns WHERE board_id = ?)""",
            (card_id, bid),
        ).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        col = conn.execute(
            "SELECT id, title FROM columns WHERE id = ? AND board_id = ?",
            (body.column_id, bid),
        ).fetchone()
        if not col:
            raise HTTPException(status_code=404, detail="Column not found")

        old_column_id = card["column_id"]
        old_position = card["position"]

        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        conn.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (old_column_id, old_position),
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM cards WHERE column_id = ? AND archived = 0",
            (body.column_id,),
        ).fetchone()[0]
        position = min(body.position, count)
        conn.execute(
            "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ?",
            (body.column_id, position),
        )
        conn.execute(
            "INSERT INTO cards (id, column_id, title, details, position, priority, due_date, labels) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (card_id, body.column_id, card["title"], card["details"], position,
             card["priority"], card["due_date"], card["labels"]),
        )
        log_activity(conn, bid, username, "card_moved", f"Moved '{card['title']}' to {col['title']}")

    return {"ok": True}


# --- Archive ---

@router.get("/api/board/archived", response_model=list[ArchivedCardOut])
def list_archived(
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        rows = conn.execute(
            """SELECT ca.id, ca.title, ca.details, ca.priority, ca.due_date, ca.labels,
                      co.id AS column_id, co.title AS column_title
               FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE co.board_id = ? AND ca.archived = 1
               ORDER BY ca.id DESC""",
            (bid,),
        ).fetchall()
    return [
        ArchivedCardOut(**{**dict(r), "labels": parse_labels(r["labels"])})
        for r in rows
    ]


@router.put("/api/board/cards/{card_id}/archive")
def archive_card(
    card_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        card = conn.execute(
            """SELECT ca.title, ca.column_id, ca.position FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE ca.id = ? AND co.board_id = ? AND ca.archived = 0""",
            (card_id, bid),
        ).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        conn.execute("UPDATE cards SET archived = 1 WHERE id = ?", (card_id,))
        conn.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND archived = 0 AND position > ?",
            (card["column_id"], card["position"]),
        )
        log_activity(conn, bid, username, "card_archived", f"Archived '{card['title']}'")
    return {"ok": True}


@router.put("/api/board/cards/{card_id}/restore")
def restore_card(
    card_id: int,
    board_id: Optional[int] = Query(None),
    username: str = Depends(get_current_user),
):
    with db() as conn:
        bid = get_board_id(conn, username, board_id)
        card = conn.execute(
            """SELECT ca.title, ca.column_id FROM cards ca
               JOIN columns co ON ca.column_id = co.id
               WHERE ca.id = ? AND co.board_id = ? AND ca.archived = 1""",
            (card_id, bid),
        ).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        count = conn.execute(
            "SELECT COUNT(*) FROM cards WHERE column_id = ? AND archived = 0",
            (card["column_id"],),
        ).fetchone()[0]
        conn.execute(
            "UPDATE cards SET archived = 0, position = ? WHERE id = ?",
            (count, card_id),
        )
        log_activity(conn, bid, username, "card_restored", f"Restored '{card['title']}'")
    return {"ok": True}
