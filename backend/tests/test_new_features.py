import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")

from main import app  # noqa: E402
from conftest import auth_header  # noqa: F401


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- Registration ---

def test_register_new_user(client):
    res = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_register_duplicate_user(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "secret123"})
    res = client.post("/api/auth/register", json={"username": "bob", "password": "secret123"})
    assert res.status_code == 409


def test_register_login_new_user(client):
    client.post("/api/auth/register", json={"username": "carol", "password": "pass123"})
    res = client.post("/api/auth/login", json={"username": "carol", "password": "pass123"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_register_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"username": "dave", "password": "pass123"})
    res = client.post("/api/auth/login", json={"username": "dave", "password": "wrong"})
    assert res.status_code == 401


def test_register_password_too_short(client):
    res = client.post("/api/auth/register", json={"username": "eve", "password": "12345"})
    assert res.status_code == 422


# --- Multiple Boards ---

def test_list_boards(client):
    res = client.get("/api/boards", headers=auth_header(client))
    assert res.status_code == 200
    boards = res.json()
    assert len(boards) >= 1
    assert boards[0]["name"] == "My Board"
    assert "card_count" in boards[0]


def test_create_board(client):
    res = client.post("/api/boards", json={"name": "Sprint 2"}, headers=auth_header(client))
    assert res.status_code == 200
    board = res.json()
    assert board["name"] == "Sprint 2"
    assert "id" in board


def test_create_board_todo_template(client):
    res = client.post(
        "/api/boards",
        json={"name": "Todo Board", "template": "todo"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board = client.get(f"/api/board?board_id={res.json()['id']}", headers=auth_header(client)).json()
    assert [c["title"] for c in board["columns"]] == ["To Do", "Doing", "Done"]
    assert all(c["cards"] == [] for c in board["columns"])


def test_create_board_sprint_template(client):
    res = client.post(
        "/api/boards",
        json={"name": "Sprint Board", "template": "sprint"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board = client.get(f"/api/board?board_id={res.json()['id']}", headers=auth_header(client)).json()
    assert [c["title"] for c in board["columns"]] == [
        "Sprint Backlog", "In Progress", "Blocked", "In Review", "Done",
    ]


def test_create_board_unknown_template(client):
    res = client.post(
        "/api/boards",
        json={"name": "Bad", "template": "nonexistent"},
        headers=auth_header(client),
    )
    assert res.status_code == 400


def test_get_board_by_id(client):
    boards = client.get("/api/boards", headers=auth_header(client)).json()
    second = boards[1]
    res = client.get(f"/api/board?board_id={second['id']}", headers=auth_header(client))
    assert res.status_code == 200
    assert res.json()["name"] == second["name"]


def test_rename_board(client):
    boards = client.get("/api/boards", headers=auth_header(client)).json()
    bid = boards[-1]["id"]
    res = client.put(f"/api/boards/{bid}", json={"name": "Renamed Board"}, headers=auth_header(client))
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed Board"


def test_delete_board(client):
    # Create an extra board then delete it
    client.post("/api/boards", json={"name": "Temp Board"}, headers=auth_header(client))
    boards = client.get("/api/boards", headers=auth_header(client)).json()
    last_id = boards[-1]["id"]
    res = client.delete(f"/api/boards/{last_id}", headers=auth_header(client))
    assert res.status_code == 200
    boards2 = client.get("/api/boards", headers=auth_header(client)).json()
    assert all(b["id"] != last_id for b in boards2)


def test_cannot_delete_last_board(client):
    # Create a fresh user with one board
    token = client.post("/api/auth/register", json={"username": "frank", "password": "pass123"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    boards = client.get("/api/boards", headers=headers).json()
    assert len(boards) == 1
    res = client.delete(f"/api/boards/{boards[0]['id']}", headers=headers)
    assert res.status_code == 400


def test_board_isolation(client):
    # Alice's board should not be visible/modifiable by user
    token_alice = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"}).json()["token"]
    alice_boards = client.get("/api/boards", headers={"Authorization": f"Bearer {token_alice}"}).json()
    alice_board_id = alice_boards[0]["id"]
    # 'user' cannot access alice's board
    res = client.get(f"/api/board?board_id={alice_board_id}", headers=auth_header(client))
    assert res.status_code == 404


# --- Column Management ---

def test_add_column(client):
    res = client.post(
        "/api/board/columns",
        json={"title": "Testing"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    col = res.json()
    assert col["title"] == "Testing"
    assert "id" in col


def test_add_column_appears_in_board(client):
    client.post("/api/board/columns", json={"title": "QA"}, headers=auth_header(client))
    board = client.get("/api/board", headers=auth_header(client)).json()
    titles = [c["title"] for c in board["columns"]]
    assert "QA" in titles


def test_delete_column(client):
    # Add a column then delete it
    col = client.post(
        "/api/board/columns", json={"title": "Temp Col"}, headers=auth_header(client)
    ).json()
    res = client.delete(f"/api/board/columns/{col['id']}", headers=auth_header(client))
    assert res.status_code == 200
    board = client.get("/api/board", headers=auth_header(client)).json()
    assert all(c["id"] != col["id"] for c in board["columns"])


def test_cannot_delete_last_column(client):
    # Create a new board and get its single columns — then try to delete them all
    token = client.post(
        "/api/auth/register", json={"username": "grace", "password": "pass123"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    boards = client.get("/api/boards", headers=headers).json()
    board_id = boards[0]["id"]
    board = client.get(f"/api/board?board_id={board_id}", headers=headers).json()
    cols = board["columns"]
    # Delete all but the last one
    for col in cols[:-1]:
        client.delete(f"/api/board/columns/{col['id']}?board_id={board_id}", headers=headers)
    last_col_id = board["columns"][-1]["id"]
    res = client.delete(f"/api/board/columns/{last_col_id}?board_id={board_id}", headers=headers)
    assert res.status_code == 400


# --- Card Enhancements: Priority & Due Date ---

def test_create_card_with_priority(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "High priority task", "priority": "high"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["priority"] == "high"


def test_create_card_with_due_date(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Deadline task", "due_date": "2025-12-31"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["due_date"] == "2025-12-31"


def test_update_card_priority_and_due_date(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    card = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Updatable card"},
        headers=auth_header(client),
    ).json()
    res = client.put(
        f"/api/board/cards/{card['id']}",
        json={"title": "Updated", "details": "", "priority": "urgent", "due_date": "2025-06-30"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["priority"] == "urgent"
    assert res.json()["due_date"] == "2025-06-30"


def test_board_cards_include_priority_and_due_date(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    for col in board["columns"]:
        for card in col["cards"]:
            assert "priority" in card
            assert "due_date" in card
