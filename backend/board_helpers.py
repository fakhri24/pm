import json
import sqlite3

from pydantic import TypeAdapter

from models import BoardAction, BoardOut, CardOut, ColumnOut

_action_adapter = TypeAdapter(BoardAction)


def parse_labels(raw) -> list:
    return json.loads(raw or "[]")


def fetch_board(conn: sqlite3.Connection, board_id: int) -> BoardOut:
    board_row = conn.execute(
        "SELECT id, name FROM boards WHERE id = ?", (board_id,)
    ).fetchone()
    columns_rows = conn.execute(
        "SELECT id, title, position FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    columns = []
    for col in columns_rows:
        cards_rows = conn.execute(
            "SELECT id, title, details, position, priority, due_date, labels FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position",
            (col["id"],),
        ).fetchall()
        cards = []
        for c in cards_rows:
            d = dict(c)
            d["labels"] = parse_labels(d.get("labels"))
            cards.append(CardOut(**d))
        columns.append(ColumnOut(
            id=col["id"],
            title=col["title"],
            position=col["position"],
            cards=cards,
        ))
    return BoardOut(id=board_row["id"], name=board_row["name"], columns=columns)


def apply_board_update(conn: sqlite3.Connection, board_id: int, actions: list) -> None:
    for action in actions:
        act = action.get("action")
        if act == "create_card":
            col = conn.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (action["column_id"], board_id),
            ).fetchone()
            if not col:
                continue
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id = ? AND archived = 0",
                (action["column_id"],),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO cards (column_id, title, details, position, priority, due_date, labels) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (action["column_id"], action["title"], action.get("details", ""), max_pos + 1,
                 action.get("priority"), action.get("due_date"), json.dumps(action.get("labels", []))),
            )
        elif act == "update_card":
            sets, params = [], []
            for field in ("title", "details", "priority", "due_date"):
                if action.get(field) is not None:
                    sets.append(f"{field} = ?")
                    params.append(action[field])
            if action.get("labels") is not None:
                sets.append("labels = ?")
                params.append(json.dumps(action["labels"]))
            if not sets:
                continue
            conn.execute(
                f"""UPDATE cards SET {", ".join(sets)}
                    WHERE id = ? AND archived = 0
                      AND column_id IN (SELECT id FROM columns WHERE board_id = ?)""",
                (*params, action["card_id"], board_id),
            )
        elif act == "delete_card":
            conn.execute(
                """DELETE FROM cards
                   WHERE id = ? AND archived = 0
                     AND column_id IN (SELECT id FROM columns WHERE board_id = ?)""",
                (action["card_id"], board_id),
            )
        elif act == "move_card":
            card = conn.execute(
                """SELECT id, column_id, position, title, details, priority, due_date, labels FROM cards
                   WHERE id = ? AND archived = 0
                     AND column_id IN (SELECT id FROM columns WHERE board_id = ?)""",
                (action["card_id"], board_id),
            ).fetchone()
            if not card:
                continue
            col = conn.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (action["column_id"], board_id),
            ).fetchone()
            if not col:
                continue
            old_col, old_pos = card["column_id"], card["position"]
            conn.execute("DELETE FROM cards WHERE id = ?", (action["card_id"],))
            conn.execute(
                "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                (old_col, old_pos),
            )
            # Clamp to the end of the target column so the position sequence stays gapless
            count = conn.execute(
                "SELECT COUNT(*) FROM cards WHERE column_id = ? AND archived = 0",
                (action["column_id"],),
            ).fetchone()[0]
            position = min(action["position"], count)
            conn.execute(
                "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ?",
                (action["column_id"], position),
            )
            conn.execute(
                "INSERT INTO cards (id, column_id, title, details, position, priority, due_date, labels) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (action["card_id"], action["column_id"], card["title"], card["details"], position,
                 card["priority"], card["due_date"], card["labels"]),
            )
        elif act == "rename_column":
            conn.execute(
                "UPDATE columns SET title = ? WHERE id = ? AND board_id = ?",
                (action["title"], action["column_id"], board_id),
            )


def validate_actions(actions) -> list[dict]:
    """Validate the LLM's board_update payload, dropping any malformed action."""
    if not isinstance(actions, list):
        return []
    valid = []
    for action in actions:
        try:
            valid.append(_action_adapter.validate_python(action).model_dump())
        except Exception:
            continue
    return valid
