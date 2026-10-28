"""Tests for the whitelist queries in db.py."""

import db


def test_get_whitelisted_actors_checks_agents_and_users(seed):
    result = db.get_whitelisted_actors(
        [seed.active_agent, seed.inactive_agent, seed.active_user, seed.inactive_user, seed.unknown]
    )

    assert result == {seed.active_agent, seed.active_user}
