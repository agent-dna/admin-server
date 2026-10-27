from typing import Any

from pydantic import BaseModel, EmailStr, Field

class AgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    data: Any = Field(None, description="Optional payload of any type; None when not applicable")

class BaseResponse(BaseModel):
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


class WhitelistAgentRequest(BaseModel):
    agent_id: str = Field(..., description="On-chain DID of the agent to whitelist")


class CreateAgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    agent_id: str = Field(..., description="Agent ID")
    agent_card_id: str = Field(..., description="Agent Card ID")


class RegisterUserRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    user_id: str = Field(..., min_length=1, description="User ID supplied by the client")
    api_key: str = Field(..., description="User API Key")


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(
        ...,
        description="True to activate the user ID, false to deactivate it",
    )
