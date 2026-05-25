import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from agentdna import AgentDNA

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
) -> tuple[bool, str]:
    agent_dir = _agent_dir(org_id, agent_name)
    if agent_dir.exists():
        return False, f"Agent '{agent_name}' already exists for org '{org_id}'"

    policy_path = agent_dir / _suffixed_policy_name(policy.filename)
    await _write_policy(policy, policy_path)

    try:
        AgentDNA(
            chain_url=settings.agentdna_chain_url,
            alias=agent_name,
            api_key=settings.agentdna_api_key,
            kind="agent",
            metadata={
                "orgId": org_id,
                "deployer": creator_did,
                "agent_name": agent_name,
            },
            policy_file = policy_path,
            cbac=True
        )
    except Exception as exc:
        shutil.rmtree(agent_dir, ignore_errors=True)
        return False, f"Failed to register agent with AgentDNA: {exc}"

    return True, f"Agent '{agent_name}' created successfully"


async def update_agent_policies(
    policy: UploadFile,
    creator_did: str,
    org_id: str,
    agent_name: str,
) -> tuple[bool, str]:
    agent_dir = _agent_dir(org_id, agent_name)
    if not agent_dir.exists():
        return False, f"Agent '{agent_name}' not found for org '{org_id}'"

    policy_path = agent_dir / _suffixed_policy_name(policy.filename)
    await _write_policy(policy, policy_path)

    try:
        agent = AgentDNA(
            chain_url=settings.agentdna_chain_url,
            alias=agent_name,
            api_key=settings.agentdna_api_key,
            kind="agent",
            metadata={
                "orgId": org_id,
                "deployer": creator_did,
                "agent_name": agent_name,
            },
            policy_file=policy_path,
            cbac=True,
        )
        agent.update_policy()
    except Exception as exc:
        return False, f"Failed to update policy with AgentDNA: {exc}"

    return True, f"Policy for agent '{agent_name}' updated successfully"
