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
    agent_id: str = Field(..., description="Agent ID")
    agent_card_id: str = Field(..., description="Agent Card ID")

class AppRequest(BaseModel):
    url: str = Field(..., description="Target application endpoint URL")
    method: str = Field(..., description="HTTP method to invoke")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers to include in the forwarded request",
    )
    body: str = Field(
        default="",
        description="HTTP request body to forward to the application",
    )

class AuthorizeActionRequest(BaseModel):
    agent_id: str = Field(..., description="On-chain NFT id of the calling agent")
    action_intent: str = Field(..., description="Intent the agent wants to perform")
    envelope: dict = Field(..., description="Signed delegation chain for CoCA verification")
    app_request: AppRequest = Field(..., description="HTTP request that will be authorized and forwarded to the target application if approval is granted")

class AuthorizeActionResponse(BaseModel):
    authorized: bool = Field(..., description="Whether the action is authorized for the agent")
    message: str = Field(..., description="Human-readable rationale for the decision")
