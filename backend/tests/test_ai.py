import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402
from conftest import auth_header  # noqa: F401


@pytest.fixture(scope="module")
def client():
    # Use a dedicated temp DB so we don't pollute other test modules
    saved = os.environ.get("DB_PATH")
    db_path = tempfile.mktemp(suffix=".db")
    os.environ["DB_PATH"] = db_path
    with TestClient(app) as c:
        yield c
    if saved is not None:
        os.environ["DB_PATH"] = saved
    elif "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]


# --- Chat route tests (mocked AI) ---

def test_chat_plain_message(client):
    with patch("routers.ai_router.chat_ai", return_value={"message": "Hello there!", "board_update": None}):
        res = client.post(
            "/api/ai/chat",
            json={"message": "Hi", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "Hello there!"
    assert data["board_update"] is None
    assert data["board"] is not None
    assert len(data["board"]["columns"]) == 5


def test_chat_requires_auth(client):
    assert client.post("/api/ai/chat", json={"message": "Hi", "history": []}).status_code == 401


def test_chat_create_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "Created a card for you.",
        "board_update": [{"action": "create_card", "column_id": col_id, "title": "AI Task", "details": "Added by AI"}],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "add a card", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "Created a card for you."
    titles = [c["title"] for c in data["board"]["columns"][0]["cards"]]
    assert "AI Task" in titles


def test_chat_rename_column(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "Renamed the column.",
        "board_update": [{"action": "rename_column", "column_id": col_id, "title": "Sprint"}],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "rename first column", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    assert res.json()["board"]["columns"][0]["title"] == "Sprint"


def test_chat_move_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    card_id = board["columns"][0]["cards"][0]["id"]
    target_col_id = board["columns"][1]["id"]

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "Moved the card.",
        "board_update": [{"action": "move_card", "card_id": card_id, "column_id": target_col_id, "position": 0}],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "move card", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    col1_card_ids = [c["id"] for c in res.json()["board"]["columns"][0]["cards"]]
    col2_card_ids = [c["id"] for c in res.json()["board"]["columns"][1]["cards"]]
    assert card_id not in col1_card_ids
    assert card_id in col2_card_ids


def test_chat_create_card_with_metadata(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "Created an urgent card.",
        "board_update": [{
            "action": "create_card", "column_id": col_id, "title": "AI Urgent Task",
            "priority": "urgent", "due_date": "2026-07-01", "labels": ["bug", "ai"],
        }],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "add urgent card", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    cards = res.json()["board"]["columns"][0]["cards"]
    card = next(c for c in cards if c["title"] == "AI Urgent Task")
    assert card["priority"] == "urgent"
    assert card["due_date"] == "2026-07-01"
    assert card["labels"] == ["bug", "ai"]


def test_chat_partial_update_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    card = board["columns"][0]["cards"][0]
    original_title = card["title"]

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "Set priority.",
        "board_update": [{"action": "update_card", "card_id": card["id"], "priority": "high"}],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "make it high priority", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    updated = next(
        c for col in res.json()["board"]["columns"] for c in col["cards"]
        if c["id"] == card["id"]
    )
    assert updated["priority"] == "high"
    assert updated["title"] == original_title


def test_chat_malformed_ai_response(client):
    with patch("routers.ai_router.chat_ai", side_effect=Exception("AI error")):
        res = client.post(
            "/api/ai/chat",
            json={"message": "break things", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    assert "Sorry" in res.json()["message"]


def test_chat_invalid_action_ignored(client):
    """An action with a bad shape (missing fields, out-of-range position) is dropped,
    not applied, and never crashes the endpoint."""
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    before = len(board["columns"][0]["cards"])

    with patch("routers.ai_router.chat_ai", return_value={
        "message": "ok",
        "board_update": [
            {"action": "create_card"},  # missing column_id/title
            {"action": "move_card", "card_id": 1, "column_id": col_id, "position": -5},  # bad position
            {"action": "bogus_action", "foo": "bar"},  # unknown action
        ],
    }):
        res = client.post(
            "/api/ai/chat",
            json={"message": "do bad things", "history": []},
            headers=auth_header(client),
        )
    assert res.status_code == 200
    assert res.json()["board_update"] is None
    after = len(res.json()["board"]["columns"][0]["cards"])
    assert after == before
