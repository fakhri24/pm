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


def first_card(client):
    board = client.get("/api/board", headers=auth_header(client)).json()
    for col in board["columns"]:
        if col["cards"]:
            return col["cards"][0]
    pytest.skip("No cards available")


def test_archive_requires_auth(client):
    assert client.put("/api/board/cards/1/archive").status_code in (401, 403)
    assert client.get("/api/board/archived").status_code in (401, 403)


def test_archive_removes_card_from_board(client):
    card = first_card(client)
    res = client.put(f"/api/board/cards/{card['id']}/archive", headers=auth_header(client))
    assert res.status_code == 200

    board = client.get("/api/board", headers=auth_header(client)).json()
    ids = [c["id"] for col in board["columns"] for c in col["cards"]]
    assert card["id"] not in ids


def test_archived_card_appears_in_list(client):
    archived = client.get("/api/board/archived", headers=auth_header(client)).json()
    assert len(archived) >= 1
    assert "column_title" in archived[0]


def test_restore_returns_card_to_board(client):
    archived = client.get("/api/board/archived", headers=auth_header(client)).json()
    card_id = archived[0]["id"]
    res = client.put(f"/api/board/cards/{card_id}/restore", headers=auth_header(client))
    assert res.status_code == 200

    board = client.get("/api/board", headers=auth_header(client)).json()
    ids = [c["id"] for col in board["columns"] for c in col["cards"]]
    assert card_id in ids

    archived_after = client.get("/api/board/archived", headers=auth_header(client)).json()
    assert card_id not in [c["id"] for c in archived_after]


def test_archive_unknown_card_404(client):
    assert client.put("/api/board/cards/99999/archive", headers=auth_header(client)).status_code == 404


def test_restore_active_card_404(client):
    card = first_card(client)
    res = client.put(f"/api/board/cards/{card['id']}/restore", headers=auth_header(client))
    assert res.status_code == 404


def test_archived_excluded_from_stats_and_search(client):
    headers = auth_header(client)
    # Create a uniquely-named card, archive it, then confirm search and stats skip it
    board = client.get("/api/board", headers=headers).json()
    col_id = board["columns"][0]["id"]
    card = client.post(
        "/api/board/cards",
        json={"column_id": col_id, "title": "ArchiveSearchProbe"},
        headers=headers,
    ).json()

    stats_before = client.get("/api/board/stats", headers=headers).json()
    client.put(f"/api/board/cards/{card['id']}/archive", headers=headers)

    results = client.get("/api/board/search?q=archivesearchprobe", headers=headers).json()
    assert results == []

    stats_after = client.get("/api/board/stats", headers=headers).json()
    assert stats_after["total"] == stats_before["total"] - 1


def test_archived_card_cannot_be_moved(client):
    headers = auth_header(client)
    archived = client.get("/api/board/archived", headers=headers).json()
    card_id = archived[0]["id"]
    board = client.get("/api/board", headers=headers).json()
    col_id = board["columns"][0]["id"]
    res = client.put(
        f"/api/board/cards/{card_id}/move",
        json={"column_id": col_id, "position": 0},
        headers=headers,
    )
    assert res.status_code == 404
