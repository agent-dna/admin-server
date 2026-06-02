import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from agentdna import AgentDNA
from rubix.signer import Signer
from rubix.client import RubixClient

from admin_store import AdminConflictError, add_admin
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
    agent_dir = _agent_dir(org_id, agent_name)
    policy_path = agent_dir / _suffixed_policy_name(policy.filename)
    await _write_policy(policy, policy_path)

    try:
        from admin_store import get_username_by_did

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
            chain_url=settings.agentdna_chain_url,
            alias=admin_username,
            api_key=settings.agentdna_api_key,
            kind="user",
            enable_nft=False,
        )

        agent = AgentDNA(
            chain_url=settings.agentdna_chain_url,
            alias=agent_name,
            api_key=settings.agentdna_api_key,
            kind="agent",
            cbac=True,
        )

        policy_content = policy_path.read_text(encoding="utf-8")

        agent_id = admin.deploy_agent_nft(
            agent,
            metadata={
                "orgId": org_id,
                "deployer": creator_did,
                "agent_name": agent_name,
            },
            policy_content=policy_content,
        )
        agent_did = agent.did

        return True, f"Agent '{agent_name}' created successfully", agent_id, agent_did
    except Exception as exc:
        shutil.rmtree(agent_dir, ignore_errors=True)
        return False, f"Failed to register agent with AgentDNA: {exc}", None, None


async def register_admin(username: str) -> tuple[bool, str]:
    client = RubixClient(node_url=settings.agentdna_chain_url, timeout=300)

    try:
        signer = Signer(
            rubixClient=client,
            alias=username,
        )
    except Exception as exc:
        return False, f"Failed to initialize signer: {exc}"

    try:
        add_admin(username, signer.did)
    except AdminConflictError as exc:
        return False, f"Admin registration conflict: {exc}"

    return True, signer.did


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

    try:
        # Change the following from agent to admin
        from admin_store import get_username_by_did
        admin_username = get_username_by_did(creator_did)
        if not admin_username:
            return (
                False,
                f"Admin '{creator_did}' is not registered locally. Try requesting registration of admin again.",
            )

        admin = AgentDNA(
            chain_url=settings.agentdna_chain_url,
            alias=admin_username,
            api_key=settings.agentdna_api_key,
            kind="user",
            enable_nft=False,
        )
        
        policy_content = policy_path.read_text(encoding="utf-8")
        admin.update_agent_policy(agent_id, policy_content)
    except Exception as exc:
        return False, f"Failed to update policy with AgentDNA: {exc}"

    return True, f"Policy for agent '{agent_name}' updated successfully"
