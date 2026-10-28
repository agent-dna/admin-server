"""Tests for POST /agent-admin/v1/whitelist/check, with the DB call mocked."""

from unittest.mock import patch

URL = "/agent-admin/v1/whitelist/check"


ID_A = "bafybeie5nqv6kd3qnfjupgvz34woh3oksc3iau6abmyajn7qvtf6d2ho34"
ID_B = "bafybeicg2rebjoofv4kbyovkw7af3rpiitvnl6i7ckcywaq6xjcxnc2mby"
ID_C = "bafybeiasb5vpmaounyilfuxbd3lryvosl4yefqrfahsb2esg46q6tu6y5q"
ID_UNKNOWN = "bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq"


def test_splits_dids_into_whitelist_and_blacklist(client):
    # Duplicates are dropped, input order is kept, unknown DIDs are blacklisted.
    with patch("services.get_whitelisted_actors", return_value={ID_A, ID_C}) as mock:
        resp = client.post(URL, json={"dids": [ID_C, ID_B, ID_A, ID_C, ID_UNKNOWN]})

    mock.assert_called_once_with([ID_C, ID_B, ID_A, ID_UNKNOWN])
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] is True
    assert body["data"] == {"whitelist": [ID_C, ID_A], "blacklist": [ID_B, ID_UNKNOWN]}


def test_db_error_returns_failed_status(client):
    with patch("services.get_whitelisted_actors", side_effect=RuntimeError("db down")):
        resp = client.post(URL, json={"dids": [ID_A]})

    body = resp.json()
    assert body["status"] is False
    assert body["data"] == {"whitelist": [], "blacklist": []}


def test_rejects_empty_did_list(client):
    assert client.post(URL, json={"dids": []}).status_code == 422
