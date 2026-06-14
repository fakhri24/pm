import sqlite3


def log_activity(
    conn: sqlite3.Connection,
    board_id: int,
    username: str,
    action: str,
    description: str,
) -> None:
    conn.execute(
        "INSERT INTO activity_log (board_id, username, action, description) VALUES (?, ?, ?, ?)",
        (board_id, username, action, description),
    )
