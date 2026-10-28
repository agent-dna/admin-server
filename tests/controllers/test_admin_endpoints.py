"""Tests for the admin endpoints, with the DB and Rubix signer mocked:

POST /agent-admin/v1/register-admin
POST /agent-admin/v1/login
POST /agent-admin/v1/update-password
"""

from unittest.mock import MagicMock

import jwt
import pytest

import services
from db import AdminConflictError
from security import JWT_ALGORITHM, hash_password, verify_password

ADMIN_DID = "bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
USERNAME = "admin-user"
PASSWORD = "S3cure-pass!"
REGISTER = {"username": USERNAME, "org": "org-1", "password": PASSWORD, "email": "admin@example.com"}
JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long"


@pytest.fixture
def signer(monkeypatch):
    """Mock the Rubix client and signer; the signer's DID is ADMIN_DID."""
    mock = MagicMock()
    mock.return_value.did = ADMIN_DID
    monkeypatch.setattr(services, "RubixClient", MagicMock())
    monkeypatch.setattr(services, "Signer", mock)
    return mock


def test_register_admin_stores_hashed_password_and_returns_did(client, signer, monkeypatch):
    add_admin = MagicMock()
    monkeypatch.setattr(services, "add_admin", add_admin)

    body = client.post("/agent-admin/v1/register-admin", json=REGISTER).json()

    assert body == {"status": True, "message": ADMIN_DID, "data": None}
    did, username, org, password_hash, email = add_admin.call_args.args
    assert (did, username, org, email) == (ADMIN_DID, USERNAME, "org-1", "admin@example.com")
    assert password_hash != PASSWORD and verify_password(PASSWORD, password_hash)


def test_register_admin_conflict(client, signer, monkeypatch):
    monkeypatch.setattr(services, "add_admin", MagicMock(side_effect=AdminConflictError("already registered")))

    body = client.post("/agent-admin/v1/register-admin", json=REGISTER).json()

    assert body["status"] is False
    assert "conflict" in body["message"]


def test_register_admin_signer_failure_stores_nothing(client, signer, monkeypatch):
    signer.side_effect = RuntimeError("chain unreachable")
    add_admin = MagicMock()
    monkeypatch.setattr(services, "add_admin", add_admin)

    body = client.post("/agent-admin/v1/register-admin", json=REGISTER).json()

    assert body["status"] is False
    add_admin.assert_not_called()


def test_login_returns_jwt_with_admin_claims(client, monkeypatch):
    monkeypatch.setattr(services.settings, "jwt_secret", JWT_SECRET)
    admin = {"did": ADMIN_DID, "org": "org-1", "password": hash_password(PASSWORD)}
    monkeypatch.setattr(services, "get_admin_by_username", MagicMock(return_value=admin))

    body = client.post("/agent-admin/v1/login", json={"username": USERNAME, "password": PASSWORD}).json()

    assert body["status"] is True
    claims = jwt.decode(body["data"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert (claims["sub"], claims["did"], claims["org_id"]) == (USERNAME, ADMIN_DID, "org-1")


@pytest.mark.parametrize(
    "admin",
    [
        pytest.param(None, id="unknown-username"),
        pytest.param({"did": ADMIN_DID, "org": "org-1", "password": hash_password("other")}, id="wrong-password"),
    ],
)
def test_login_failures_share_one_message(client, monkeypatch, admin):
    # Same message for both, so responses can't be used to find valid usernames.
    monkeypatch.setattr(services, "get_admin_by_username", MagicMock(return_value=admin))

    body = client.post("/agent-admin/v1/login", json={"username": USERNAME, "password": PASSWORD}).json()

    assert body == {"status": False, "message": "Invalid username or password", "data": None}


def test_update_password_stores_new_hash(client, monkeypatch):
    monkeypatch.setattr(services, "get_admin_by_username", MagicMock(return_value={"did": ADMIN_DID}))
    update = MagicMock(return_value=True)
    monkeypatch.setattr(services, "update_admin_password", update)

    body = client.post(
        "/agent-admin/v1/update-password", json={"username": USERNAME, "new_password": "N3w-pass!"}
    ).json()

    assert body["status"] is True
    username, password_hash = update.call_args.args
    assert username == USERNAME and verify_password("N3w-pass!", password_hash)


def test_update_password_unknown_admin(client, monkeypatch):
    monkeypatch.setattr(services, "get_admin_by_username", MagicMock(return_value=None))
    update = MagicMock()
    monkeypatch.setattr(services, "update_admin_password", update)

    body = client.post(
        "/agent-admin/v1/update-password", json={"username": "unknown", "new_password": "N3w-pass!"}
    ).json()

    assert body["status"] is False
    update.assert_not_called()


@pytest.mark.parametrize(
    "url, payload, db_function",
    [
        pytest.param("/agent-admin/v1/login", {"username": USERNAME, "password": PASSWORD}, "get_admin_by_username", id="login"),
        pytest.param("/agent-admin/v1/update-password", {"username": USERNAME, "new_password": "x"}, "get_admin_by_username", id="update-password"),
    ],
)
def test_db_error_returns_failed_status(client, monkeypatch, url, payload, db_function):
    monkeypatch.setattr(services, db_function, MagicMock(side_effect=RuntimeError("db down")))

    assert client.post(url, json=payload).json()["status"] is False
