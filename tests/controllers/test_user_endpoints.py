"""Tests for the user endpoints, with the DB mocked:

POST  /agent-admin/v1/users
PATCH /agent-admin/v1/users/{user_id}/status
GET   /agent-admin/v1/users/{user_id}/status
GET   /agent-admin/v1/users
"""

from unittest.mock import MagicMock

import pytest

import services

USER_ID = "bafybeiasb5vpmaounyilfuxbd3lryvosl4yefqrfahsb2esg46q6tu6y5q"
EMAIL = "user@example.com"
API_KEY = "user-api-key"
REGISTER = {"email": EMAIL, "user_id": USER_ID, "api_key": API_KEY}


def test_register_user_passes_fields_in_order(client, monkeypatch):
    # Guards against the (email, api_key, user_id) argument order getting mixed up.
    register = MagicMock()
    monkeypatch.setattr(services, "_register_user", register)

    body = client.post("/agent-admin/v1/users", json=REGISTER).json()

    assert body == {"status": True, "message": "user registered successfully", "data": None}
    register.assert_called_once_with(EMAIL, API_KEY, USER_ID)


def test_register_user_conflict(client, monkeypatch):
    error = ValueError("The email is already registered with a different API key")
    monkeypatch.setattr(services, "_register_user", MagicMock(side_effect=error))

    body = client.post("/agent-admin/v1/users", json=REGISTER).json()

    assert body["status"] is False
    assert str(error) in body["message"]


@pytest.mark.parametrize("is_active, word", [(True, "whitelisted"), (False, "blacklisted")])
def test_update_user_status(client, monkeypatch, is_active, word):
    set_status = MagicMock(return_value=True)
    monkeypatch.setattr(services, "_set_user_active_status", set_status)

    body = client.patch(f"/agent-admin/v1/users/{USER_ID}/status", json={"is_active": is_active}).json()

    assert body == {"status": True, "message": f"user is {word} successfully", "data": True}
    set_status.assert_called_once_with(USER_ID, is_active)


def test_get_user_status(client, monkeypatch):
    lookup = MagicMock(return_value=True)
    monkeypatch.setattr(services, "_get_user_active_status", lookup)

    body = client.get(f"/agent-admin/v1/users/{USER_ID}/status").json()

    assert body["data"] is True
    lookup.assert_called_once_with(USER_ID)


@pytest.mark.parametrize(
    "users, message",
    [
        pytest.param([{"user_id": USER_ID, "is_active": True}], "users fetched successfully", id="some"),
        pytest.param([], "no users found", id="none"),
    ],
)
def test_list_users(client, monkeypatch, users, message):
    monkeypatch.setattr(services, "_get_all_users", MagicMock(return_value=users))

    body = client.get("/agent-admin/v1/users").json()

    assert body == {"status": True, "message": message, "data": users}


@pytest.mark.parametrize(
    "method, url, payload, db_function",
    [
        pytest.param("PATCH", f"/agent-admin/v1/users/{USER_ID}/status", {"is_active": True}, "_set_user_active_status", id="update-status"),
        pytest.param("GET", f"/agent-admin/v1/users/{USER_ID}/status", None, "_get_user_active_status", id="get-status"),
        pytest.param("GET", "/agent-admin/v1/users", None, "_get_all_users", id="list-users"),
    ],
)
def test_db_error_returns_failed_status(client, monkeypatch, method, url, payload, db_function):
    monkeypatch.setattr(services, db_function, MagicMock(side_effect=RuntimeError("db down")))

    assert client.request(method, url, json=payload).json()["status"] is False
