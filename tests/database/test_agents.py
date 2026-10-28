"""Tests for the agent queries in db.py."""

import pytest

import db


def test_add_registered_agent_stores_active_agent(test_pool):
    db.add_registered_agent("agent-did", "agent-a", "org-1", "admin-did", "allow: read")

    with test_pool.connection() as conn:
        row = conn.execute(
            "SELECT did, agent_name, org_id, deployer_did, policy, is_active FROM agents"
        ).fetchone()
    assert row == ("agent-did", "agent-a", "org-1", "admin-did", "allow: read", True)


def test_add_registered_agent_rejects_duplicate_did(seed):
    with pytest.raises(db.AgentConflictError):
        db.add_registered_agent(seed.active_agent, "other", "org-1", "admin-did", "")


def test_get_all_agents_omits_policy(seed):
    agents = db.get_all_agents()

    assert sorted(agents, key=lambda a: a["agent_name"]) == [
        {
            "did": seed.active_agent,
            "agent_name": seed.active_agent_name,
            "org_id": seed.admin_org,
            "deployer_did": seed.admin_did,
            "is_active": True,
        },
        {
            "did": seed.inactive_agent,
            "agent_name": seed.inactive_agent_name,
            "org_id": seed.admin_org,
            "deployer_did": seed.admin_did,
            "is_active": False,
        },
    ]


def test_get_agent_by_did_includes_policy(seed):
    assert db.get_agent_by_did(seed.active_agent) == {
        "did": seed.active_agent,
        "agent_name": seed.active_agent_name,
        "org_id": seed.admin_org,
        "deployer_did": seed.admin_did,
        "policy": seed.agent_policy,
        "is_active": True,
    }
    assert db.get_agent_by_did(seed.unknown) is None


def test_set_agent_policy_matches_org_and_name(seed):
    assert db.set_agent_policy(seed.admin_org, seed.active_agent_name, "allow: write") is True
    assert db.get_agent_by_did(seed.active_agent)["policy"] == "allow: write"
    # The other agent in the same org is untouched.
    assert db.get_agent_by_did(seed.inactive_agent)["policy"] == seed.agent_policy

    assert db.set_agent_policy("other-org", seed.active_agent_name, "allow: write") is False


def test_set_agent_active_status(seed):
    assert db.set_agent_active_status(seed.inactive_agent, True) is True
    assert db.is_agent_whitelisted(seed.inactive_agent) is True

    assert db.set_agent_active_status(seed.unknown, True) is False
