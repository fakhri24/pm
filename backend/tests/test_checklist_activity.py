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


def get_first_card_id(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    for col in board["columns"]:
        if col["cards"]:
            return col["cards"][0]["id"]
    pytest.skip("No cards available")


def get_first_col_id(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    return board["columns"][0]["id"]


# --- Checklist ---

def test_get_checklist_empty(client):
    card_id = get_first_card_id(client)
    res = client.get(f"/api/board/cards/{card_id}/checklist", headers=auth_header(client))
    assert res.status_code == 200
    assert res.json() == []


def test_add_checklist_item(client):
    card_id = get_first_card_id(client)
    res = client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": "Write tests"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    item = res.json()
    assert item["content"] == "Write tests"
    assert item["checked"] is False
    assert item["card_id"] == card_id
    assert "id" in item


def test_get_checklist_has_item(client):
    card_id = get_first_card_id(client)
    client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": "Another item"},
        headers=auth_header(client),
    )
    res = client.get(f"/api/board/cards/{card_id}/checklist", headers=auth_header(client))
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_toggle_checklist_item(client):
    card_id = get_first_card_id(client)
    item = client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": "Toggle me"},
        headers=auth_header(client),
    ).json()
    res = client.put(
        f"/api/board/checklist/{item['id']}",
        json={"checked": True},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["checked"] is True


def test_update_checklist_item_content(client):
    card_id = get_first_card_id(client)
    item = client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": "Old text"},
        headers=auth_header(client),
    ).json()
    res = client.put(
        f"/api/board/checklist/{item['id']}",
        json={"content": "New text"},
        headers=auth_header(client),
    )
    assert res.status_code == 200
    assert res.json()["content"] == "New text"


def test_delete_checklist_item(client):
    card_id = get_first_card_id(client)
    item = client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": "Delete me"},
        headers=auth_header(client),
    ).json()
    res = client.delete(f"/api/board/checklist/{item['id']}", headers=auth_header(client))
    assert res.status_code == 200
    items = client.get(f"/api/board/cards/{card_id}/checklist", headers=auth_header(client)).json()
    assert all(i["id"] != item["id"] for i in items)


def test_checklist_wrong_card_404(client):
    res = client.get("/api/board/cards/99999/checklist", headers=auth_header(client))
    assert res.status_code == 404


def test_checklist_requires_auth(client):
    card_id = get_first_card_id(client)
    assert client.get(f"/api/board/cards/{card_id}/checklist").status_code == 401
    assert client.post(f"/api/board/cards/{card_id}/checklist", json={"content": "x"}).status_code == 401


def test_checklist_empty_content_rejected(client):
    card_id = get_first_card_id(client)
    res = client.post(
        f"/api/board/cards/{card_id}/checklist",
        json={"content": ""},
        headers=auth_header(client),
    )
    assert res.status_code == 422


def test_checklist_items_ordered_by_position(client):
    card_id = get_first_card_id(client)
    for text in ["First", "Second", "Third"]:
        client.post(
            f"/api/board/cards/{card_id}/checklist",
            json={"content": text},
            headers=auth_header(client),
        )
    items = client.get(f"/api/board/cards/{card_id}/checklist", headers=auth_header(client)).json()
    positions = [i["position"] for i in items]
    assert positions == sorted(positions)


# --- Activity log ---

def test_activity_requires_auth(client):
    assert client.get("/api/board/activity").status_code == 401


def test_activity_log_after_card_create(client):
    # Create a card to generate activity
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "Activity Test Card", "details": ""},
        headers=auth_header(client),
    )
    res = client.get("/api/board/activity", headers=auth_header(client))
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) > 0
    assert any(e["action"] == "card_created" for e in entries)
    assert any("Activity Test Card" in e["description"] for e in entries)


def test_activity_log_after_card_delete(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    col_id = board["columns"][0]["id"]
    card = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "ToDelete", "details": ""},
        headers=auth_header(client),
    ).json()
    client.delete(f"/api/board/cards/{card['id']}", headers=auth_header(client))
    entries = client.get("/api/board/activity", headers=auth_header(client)).json()
    assert any(e["action"] == "card_deleted" for e in entries)


def test_activity_log_after_card_move(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    card_id = board["columns"][0]["cards"][0]["id"]
    target_col = board["columns"][1]["id"]
    client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": target_col, "position": 0},
        headers=auth_header(client),
    )
    entries = client.get("/api/board/activity", headers=auth_header(client)).json()
    assert any(e["action"] == "card_moved" for e in entries)


def test_activity_log_after_column_add(client):
    client.post(
        "/api/board/columns",
        json={"title": "New Column"},
        headers=auth_header(client),
    )
    entries = client.get("/api/board/activity", headers=auth_header(client)).json()
    assert any(e["action"] == "column_added" for e in entries)


def test_activity_entries_ordered_newest_first(client):
    entries = client.get("/api/board/activity", headers=auth_header(client)).json()
    if len(entries) >= 2:
        dates = [e["created_at"] for e in entries]
        assert dates == sorted(dates, reverse=True)


def test_activity_limit_param(client):
    res = client.get("/api/board/activity?limit=2", headers=auth_header(client))
    assert res.status_code == 200
    assert len(res.json()) <= 2


def test_activity_entry_fields(client):
    entries = client.get("/api/board/activity", headers=auth_header(client)).json()
    assert len(entries) > 0
    e = entries[0]
    assert all(k in e for k in ("id", "board_id", "username", "action", "description", "created_at"))
