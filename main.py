import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import init_db, pool
from recovery import replay
from schemas import (
    AgentResponse,
    CreateAgentResponse,
    RegisterAdminRequest,
    LoginRequest,
    UpdatePasswordRequest,
    RevokeAgentRequest,
)
from services import (
    create_agent,
    register_admin,
    update_agent_policies,
    update_password,
    revoke_agent,
    list_agents,
    get_agent,
    login,
    agent_whitelist
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    replay()  # reconcile `a`ny DB writes left pending by a prior failed/crashed run
    yield
    pool.close()


app = FastAPI(title="Admin Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agent-admin/v1/create-agent", response_model=CreateAgentResponse)
async def create_agent_endpoint(
    policy: UploadFile = File(...),
    creator_did: str = Form(...),
    org_id: str = Form(...),
    agent_name: str = Form(...),
    agent_id: str = Form(...)
) -> CreateAgentResponse:
    status, message, agent_id, agent_card_id = await create_agent(
        policy, creator_did, org_id, agent_name, agent_id
    )
    response = CreateAgentResponse(
        status=status, message=message, agent_id=agent_id, agent_card_id=agent_card_id
    )
    return response


@app.post("/agent-admin/v1/agents", response_model=AgentResponse)
async def list_agents_endpoint() -> AgentResponse:
    status, message, data = await list_agents()
    return AgentResponse(status=status, message=message, data=data)


@app.get("/agent-admin/v1/agents/{did}", response_model=AgentResponse)
async def get_agent_endpoint(did: str) -> AgentResponse:
    status, message, data = await get_agent(did)
    return AgentResponse(status=status, message=message, data=data)

@app.post("/agent-admin/v1/register-admin", response_model=AgentResponse)
async def register_admin_endpoint(payload: RegisterAdminRequest) -> AgentResponse:
    status, message = await register_admin(payload.username, payload.org, payload.password, payload.email)
    return AgentResponse(status=status, message=message, data=None)


@app.post("/agent-admin/v1/login", response_model=AgentResponse)
async def login_endpoint(payload: LoginRequest) -> AgentResponse:
    status, message, token = await login(payload.username, payload.password)
    return AgentResponse(status=status, message=message, data=token)


@app.post("/agent-admin/v1/update-password", response_model=AgentResponse)
async def update_password_endpoint(payload: UpdatePasswordRequest) -> AgentResponse:
    status, message = await update_password(
        payload.username, payload.new_password
    )
    return AgentResponse(status=status, message=message, data=None)


@app.post("/agent-admin/v1/revoke-agent", response_model=AgentResponse)
async def revoke_agent_endpoint(payload: RevokeAgentRequest) -> AgentResponse:
    status, message = await revoke_agent(payload.agent_id)
    return AgentResponse(status=status, message=message, data=None)


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
    return AgentResponse(status=status, message=message, data=None)


@app.get("/agent-admin/v1/whitelist/{did}", response_model=AgentResponse)
async def check_agent_whitelist(did: str) -> AgentResponse:
    status, message, is_whitelisted = await agent_whitelist(did)
    return AgentResponse(status=status, message=message, data=is_whitelisted)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=settings.admin_server_port, reload=True)
