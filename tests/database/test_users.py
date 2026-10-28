"""Tests for the user queries in db.py."""

import pytest

import db

NEW_ID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"


def _rows(pool):
    with pool.connection() as conn:
        users = conn.execute("SELECT email, api_key FROM users ORDER BY email").fetchall()
        ids = conn.execute("SELECT id, email, is_active FROM user_id ORDER BY id").fetchall()
    return users, ids


def test_register_user_creates_user_and_id(test_pool):
    db._register_user("new@example.com", "new-key", NEW_ID)

    assert _rows(test_pool) == (
        [("new@example.com", "new-key")],
        [(NEW_ID, "new@example.com", True)],
    )


def test_register_user_adds_id_to_existing_user(seed, test_pool):
    db._register_user(seed.user_email, seed.user_api_key, NEW_ID)

    users, ids = _rows(test_pool)
    assert users == [(seed.user_email, seed.user_api_key)]
    assert (NEW_ID, seed.user_email, True) in ids


# Each case builds (email, api_key, user_id) from the seed data.
@pytest.mark.parametrize(
    "conflict",
    [
        pytest.param(lambda s: (s.user_email, "different-key", NEW_ID), id="email-with-different-api-key"),
        pytest.param(lambda s: ("other@example.com", s.user_api_key, NEW_ID), id="api-key-of-another-email"),
        pytest.param(lambda s: (s.user_email, s.user_api_key, s.active_user), id="duplicate-user-id"),
    ],
)
def test_register_user_rejects_conflicts_without_writing(seed, test_pool, conflict):
    before = _rows(test_pool)

    with pytest.raises(ValueError):
        db._register_user(*conflict(seed))

    # The user and user ID are written in one transaction, so nothing is left behind.
    assert _rows(test_pool) == before


@pytest.mark.parametrize(
    "did_field, expected",
    [("active_user", True), ("inactive_user", False), ("unknown", False)],
)
def test_get_user_active_status(seed, did_field, expected):
    assert db._get_user_active_status(getattr(seed, did_field)) is expected


def test_set_user_active_status(seed):
    assert db._set_user_active_status(seed.active_user, False) is True
    assert db._get_user_active_status(seed.active_user) is False

    assert db._set_user_active_status(seed.unknown, False) is False


def test_get_all_users(seed):
    users = db._get_all_users()

    assert sorted(users, key=lambda u: u["user_id"]) == sorted(
        [
            {"user_id": seed.active_user, "is_active": True},
            {"user_id": seed.inactive_user, "is_active": False},
        ],
        key=lambda u: u["user_id"],
    )
