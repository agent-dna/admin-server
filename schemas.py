from typing import Any

from pydantic import BaseModel, Field

class AgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    data: Any = Field(None, description="Optional payload of any type; None when not applicable")

class RegisterAdminRequest(BaseModel):
    username: str = Field(..., description="Username of the admin to register")
    org: str = Field(..., description="Organization the admin belongs to")
    password: str = Field(..., description="Admin password (stored salted and hashed)")
    email: str = Field(..., description="Admin email")

class LoginRequest(BaseModel):
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")


class CreateAgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    agent_id: str | None = Field(None, description="On-chain NFT id for the deployed agent")
    agent_did: str | None = Field(None, description="DID of the deployed agent")


class AuthorizeActionRequest(BaseModel):
    agent_id: str = Field(..., description="On-chain NFT id of the calling agent")
    action_intent: str = Field(..., description="Intent the agent wants to perform")
    agent_envelope: dict = Field(..., description="Signed delegation chain for CoCA verification")

class AuthorizeActionResponse(BaseModel):
    authorized: bool = Field(..., description="Whether the action is authorized for the agent")
    message: str = Field(..., description="Human-readable rationale for the decision")
