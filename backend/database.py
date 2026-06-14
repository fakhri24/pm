import os
import sqlite3
from contextlib import contextmanager

INITIAL_COLUMNS = ["Backlog", "Discovery", "In Progress", "Review", "Done"]

BOARD_TEMPLATES = {
    "kanban": INITIAL_COLUMNS,
    "todo": ["To Do", "Doing", "Done"],
    "sprint": ["Sprint Backlog", "In Progress", "Blocked", "In Review", "Done"],
}
INITIAL_CARDS = {
    "Backlog": [
        ("Align roadmap themes", "Draft quarterly themes with impact statements and metrics."),
        ("Gather customer signals", "Review support tags, sales notes, and churn feedback."),
    ],
    "Discovery": [
        ("Prototype analytics view", "Sketch initial dashboard layout and key drill-downs."),
    ],
    "In Progress": [
        ("Refine status language", "Standardize column labels and tone across the board."),
        ("Design card layout", "Add hierarchy and spacing for scanning dense lists."),
    ],
    "Review": [
        ("QA micro-interactions", "Verify hover, focus, and loading states."),
    ],
    "Done": [
        ("Ship marketing page", "Final copy approved and asset pack delivered."),
        ("Close onboarding sprint", "Document release notes and share internally."),
    ],
}


def get_connection() -> sqlite3.Connection:
    db_path = os.environ.get("DB_PATH", "data/kanban.db")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                position INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_id INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL,
                priority TEXT,
                due_date TEXT,
                labels TEXT DEFAULT '[]',
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                checked INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        _migrate(conn)
        _seed_if_empty(conn)


def _migrate(conn: sqlite3.Connection):
    """Apply incremental schema changes on existing databases."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
    if "priority" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN priority TEXT")
    if "due_date" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN due_date TEXT")
    if "labels" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN labels TEXT DEFAULT '[]'")
    if "archived" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")

    # Replace the sentinel password hash with a real bcrypt hash for the default user.
    # Import here to avoid circular dependency at module load time.
    from auth import hash_password, VALID_PASSWORD
    sentinel = "hardcoded"
    row = conn.execute(
        "SELECT id FROM users WHERE username = 'user' AND password_hash = ?", (sentinel,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(VALID_PASSWORD), row["id"]),
        )


def _seed_if_empty(conn: sqlite3.Connection):
    existing = conn.execute("SELECT id FROM users WHERE username = 'user'").fetchone()
    if existing:
        return

    from auth import hash_password, VALID_PASSWORD
    conn.execute(
        "INSERT INTO users (username, password_hash) VALUES ('user', ?)",
        (hash_password(VALID_PASSWORD),),
    )
    user_id = conn.execute("SELECT id FROM users WHERE username = 'user'").fetchone()["id"]
    _create_board_with_defaults(conn, user_id, "My Board", with_samples=True)


def _create_board_with_defaults(
    conn: sqlite3.Connection,
    user_id: int,
    board_name: str,
    template: str = "kanban",
    with_samples: bool = False,
) -> int:
    columns = BOARD_TEMPLATES[template]
    conn.execute("INSERT INTO boards (user_id, name) VALUES (?, ?)", (user_id, board_name))
    board_id = conn.execute(
        "SELECT id FROM boards WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()["id"]
    for col_pos, col_title in enumerate(columns):
        conn.execute(
            "INSERT INTO columns (board_id, title, position) VALUES (?, ?, ?)",
            (board_id, col_title, col_pos),
        )
        if not with_samples:
            continue
        col_id = conn.execute(
            "SELECT id FROM columns WHERE board_id = ? AND position = ?",
            (board_id, col_pos),
        ).fetchone()["id"]
        for card_pos, (card_title, card_details) in enumerate(INITIAL_CARDS.get(col_title, [])):
            conn.execute(
                "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                (col_id, card_title, card_details, card_pos),
            )
    return board_id
