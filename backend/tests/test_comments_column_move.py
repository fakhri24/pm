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


# --- Column reordering ---

def test_move_column(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    cols = board["columns"]
    assert len(cols) >= 3
    first_id = cols[0]["id"]
    res = client.put(
        f"/api/board/columns/{first_id}/move",
        json={"position": 2},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    positions = {c["id"]: c["position"] for c in board2["columns"]}
    assert positions[first_id] == 2


def test_move_column_to_same_position(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col = board["columns"][0]
    res = client.put(
        f"/api/board/columns/{col['id']}/move",
        json={"position": col["position"]},
        headers=auth_header(client),
    )
    assert res.status_code == 200


def test_move_column_clamped(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    total = len(board["columns"])
    res = client.put(
        f"/api/board/columns/{col_id}/move",
        json={"position": 999},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    positions = {c["id"]: c["position"] for c in board2["columns"]}
    assert positions[col_id] == total - 1


def test_move_column_wrong_id(client):
    res = client.put(
        "/api/board/columns/99999/move",
        json={"position": 0},
        headers=auth_header(client),
    )
    assert res.status_code == 404


def test_move_column_requires_auth(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.put(f"/api/board/columns/{col_id}/move", json={"position": 0})
    assert res.status_code == 401


def test_column_positions_remain_gapless(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][2]["id"]
    client.put(
        f"/api/board/columns/{col_id}/move",
        json={"position": 0},
        headers=auth_header(client),
    )
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    positions = sorted(c["position"] for c in board2["columns"])
    assert positions == list(range(len(board2["columns"])))


# --- Comments ---

def get_card_id(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    for col in board["columns"]:
        if col["cards"]:
            return col["cards"][0]["id"]
    pytest.skip("No cards available")


def test_add_comment(client):
    card_id = get_card_id(client)
    res = client.post(
        f"/api/board/cards/{card_id}/comments",
        json={"content": "This is a comment"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    comment = res.json()
    assert comment["content"] == "This is a comment"
    assert comment["card_id"] == card_id
    assert "created_at" in comment
    assert "id" in comment


def test_get_comments(client):
    card_id = get_card_id(client)
    client.post(
        f"/api/board/cards/{card_id}/comments",
        json={"content": "Comment A"},
        headers=auth_header(client),
    )
    client.post(
        f"/api/board/cards/{card_id}/comments",
        json={"content": "Comment B"},
        headers=auth_header(client),
    )
    res = client.get(
        f"/api/board/cards/{card_id}/comments",
        headers=auth_header(client),
    )
    assert res.status_code == 200
    comments = res.json()
    contents = [c["content"] for c in comments]
    assert "Comment A" in contents
    assert "Comment B" in contents


def test_delete_comment(client):
    card_id = get_card_id(client)
    comment = client.post(
        f"/api/board/cards/{card_id}/comments",
        json={"content": "To be deleted"},
        headers=auth_header(client),
    ).json()
    res = client.delete(
        f"/api/board/comments/{comment['id']}",
        headers=auth_header(client),
    )
    assert res.status_code == 200
    comments = client.get(
        f"/api/board/cards/{card_id}/comments",
        headers=auth_header(client),
    ).json()
    assert all(c["id"] != comment["id"] for c in comments)


def test_delete_comment_wrong_id(client):
    res = client.delete("/api/board/comments/99999", headers=auth_header(client))
    assert res.status_code == 404


def test_comments_require_auth(client):
    card_id = get_card_id(client)
    assert client.get(f"/api/board/cards/{card_id}/comments").status_code == 401
    assert client.post(f"/api/board/cards/{card_id}/comments", json={"content": "x"}).status_code == 401


def test_comment_empty_content_rejected(client):
    card_id = get_card_id(client)
    res = client.post(
        f"/api/board/cards/{card_id}/comments",
        json={"content": ""},
        headers=auth_header(client),
    )
    assert res.status_code == 422


def test_comments_ordered_by_created_at(client):
    card_id = get_card_id(client)
    for i in range(3):
        client.post(
            f"/api/board/cards/{card_id}/comments",
            json={"content": f"Comment {i}"},
            headers=auth_header(client),
        )
    comments = client.get(
        f"/api/board/cards/{card_id}/comments",
        headers=auth_header(client),
    ).json()
    dates = [c["created_at"] for c in comments]
    assert dates == sorted(dates)
