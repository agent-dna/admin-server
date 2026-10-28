"""Tests for the tool endpoints, with the DB mocked:

POST  /agent-admin/v1/tools/register
PATCH /agent-admin/v1/tools/{tool_id}/status
GET   /agent-admin/v1/tools/{tool_id}/status
"""

from unittest.mock import MagicMock

import pytest

import services
from db import ToolConflictError

TOOL_ID = "bafybeihkoviema7g3gxyt6la7vd5ho32ictqbilu3wnlo3rs7ewhnp7lly"
TOOL_NAME = "search-tool"
REGISTER = {"tool_id": TOOL_ID, "tool_name": TOOL_NAME}


def test_register_tool_stores_tool(client, monkeypatch):
    add_tool = MagicMock()
    monkeypatch.setattr(services, "add_tool", add_tool)

    body = client.post("/agent-admin/v1/tools/register", json=REGISTER).json()

    assert body == {"status": True, "message": f"tool '{TOOL_NAME}' registered successfully", "data": None}
    add_tool.assert_called_once_with(TOOL_ID, TOOL_NAME)


def test_register_tool_conflict(client, monkeypatch):
    error = ToolConflictError("already registered")
    monkeypatch.setattr(services, "add_tool", MagicMock(side_effect=error))

    body = client.post("/agent-admin/v1/tools/register", json=REGISTER).json()

    assert body["status"] is False
    assert str(error) in body["message"]


@pytest.mark.parametrize("field", ["tool_id", "tool_name"])
def test_register_tool_rejects_empty_field(client, field):
    response = client.post("/agent-admin/v1/tools/register", json={**REGISTER, field: ""})

    assert response.status_code == 422


@pytest.mark.parametrize("is_active, word", [(True, "whitelisted"), (False, "blacklisted")])
def test_update_tool_status(client, monkeypatch, is_active, word):
    set_status = MagicMock(return_value=True)
    monkeypatch.setattr(services, "set_tool_active_status", set_status)

    body = client.patch(f"/agent-admin/v1/tools/{TOOL_ID}/status", json={"is_active": is_active}).json()

    assert body == {"status": True, "message": f"tool is {word} successfully", "data": None}
    set_status.assert_called_once_with(TOOL_ID, is_active)


def test_update_tool_status_unknown_tool(client, monkeypatch):
    monkeypatch.setattr(services, "set_tool_active_status", MagicMock(return_value=False))

    body = client.patch(f"/agent-admin/v1/tools/{TOOL_ID}/status", json={"is_active": False}).json()

    assert body["status"] is False
    assert "no tool found" in body["message"]


def test_get_tool_status(client, monkeypatch):
    lookup = MagicMock(return_value=True)
    monkeypatch.setattr(services, "is_tool_whitelisted", lookup)

    body = client.get(f"/agent-admin/v1/tools/{TOOL_ID}/status").json()

    assert body == {"status": True, "message": "tool status fetched successfully", "data": True}
    lookup.assert_called_once_with(TOOL_ID)


@pytest.mark.parametrize(
    "method, url, payload, db_function",
    [
        pytest.param("POST", "/agent-admin/v1/tools/register", REGISTER, "add_tool", id="register-tool"),
        pytest.param("PATCH", f"/agent-admin/v1/tools/{TOOL_ID}/status", {"is_active": True}, "set_tool_active_status", id="update-status"),
        pytest.param("GET", f"/agent-admin/v1/tools/{TOOL_ID}/status", None, "is_tool_whitelisted", id="get-status"),
    ],
)
def test_db_error_returns_failed_status(client, monkeypatch, method, url, payload, db_function):
    monkeypatch.setattr(services, db_function, MagicMock(side_effect=RuntimeError("db down")))

    assert client.request(method, url, json=payload).json()["status"] is False
