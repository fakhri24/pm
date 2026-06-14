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


# --- Labels ---

def test_create_card_with_labels(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    res = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Labeled card", "labels": ["bug", "frontend"]},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["labels"] == ["bug", "frontend"]


def test_update_card_labels(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    card = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Update labels"},
        headers=auth_header(client),
    ).json()
    res = client.put(
        f"/api/board/cards/{card['id']}",
        json={"title": "Update labels", "details": "", "labels": ["backend", "v2"]},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert set(res.json()["labels"]) == {"backend", "v2"}


def test_card_labels_default_empty(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    for col in board["columns"]:
        for card in col["cards"]:
            assert isinstance(card["labels"], list)


def test_board_includes_card_labels(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Tagged", "labels": ["release"]},
        headers=auth_header(client),
    )
    board2 = client.get("/api/board", headers=auth_header(client)).json()
    all_labels = [
        card["labels"]
        for col in board2["columns"]
        for card in col["cards"]
    ]
    flat = [l for labels in all_labels for l in labels]
    assert "release" in flat


# --- Search ---

def test_search_by_title(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Unique search card xyz"},
        headers=auth_header(client),
    )
    res = client.get("/api/board/search?q=xyz", headers=auth_header(client))
    assert res.status_code == 200
    results = res.json()
    assert any("xyz" in r["title"].lower() for r in results)


def test_search_by_details(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Plain card", "details": "Unique detail qwerty123"},
        headers=auth_header(client),
    )
    res = client.get("/api/board/search?q=qwerty123", headers=auth_header(client))
    assert res.status_code == 200
    results = res.json()
    assert any("qwerty123" in r["details"].lower() for r in results)


def test_search_returns_column_info(client):
    res = client.get("/api/board/search?q=card", headers=auth_header(client))
    assert res.status_code == 200
    if res.json():
        result = res.json()[0]
        assert "column_id" in result
        assert "column_title" in result


def test_search_case_insensitive(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "CaseSensitiveTest UPPER"},
        headers=auth_header(client),
    )
    res = client.get("/api/board/search?q=casesensitivetest", headers=auth_header(client))
    assert res.status_code == 200
    assert any("casesensitivetest" in r["title"].lower() for r in res.json())


def test_search_requires_auth(client):
    assert client.get("/api/board/search?q=test").status_code == 401


# --- Board Stats ---

def test_board_stats(client):
    res = client.get("/api/board/stats", headers=auth_header(client))
    assert res.status_code == 200
    stats = res.json()
    assert "total" in stats
    assert "overdue" in stats
    assert "urgent" in stats
    assert "columns" in stats
    assert isinstance(stats["columns"], list)
    assert len(stats["columns"]) >= 5


def test_board_stats_requires_auth(client):
    assert client.get("/api/board/stats").status_code == 401


def test_board_stats_urgent_count(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    before = client.get("/api/board/stats", headers=auth_header(client)).json()["urgent"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Fire drill", "priority": "urgent"},
        headers=auth_header(client),
    )
    after = client.get("/api/board/stats", headers=auth_header(client)).json()["urgent"]
    assert after == before + 1
