import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use a temp DB for tests
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")

from main import app  # noqa: E402 — must be after env var
from conftest import auth_header  # noqa: F401


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


# --- Health & Auth ---

def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_success(client):
    res = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password(client):
    assert client.post("/api/auth/login", json={"username": "user", "password": "wrong"}).status_code == 401


def test_login_wrong_username(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password"}).status_code == 401


def test_me_authenticated(client):
    res = client.get("/api/auth/me", headers=auth_header(client))
    assert res.status_code == 200
    assert res.json()["username"] == "user"


def test_me_unauthenticated(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_invalid_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert res.status_code == 401


def test_logout_requires_auth(client):
    assert client.post("/api/auth/logout").status_code == 401
    assert client.post("/api/auth/logout", headers=auth_header(client)).status_code == 200


# --- Board ---

def test_get_board(client):
    res = client.get("/api/board", headers=auth_header(client))
    assert res.status_code == 200
    board = res.json()
    assert board["name"] == "My Board"
    assert len(board["columns"]) == 5
    titles = [c["title"] for c in board["columns"]]
    assert titles == ["Backlog", "Discovery", "In Progress", "Review", "Done"]


def test_get_board_unauthenticated(client):
    assert client.get("/api/board").status_code == 401


# --- Columns ---

def test_rename_column(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.put(f"/api/board/columns/{col_id}", json={"title": "Todo"}, headers=auth_header(client))
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    assert board2["columns"][0]["title"] == "Todo"


def test_rename_column_wrong_id(client):
    res = client.put("/api/board/columns/99999", json={"title": "X"}, headers=auth_header(client))
    assert res.status_code == 404


def test_rename_column_unauthenticated(client):
    assert client.put("/api/board/columns/1", json={"title": "X"}).status_code == 401


# --- Cards ---

def test_create_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "New card", "details": "Some details"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    card = res.json()
    assert card["title"] == "New card"
    assert card["details"] == "Some details"


def test_create_card_wrong_column(client):
    res = client.post(
        "/api/board/cards",
        json={"column_id": 99999, "title": "X"},
        headers=auth_header(client),
    )
    assert res.status_code == 404


def test_create_card_unauthenticated(client):
    assert client.post("/api/board/cards", json={"column_id": 1, "title": "X"}).status_code == 401


def test_create_card_title_too_long(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "x" * 501},
        headers=auth_header(client),
    )
    assert res.status_code == 422


def test_move_card_negative_position_rejected(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col = board["columns"][0]
    card_id = col["cards"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": col["id"], "position": -1},
        headers=auth_header(client),
    )
    assert res.status_code == 422


def test_update_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    card_id = board["columns"][0]["cards"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}",
        json={"title": "Updated", "details": "Updated details"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Updated"


def test_delete_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    card_id = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "To delete"},
        headers=auth_header(client),
    ).json()["id"]
    res = client.delete(f"/api/board/cards/{card_id}", headers=auth_header(client))
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    ids = [c["id"] for col in board2["columns"] for c in col["cards"]]
    assert card_id not in ids


def test_delete_card_wrong_id(client):
    assert client.delete("/api/board/cards/99999", headers=auth_header(client)).status_code == 404


def test_move_card_within_column(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    backlog = next(c for c in board["columns"] if len(c["cards"]) >= 2)
    card_id = backlog["cards"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": backlog["id"], "position": 1},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    updated_col = next(c for c in board2["columns"] if c["id"] == backlog["id"])
    assert updated_col["cards"][1]["id"] == card_id


def test_move_card_cross_column(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    src_col = next(c for c in board["columns"] if c["cards"])
    dst_col = next(c for c in board["columns"] if c["id"] != src_col["id"])
    card_id = src_col["cards"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": dst_col["id"], "position": 0},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    dst_updated = next(c for c in board2["columns"] if c["id"] == dst_col["id"])
    assert dst_updated["cards"][0]["id"] == card_id


def test_move_card_position_clamped(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    src_col = next(c for c in board["columns"] if c["cards"])
    dst_col = next(c for c in board["columns"] if c["id"] != src_col["id"])
    card_id = src_col["cards"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": dst_col["id"], "position": 999},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    dst_updated = next(c for c in board2["columns"] if c["id"] == dst_col["id"])
    assert dst_updated["cards"][-1]["id"] == card_id
    positions = [c["position"] for c in dst_updated["cards"]]
    assert positions == list(range(len(positions)))
