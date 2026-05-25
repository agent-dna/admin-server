from fastapi import FastAPI, File, Form, UploadFile

from config import settings
from schemas import AgentResponse
from services import create_agent, update_agent_policies

app = FastAPI(title="Admin Server", version="0.1.0")


@app.post("/agent-admin/v1/create-agent", response_model=AgentResponse)
async def create_agent_endpoint(
    policy: UploadFile = File(...),
    creator_did: str = Form(...),
    org_id: str = Form(...),
    agent_name: str = Form(...),
) -> AgentResponse:
    status, message = await create_agent(policy, creator_did, org_id, agent_name)
    return AgentResponse(status=status, message=message)


@app.post("/agent-admin/v1/update-agent-policies", response_model=AgentResponse)
async def update_agent_policies_endpoint(
    policy: UploadFile = File(...),
    creator_did: str = Form(...),
    org_id: str = Form(...),
    agent_name: str = Form(...),
) -> AgentResponse:
    status, message = await update_agent_policies(
        policy, creator_did, org_id, agent_name
    )
    return AgentResponse(status=status, message=message)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=settings.admin_server_port, reload=True)
