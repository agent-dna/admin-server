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


class UpdatePasswordRequest(BaseModel):
    username: str = Field(..., description="Admin username")
    new_password: str = Field(..., description="New password to set (stored salted and hashed)")


class RevokeAgentRequest(BaseModel):
    agent_id: str = Field(..., description="On-chain DID of the agent to revoke")


class CreateAgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    agent_id: str = Field(..., description="Agent ID")
    agent_card_id: str = Field(..., description="Agent Card ID")


