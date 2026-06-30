import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from agentdna.core import AgentDNA
from rubix.signer import Signer
from rubix.client import RubixClient
from agentdna.cbac import CBAC
from agentdna.provenance import Provenance
from agentdna.helpers import get_root_envelope
from agentdna.types import IntentWorkflow
from agentdna.verifier import verify_heavy

from db import (
    AdminConflictError,
    add_admin,
    add_registered_agent,
    get_username_by_did,
    get_admin_by_username,
    get_all_agents,
    get_agent_by_did,
    set_agent_policy,
    agent_exists,
)
from recovery import journal, clear
from security import hash_password, verify_password, create_access_token
from config import settings

POLICY_STORE = Path(__file__).parent / "policy_store"


def _agent_dir(org_id: str, agent_name: str) -> Path:
    return POLICY_STORE / org_id / agent_name


def _suffixed_policy_name(original_name: str | None) -> str:
    suffix = uuid4().hex
    if original_name:
        stem = Path(original_name).stem or "policy"
        ext = Path(original_name).suffix
        return f"{stem}_{suffix}{ext}"
    return f"policy_{suffix}"


async def _write_policy(policy: UploadFile, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = await policy.read()
    target.write_bytes(contents)


async def create_agent(
    policy: UploadFile,
    creator_did: str,
    org_id: str,
    agent_name: str,
) -> tuple[bool, str, str | None, str | None]:
    provenance_layer = Provenance(
        name="admin-server",
        provenance_url=settings.agentdna_chain_url,
        api_key=settings.agentdna_api_key,
        config_path=settings.agentdna_config_dir
    )
    cbac = CBAC(provenance_layer, "")

    agent_dir = _agent_dir(org_id, agent_name)
    policy_path = agent_dir / _suffixed_policy_name(policy.filename)
    await _write_policy(policy, policy_path)

    try:
        admin_username = get_username_by_did(creator_did)
        if not admin_username:
            shutil.rmtree(agent_dir, ignore_errors=True)
            return (
                False,
                f"Admin '{creator_did}' is not registered locally. Try requesting registration of admin again.",
                None,
                None,
            )

        admin = AgentDNA(
            name=admin_username,
            type="human",
            provenance_layer_url=settings.agentdna_chain_url,
            api_key=settings.agentdna_api_key,
            config_dir=settings.agentdna_config_dir,
            skip_actor_id_registration=True
        )

        agent = AgentDNA(
            name=agent_name,
            type="agent",
            provenance_layer_url=settings.agentdna_chain_url,
            api_key=settings.agentdna_api_key,
            config_dir=settings.agentdna_config_dir,
            skip_actor_id_registration=True
        )

        policy_content = policy_path.read_text(encoding="utf-8")
        
        try:
            admin.create_agent_card(
                agent,
                policy_file=policy_path,
            )
        except Exception as exc:
            shutil.rmtree(agent_dir, ignore_errors=True)
            return False, f"Failed to deploy agent with AgentDNA: {exc}", None, None

        # Pre compute NLI embeddings
        try:
            await cbac.precompute_policy(agent.get_actor_id(), skip_compute=False)
        except Exception as exec:
            return False, f"Failed to precompute policy: {exec}", None, None

        agent_payload = {
            "id": agent.get_actor_id(),
            "agent_name": agent_name,
            "org_id": org_id,
            "deployer_did": creator_did,
            "policy": policy_content,
        }
        # entry = journal("add_registered_agent", agent_payload)
        try:
            add_registered_agent(**agent_payload)
            print(f"Agent {agent_payload['agent_name']} has been created")
            # clear(entry)
        except Exception as exc:
            return (
                True,
                f"Agent '{agent_name}' created; DB persistence deferred and will reconcile on restart ({exc})",
                agent.get_actor_id(),
                agent.get_actor_id(),
            )

        return True, f"Agent '{agent_name}' created successfully", agent.get_actor_id(), agent.get_actor_id()
    except Exception as exc:
        shutil.rmtree(agent_dir, ignore_errors=True)
        return False, f"Failed to register agent with AgentDNA: {exc}", None, None

async def register_admin(username: str, org: str, password: str, email: str) -> tuple[bool, str]:
    client = RubixClient(node_url=settings.agentdna_chain_url, timeout=300)

    try:
        signer = Signer(
            rubixClient=client,
            alias=username,
        )
    except Exception as exc:
        return False, f"Failed to initialize signer: {exc}"

    try:
        add_admin(signer.did, username, org, hash_password(password), email)
    except AdminConflictError as exc:
        return False, f"Admin registration conflict: {exc}"

    return True, signer.did


async def login(username: str, password: str) -> tuple[bool, str, str | None]:
    try:
        admin = get_admin_by_username(username)
    except Exception as exc:
        return False, f"Error occurred during login: {exc}", None

    # Same generic message whether the username is unknown or the password is
    # wrong, so the response can't be used to enumerate valid usernames.
    if admin is None or not verify_password(password, admin["password"]):
        return False, "Invalid username or password", None

    token = create_access_token(username, did=admin["did"], org_id=admin["org"])
    return True, "Login successful", token


async def authorize_action(agent_id: str, action_intent: str, intent_workflow: IntentWorkflow) -> tuple[bool, str]:
    provenance_layer = Provenance(
        name="admin-server",
        provenance_url=settings.agentdna_chain_url,
        api_key=settings.agentdna_api_key,
        config_path=settings.agentdna_config_dir
    )
    cbac = CBAC(provenance=provenance_layer, cbac_url="")
    
    # Reject early if the agent (matched by did) isn't registered in our database,
    # before doing any CBAC / CoCA work.
    try:
        if not agent_exists(agent_id):
            return False, f"Agent '{agent_id}' is not whitelisted"
    except Exception as exc:
        return False, f"Error occurred while checking agent registration: {exc}"

    # CoCA verification
    coca_verification_result = verify_heavy(provenance=provenance_layer, workflow=intent_workflow)
    if not coca_verification_result.valid:
        return False, f"CoCA verification failed: issues found: {coca_verification_result.issues}"

    root_intent = ""
    try:
        root_envelope = get_root_envelope(intent_workflow)
        root_intent = root_envelope.payload
    except Exception as exc:
        return False, f"Error occurred while extracting root intent from envelope: {exc}"

    if root_intent == "":
        return False, "CBAC verification failed: root intent is empty"
    
    """
    CBAC Verification:
      - Agent's intent to policy verification
      - User's intent with Agent's intent verification
    """
    try:
        result = await cbac.verify_agent_app_interaction(agent_id, action_intent, root_intent)
    except Exception as exc:
        return False, f"CBAC verification failed: {exc}"

    cbac_decision = result.decision
    if cbac_decision not in ["allow", "deny"]:
        return False, f"Unexpected CBAC decision: {cbac_decision}"

    if cbac_decision == "allow":
        return True, result.reason or f"Action '{action_intent}' authorized for agent '{agent_id}'"
    return False, result.reason or f"Action '{action_intent}' is not authorized for agent '{agent_id}'"

async def update_agent_policies(
    policy: UploadFile,
    creator_did: str,
    org_id: str,
    agent_name: str,
    agent_id: str,
) -> tuple[bool, str]:
    agent_dir = _agent_dir(org_id, agent_name)
    policy_path = agent_dir / _suffixed_policy_name(policy.filename)
    await _write_policy(policy, policy_path)
    policy_content = policy_path.read_text(encoding="utf-8")

    try:
        admin_username = get_username_by_did(creator_did)
        if not admin_username:
            return (
                False,
                f"Admin '{creator_did}' is not registered locally. Try requesting registration of admin again.",
            )

        admin = AgentDNA(
            name=admin_username,
            type="human",
            provenance_layer_url=settings.agentdna_chain_url,
            api_key=settings.agentdna_api_key,
            config_dir=settings.agentdna_config_dir,
            skip_actor_id_registration=True
        )
        
        admin.update_agent_policy_by_id(agent_id, policy_file=policy_path)
    except Exception as exc:
        return False, f"Failed to update policy with AgentDNA: {exc}"

    # Pre compute NLI embeddings
    try:
        provenance_layer = Provenance(
            name="admin-server",
            provenance_url=settings.agentdna_chain_url,
            config_path=settings.agentdna_config_dir
        )

        cbac = CBAC(provenance_layer, "")
        await cbac.precompute_policy(agent_id, skip_compute=False)
    except Exception as exec:
        return False, f"Failed to precompute policy: {exec}"

    # Policy updated on-chain; mirror it into Postgres. The agents table is keyed
    # by did (which we don't have here), so match on (org_id, agent_name) — the
    # same identity the policy_store layout uses. Journal first so a DB failure is
    # reconciled by replay() on the next startup rather than lost.
    policy_payload = {
        "org_id": org_id,
        "agent_name": agent_name,
        "policy": policy_content,
    }
    entry = journal("set_agent_policy", policy_payload)
    try:
        updated = set_agent_policy(**policy_payload)
        clear(entry)
    except Exception as exc:
        return (
            True,
            f"Policy for agent '{agent_name}' updated on-chain; DB persistence deferred and will reconcile on restart ({exc})",
        )

    if not updated:
        return (
            True,
            f"Policy for agent '{agent_name}' updated on-chain, but no matching DB record was found to update",
        )

    return True, f"Policy for agent '{agent_name}' updated successfully"

async def list_agents() -> tuple[bool, str, list[dict[str, str]]]:
    try:
        agents = get_all_agents()
    except Exception as exc:
        return False, f"Failed to fetch agents: {exc}", []
    return True, f"Retrieved {len(agents)} agent(s)", agents


async def get_agent(did: str) -> tuple[bool, str, dict[str, str] | None]:
    try:
        agent = get_agent_by_did(did)
    except Exception as exc:
        return False, f"Failed to fetch agent: {exc}", None
    if agent is None:
        return False, f"No agent found with did '{did}'", None
    return True, "Agent retrieved", agent