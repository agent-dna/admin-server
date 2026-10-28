"""Tests for the agent endpoints, with the DB and AgentDNA mocked:

POST /agent-admin/v1/create-agent
POST /agent-admin/v1/update-agent-policies
POST /agent-admin/v1/agents
GET  /agent-admin/v1/agents/{did}
POST /agent-admin/v1/revoke-agent
POST /agent-admin/v1/whitelist
GET  /agent-admin/v1/whitelist/{did}
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import recovery
import services

ADMIN_DID = "bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
AGENT_ID = "bafybeie5nqv6kd3qnfjupgvz34woh3oksc3iau6abmyajn7qvtf6d2ho34"
AGENT_CARD_ID = "agent-card-1"
POLICY = b"allow: read"
FORM = {"creator_did": ADMIN_DID, "org_id": "org-1", "agent_name": "agent-a", "agent_id": AGENT_ID}
FILES = {"policy": ("policy.yaml", POLICY, "text/yaml")}


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """Write policy files and recovery journal entries to a temp dir, not the repo."""
    paths = SimpleNamespace(policy_store=tmp_path / "policy_store", log_dir=tmp_path / "log")
    monkeypatch.setattr(services, "POLICY_STORE", paths.policy_store)
    monkeypatch.setattr(recovery, "LOG_DIR", paths.log_dir)
    monkeypatch.setattr(services.settings, "is_cbac_enabled", False)
    return paths


@pytest.fixture
def deps(monkeypatch):
    """Mock the admin lookup, AgentDNA and the DB writes used by create/update."""
    mocks = SimpleNamespace(
        get_username_by_did=MagicMock(return_value="admin-user"),
        agentdna=MagicMock(),
        add_registered_agent=MagicMock(),
        set_agent_policy=MagicMock(return_value=True),
    )
    mocks.agentdna.return_value.create_agent_card_by_id.return_value = AGENT_CARD_ID
    monkeypatch.setattr(services, "AgentDNA", mocks.agentdna)
    for name in ("get_username_by_did", "add_registered_agent", "set_agent_policy"):
        monkeypatch.setattr(services, name, getattr(mocks, name))
    return mocks


def _agent_dir(storage):
    return storage.policy_store / "org-1" / "agent-a"


def _journal_entries(storage):
    return list(storage.log_dir.glob("*.json")) if storage.log_dir.exists() else []


# --- create-agent ---


def test_create_agent_deploys_and_records_agent(client, storage, deps):
    body = client.post("/agent-admin/v1/create-agent", data=FORM, files=FILES).json()

    assert body == {
        "status": True,
        "message": "Agent 'agent-a' created successfully",
        "agent_id": AGENT_ID,
        "agent_card_id": AGENT_CARD_ID,
    }
    # The policy is stored under a UUID-suffixed name, keeping the extension.
    [policy_file] = _agent_dir(storage).iterdir()
    assert policy_file.name.startswith("policy_") and policy_file.suffix == ".yaml"
    assert policy_file.read_bytes() == POLICY
    deps.agentdna.return_value.create_agent_card_by_id.assert_called_once_with(AGENT_ID, policy_file=policy_file)
    deps.add_registered_agent.assert_called_once_with(
        id=AGENT_ID, agent_name="agent-a", org_id="org-1", deployer_did=ADMIN_DID, policy=POLICY.decode()
    )
    assert _journal_entries(storage) == []


def test_create_agent_unregistered_admin(client, storage, deps):
    deps.get_username_by_did.return_value = None

    body = client.post("/agent-admin/v1/create-agent", data=FORM, files=FILES).json()

    assert body["status"] is False
    assert "not registered" in body["message"]
    assert not _agent_dir(storage).exists()
    deps.agentdna.assert_not_called()


def test_create_agent_deploy_failure_cleans_up(client, storage, deps):
    deps.agentdna.return_value.create_agent_card_by_id.side_effect = RuntimeError("chain error")

    body = client.post("/agent-admin/v1/create-agent", data=FORM, files=FILES).json()

    assert body["status"] is False
    assert not _agent_dir(storage).exists()
    deps.add_registered_agent.assert_not_called()


def test_create_agent_db_failure_after_deploy_is_journaled(client, storage, deps):
    # The chain deploy is the commit point: a failed DB write is kept for replay on restart.
    deps.add_registered_agent.side_effect = RuntimeError("db down")

    body = client.post("/agent-admin/v1/create-agent", data=FORM, files=FILES).json()

    assert body["status"] is True
    assert "deferred" in body["message"]
    [entry] = _journal_entries(storage)
    record = json.loads(entry.read_text())
    assert record["op"] == "add_registered_agent"
    assert record["payload"]["id"] == AGENT_ID


def test_create_agent_cbac_precompute_failure(client, deps, monkeypatch):
    monkeypatch.setattr(services.settings, "is_cbac_enabled", True)
    monkeypatch.setattr(services, "_precompute_cbac_policy", AsyncMock(return_value=(False, "boom")))

    body = client.post("/agent-admin/v1/create-agent", data=FORM, files=FILES).json()

    assert body["status"] is False
    assert body["message"] == "CBAC policy precompute failed: boom"


# --- update-agent-policies ---


def test_update_agent_policies_updates_chain_and_db(client, storage, deps):
    body = client.post("/agent-admin/v1/update-agent-policies", data=FORM, files=FILES).json()

    assert body == {"status": True, "message": "Policy for agent 'agent-a' updated successfully", "data": None}
    [policy_file] = _agent_dir(storage).iterdir()
    deps.agentdna.return_value.update_agent_policy_by_id.assert_called_once_with(AGENT_ID, policy_file=policy_file)
    deps.set_agent_policy.assert_called_once_with(org_id="org-1", agent_name="agent-a", policy=POLICY.decode())
    assert _journal_entries(storage) == []


def test_update_agent_policies_unregistered_admin(client, deps):
    deps.get_username_by_did.return_value = None

    body = client.post("/agent-admin/v1/update-agent-policies", data=FORM, files=FILES).json()

    assert body["status"] is False
    deps.agentdna.assert_not_called()


def test_update_agent_policies_chain_failure_skips_db(client, deps):
    deps.agentdna.return_value.update_agent_policy_by_id.side_effect = RuntimeError("chain error")

    body = client.post("/agent-admin/v1/update-agent-policies", data=FORM, files=FILES).json()

    assert body["status"] is False
    deps.set_agent_policy.assert_not_called()


# --- reads and status changes ---


def test_list_agents(client, monkeypatch):
    agents = [{"did": AGENT_ID, "agent_name": "agent-a", "org_id": "org-1", "deployer_did": ADMIN_DID, "is_active": True}]
    monkeypatch.setattr(services, "get_all_agents", MagicMock(return_value=agents))

    body = client.post("/agent-admin/v1/agents").json()

    assert body == {"status": True, "message": "Retrieved 1 agent(s)", "data": agents}


def test_get_agent(client, monkeypatch):
    agent = {"did": AGENT_ID, "agent_name": "agent-a", "policy": "allow: read"}
    monkeypatch.setattr(services, "get_agent_by_did", MagicMock(return_value=agent))

    assert client.get(f"/agent-admin/v1/agents/{AGENT_ID}").json()["data"] == agent


def test_get_agent_not_found(client, monkeypatch):
    monkeypatch.setattr(services, "get_agent_by_did", MagicMock(return_value=None))

    body = client.get(f"/agent-admin/v1/agents/{AGENT_ID}").json()

    assert body["status"] is False
    assert body["data"] is None


@pytest.mark.parametrize(
    "url, is_active",
    [("/agent-admin/v1/revoke-agent", False), ("/agent-admin/v1/whitelist", True)],
)
def test_set_agent_status(client, monkeypatch, url, is_active):
    set_status = MagicMock(return_value=True)
    monkeypatch.setattr(services, "set_agent_active_status", set_status)

    body = client.post(url, json={"agent_id": AGENT_ID}).json()

    assert body["status"] is True
    set_status.assert_called_once_with(AGENT_ID, is_active)


@pytest.mark.parametrize("url", ["/agent-admin/v1/revoke-agent", "/agent-admin/v1/whitelist"])
def test_set_agent_status_unknown_agent(client, monkeypatch, url):
    monkeypatch.setattr(services, "set_agent_active_status", MagicMock(return_value=False))

    body = client.post(url, json={"agent_id": AGENT_ID}).json()

    assert body["status"] is False
    assert "No agent found" in body["message"]


def test_check_agent_whitelist(client, monkeypatch):
    lookup = MagicMock(return_value=True)
    monkeypatch.setattr(services, "is_agent_whitelisted", lookup)

    body = client.get(f"/agent-admin/v1/whitelist/{AGENT_ID}").json()

    assert body["data"] is True
    lookup.assert_called_once_with(AGENT_ID)


@pytest.mark.parametrize(
    "method, url, payload, db_function",
    [
        pytest.param("POST", "/agent-admin/v1/agents", None, "get_all_agents", id="list-agents"),
        pytest.param("GET", f"/agent-admin/v1/agents/{AGENT_ID}", None, "get_agent_by_did", id="get-agent"),
        pytest.param("POST", "/agent-admin/v1/revoke-agent", {"agent_id": AGENT_ID}, "set_agent_active_status", id="revoke-agent"),
        pytest.param("POST", "/agent-admin/v1/whitelist", {"agent_id": AGENT_ID}, "set_agent_active_status", id="whitelist-agent"),
        pytest.param("GET", f"/agent-admin/v1/whitelist/{AGENT_ID}", None, "is_agent_whitelisted", id="check-whitelist"),
    ],
)
def test_db_error_returns_failed_status(client, monkeypatch, method, url, payload, db_function):
    monkeypatch.setattr(services, db_function, MagicMock(side_effect=RuntimeError("db down")))

    assert client.request(method, url, json=payload).json()["status"] is False
