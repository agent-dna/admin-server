from pydantic import BaseModel, Field

class AgentResponse(BaseModel):
    status: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")


class RegisterAdminRequest(BaseModel):
    username: str = Field(..., description="Username of the admin to register")
