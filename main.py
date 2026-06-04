from fastapi import FastAPI, File, Form, UploadFile

from config import settings
from schemas import (
    AgentResponse,
    AuthorizeActionRequest,
    AuthorizeActionResponse,
    CreateAgentResponse,
    RegisterAdminRequest,
)
from services import (
    authorize_action,
    create_agent,
    register_admin,
    update_agent_policies,
)

app = FastAPI(title="Admin Server", version="0.1.0")


@app.post("/agent-admin/v1/create-agent", response_model=CreateAgentResponse)
async def create_agent_endpoint(
    policy: UploadFile = File(...),
    creator_did: str = Form(...),
    org_id: str = Form(...),
    agent_name: str = Form(...),
) -> CreateAgentResponse:
    status, message, agent_id, agent_did = await create_agent(
        policy, creator_did, org_id, agent_name
    )
    response = CreateAgentResponse(
        status=status, message=message, agent_id=agent_id, agent_did=agent_did
    )
    return response


@app.post("/agent-admin/v1/register-admin", response_model=AgentResponse)
async def register_admin_endpoint(payload: RegisterAdminRequest) -> AgentResponse:
    status, message = await register_admin(payload.username)
    return AgentResponse(status=status, message=message)


@app.post("/agent-admin/v1/authorize-action", response_model=AuthorizeActionResponse)
async def authorize_action_endpoint(
    payload: AuthorizeActionRequest,
) -> AuthorizeActionResponse:
    authorized, message = await authorize_action(payload.agent_id, payload.action_intent)
    return AuthorizeActionResponse(authorized=authorized, message=message)


@app.post("/agent-admin/v1/update-agent-policies", response_model=AgentResponse)
async def update_agent_policies_endpoint(
    policy: UploadFile = File(...),
    creator_did: str = Form(...),
    org_id: str = Form(...),
    agent_name: str = Form(...),
    agent_id: str = Form(...),
) -> AgentResponse:
    status, message = await update_agent_policies(
        policy, creator_did, org_id, agent_name, agent_id
    )
    return AgentResponse(status=status, message=message)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=settings.admin_server_port, reload=True)
