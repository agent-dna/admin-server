"""Tests for the tool queries in db.py."""

import pytest

import db

NEW_TOOL_ID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"


def _rows(pool):
    with pool.connection() as conn:
        return conn.execute("SELECT tool_id, tool_name, is_active FROM tools ORDER BY tool_id").fetchall()


def test_add_tool_stores_active_tool(test_pool):
    db.add_tool(NEW_TOOL_ID, "new-tool")

    assert _rows(test_pool) == [(NEW_TOOL_ID, "new-tool", True)]


def test_add_tool_rejects_duplicate_id(seed, test_pool):
    before = _rows(test_pool)

    with pytest.raises(db.ToolConflictError):
        db.add_tool(seed.active_tool, "another-name")

    assert _rows(test_pool) == before


@pytest.mark.parametrize(
    "did_field, expected",
    [("active_tool", True), ("inactive_tool", False), ("unknown", False)],
)
def test_is_tool_whitelisted(seed, did_field, expected):
    assert db.is_tool_whitelisted(getattr(seed, did_field)) is expected


def test_set_tool_active_status(seed):
    assert db.set_tool_active_status(seed.active_tool, False) is True
    assert db.is_tool_whitelisted(seed.active_tool) is False

    assert db.set_tool_active_status(seed.unknown, False) is False
