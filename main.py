import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi.responses import JSONResponse

from config import settings
from db import init_db, pool
from recovery import replay
from schemas import (
    AgentResponse,
    AuthorizeActionRequest,
    AuthorizeActionResponse,
    CreateAgentResponse,
    RegisterAdminRequest,
    LoginRequest,
    AppRequest
)
from services import (
    authorize_action,
    create_agent,
    register_admin,
    update_agent_policies,
    list_agents,
    get_agent,
    login,
)
from agentdna.types import (
    IntentWorkflow
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
) -> CreateAgentResponse:
    status, message, agent_id, agent_did = await create_agent(
        policy, creator_did, org_id, agent_name
    )
    response = CreateAgentResponse(
        status=status, message=message, agent_id=agent_id, agent_did=agent_did
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

async def forward_to_app(
    app: AppRequest,
) -> tuple[int, httpx.Headers, bytes]:
    method = app.method or "POST"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.request(
                method=method,
                url=app.url,
                headers=app.headers,
                content=app.body or "",
            )
    except httpx.RequestError as exc:
        raise RuntimeError(f"forward_to_app: {exc}") from exc

    return (
        resp.status_code,
        resp.headers,
        resp.content,
    )

def relay_headers(response: Response, headers: httpx.Headers) -> None:
    hop_by_hop_headers = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
    for key, value in headers.items():
        if key.lower() not in hop_by_hop_headers:
            response.headers[key] = value

@app.post("/agent-admin/v1/authorize-action")
async def authorize_action_endpoint(payload: AuthorizeActionRequest):
    try:
        agent_envelope = IntentWorkflow(**payload.envelope)

        authorized, message = await authorize_action(
            payload.agent_id,
            payload.action_intent,
            agent_envelope,
        )

        if not authorized:
            return JSONResponse(
                status_code=403,
                headers={"X-CBAC-Decision": "deny"},
                content={
                    "status": False,
                    "message": message,
                },
            )

        status_code, headers, body = await forward_to_app(payload.app_request)

        response = Response(
            content=body,
            status_code=status_code,
        )

        relay_headers(response, headers)

        return response

    except Exception as exc:
        return JSONResponse(
            status_code=502,
            headers={"X-CBAC-Decision": "error"},
            content={
                "status": False,
                "message": str(exc),
            },
        )

@app.post("/agent-admin/v1/login", response_model=AgentResponse)
async def login_endpoint(payload: LoginRequest) -> AgentResponse:
    status, message, token = await login(payload.username, payload.password)
    return AgentResponse(status=status, message=message, data=token)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=settings.admin_server_port, reload=True)
