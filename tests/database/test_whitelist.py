"""Tests for the whitelist queries in db.py."""

import pytest

import db


@pytest.mark.parametrize(
    "did_field, expected",
    [("active_agent", True), ("inactive_agent", False), ("unknown", False)],
)
def test_is_agent_whitelisted(seed, did_field, expected):
    assert db.is_agent_whitelisted(getattr(seed, did_field)) is expected


def test_get_whitelisted_actors_checks_agents_and_users(seed):
    result = db.get_whitelisted_actors(
        [seed.active_agent, seed.inactive_agent, seed.active_user, seed.inactive_user, seed.unknown]
    )

    assert result == {seed.active_agent, seed.active_user}
