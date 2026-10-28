"""Tests for the admin queries in db.py."""

import pytest

import db


def test_add_admin_stores_admin(test_pool):
    db.add_admin("did-1", "new-admin", "org-1", "hash", "new@example.com")

    with test_pool.connection() as conn:
        row = conn.execute("SELECT did, username, org, password, email FROM admin").fetchone()
    assert row == ("did-1", "new-admin", "org-1", "hash", "new@example.com")


@pytest.mark.parametrize("duplicate", ["did", "username"])
def test_add_admin_rejects_duplicate(seed, duplicate):
    did = seed.admin_did if duplicate == "did" else "other-did"
    username = seed.admin_username if duplicate == "username" else "other-admin"

    with pytest.raises(db.AdminConflictError):
        db.add_admin(did, username, "org-1", "hash", "other@example.com")


def test_get_username_by_did(seed):
    assert db.get_username_by_did(seed.admin_did) == seed.admin_username
    assert db.get_username_by_did(seed.unknown) is None


def test_get_admin_by_username(seed):
    assert db.get_admin_by_username(seed.admin_username) == {
        "did": seed.admin_did,
        "org": seed.admin_org,
        "password": seed.admin_password_hash,
    }
    assert db.get_admin_by_username("unknown-admin") is None


def test_update_admin_password(seed):
    assert db.update_admin_password(seed.admin_username, "new-hash") is True
    assert db.get_admin_by_username(seed.admin_username)["password"] == "new-hash"

    assert db.update_admin_password("unknown-admin", "new-hash") is False
