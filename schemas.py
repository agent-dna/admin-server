from pydantic import BaseModel, Field

class AgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")


class RegisterAdminRequest(BaseModel):
    username: str = Field(..., description="Username of the admin to register")


class CreateAgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    agent_id: str | None = Field(None, description="On-chain NFT id for the deployed agent")
    agent_did: str | None = Field(None, description="DID of the deployed agent")


class AuthorizeActionRequest(BaseModel):
    agent_id: str = Field(..., description="On-chain NFT id of the calling agent")
    action_intent: str = Field(..., description="Intent the agent wants to perform")


class AuthorizeActionResponse(BaseModel):
    authorized: bool = Field(..., description="Whether the action is authorized for the agent")
    message: str = Field(..., description="Human-readable rationale for the decision")
