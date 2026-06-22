# admin-server

Admin server to manage deployed agents.

## Overview

This is a Python (FastAPI) server that registers admins, deploys agents, manages their policies, and makes authorization decisions for agent actions.

- **Admins** sign up with a username, organization, and password (stored salted + hashed with bcrypt) and receive a Rubix DID. They can log in to obtain a JWT.
- **Agents** are created by a registered admin: the policy file is uploaded via multipart form data, stored on disk under `policy_store/<org_id>/<agent_name>/` with a UUID4 suffix (extension preserved), the agent NFT is deployed via AgentDNA, and the agent is recorded in Postgres.
- **Authorization** decisions combine CBAC (does the agent's policy permit the intent?) with CoCA (is every layer of the signed delegation chain cryptographically valid?).

State lives in **Postgres** (`admin` and `agents` tables); there is no JSON/file-based store. The blockchain is the authoritative, append-only commit point, and Postgres is a derived index — when a chain write succeeds but the follow-up DB write fails, the write is journaled to `.log/` and reconciled automatically on the next startup.

## Requirements

- Python 3.10 or newer
- A reachable PostgreSQL instance
- pip

(Or just Docker — see [Running with Docker](#running-with-docker), which provides Postgres for you.)

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy the sample env file and edit values:

   ```bash
   cp .env.sample .env
   ```

   Available variables:

   - `ADMIN_SERVER_PORT`: the port the server listens on. Defaults to `8000`.
   - `AGENTDNA_API_KEY`: API key passed to the AgentDNA SDK.
   - `AGENTDNA_CHAIN_URL`: chain URL passed to the AgentDNA SDK.
   - `DATABASE_URL`: PostgreSQL connection string, e.g. `postgresql://postgres:postgres@localhost:5432/admin_server`.
   - `JWT_SECRET`: secret used to sign login JWTs (HS256). Must be a long, random string of at least 32 bytes of entropy. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. **Tokens signed with an empty/weak secret can be forged.**
   - `JWT_EXPIRY_MINUTES`: token lifetime in minutes. Defaults to `60`.

   The required tables (`admin`, `agents`) are created automatically on startup if they do not already exist.

## Running

Start the server:

```bash
python main.py
```

The server will listen on `http://localhost:<ADMIN_SERVER_PORT>`.

You can also browse the auto-generated API docs at `http://localhost:<ADMIN_SERVER_PORT>/docs`.

## Running with Docker

`docker-compose.yml` builds the server and starts a bundled Postgres (`admin-server-db`):

```bash
docker compose up --build
```

Compose reads `AGENTDNA_API_KEY` / `AGENTDNA_CHAIN_URL` / `JWT_SECRET` etc. from your host `.env` and points the server's `DATABASE_URL` at the bundled database automatically. Note: if your Rubix chain runs on the host, set `AGENTDNA_CHAIN_URL` to `http://host.docker.internal:<port>` (a `localhost` URL won't resolve from inside the container).

## Endpoints

All endpoints are under `/agent-admin/v1`. Several share a common response envelope, `AgentResponse`:

- `status` (bool): whether the operation succeeded
- `message` (string): human-readable result
- `data` (any | null): optional payload — its shape depends on the endpoint

### POST `/register-admin`

Registers an admin: initializes a Rubix signer, then stores `(did, username, org, password_hash)` in the `admin` table. The password is hashed with bcrypt before storage.

Request type: `application/json`

Request body:

- `username` (string): username of the admin to register
- `org` (string): organization the admin belongs to
- `password` (string): admin password (stored salted and hashed)

Response: `AgentResponse`. On success, `message` is the admin's DID (IPFS CID v1) and `data` is `null`.

Sample success:

```json
{
  "status": true,
  "message": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
  "data": null
}
```

Sample failure (conflict with existing record):

```json
{
  "status": false,
  "message": "Admin registration conflict: admin with did '...' or username 'admin-user' is already registered",
  "data": null
}
```

### POST `/login`

Verifies an admin's credentials and, on success, returns a signed JWT (HS256, expires after `JWT_EXPIRY_MINUTES`) in `data`.

Request type: `application/json`

Request body:

- `username` (string): admin username
- `password` (string): admin password

Response: `AgentResponse`. On success, `data` is the JWT. To avoid username enumeration, an unknown username and a wrong password return the same generic failure message.

Sample success:

```json
{
  "status": true,
  "message": "Login successful",
  "data": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<...>.<signature>"
}
```

Sample failure:

```json
{
  "status": false,
  "message": "Invalid username or password",
  "data": null
}
```

### POST `/create-agent`

Creates a new agent: stores its policy file (UUID-suffixed), deploys the agent NFT via AgentDNA, and records the agent in the `agents` table. The caller's DID (`creator_did`) must already be registered via `/register-admin`.

Request type: `multipart/form-data`

Request fields:

- `policy` (file): the policy file to upload
- `creator_did` (string): DID of the admin creating the agent
- `org_id` (string): organization ID the agent belongs to
- `agent_name` (string): name of the agent

Response (`CreateAgentResponse`):

- `status` (bool): true if the agent was created
- `message` (string): human-readable result
- `agent_id` (string | null): on-chain NFT id for the deployed agent
- `agent_did` (string | null): DID of the deployed agent

Sample success:

```json
{
  "status": true,
  "message": "Agent 'agent-a' created successfully",
  "agent_id": "<nft-id>",
  "agent_did": "<agent-did>"
}
```

Sample failure (admin not registered):

```json
{
  "status": false,
  "message": "Admin 'bafybeic...' is not registered locally. Try requesting registration of admin again.",
  "agent_id": null,
  "agent_did": null
}
```

> Note: the on-chain deploy is the commit point. If the deploy succeeds but the Postgres write fails, the response is still `status: true` with a message noting that persistence was deferred — the record is journaled to `.log/` and reconciled on the next startup.

### POST `/agents`

Lists all registered agents. Returns a lightweight view **without** the policy body (use `/agents/{did}` for the full record including policy).

Request body: none.

Response: `AgentResponse` with `data` set to a list of agents.

```json
{
  "status": true,
  "message": "Retrieved 2 agent(s)",
  "data": [
    { "did": "<agent-did>", "agent_name": "agent-a", "org_id": "org-1", "deployer_did": "<admin-did>" }
  ]
}
```

### GET `/agents/{did}`

Fetches a single agent by its DID, including the full policy text.

Path parameter:

- `did` (string): the agent's DID

Response: `AgentResponse` with `data` set to the agent record (or `null` when not found).

```json
{
  "status": true,
  "message": "Agent retrieved",
  "data": {
    "did": "<agent-did>",
    "agent_name": "agent-a",
    "org_id": "org-1",
    "deployer_did": "<admin-did>",
    "policy": "<full policy text>"
  }
}
```

Not found:

```json
{
  "status": false,
  "message": "No agent found with did '<agent-did>'",
  "data": null
}
```

### POST `/authorize-action`

Authorization decision endpoint called by the CBAC middleware that sits between agents and external apps (Slack, GitHub, etc.). The flow:

```text
Agent --> Middleware --> App
              |
              v
         Admin Server
       (authorize-action)
```

The middleware ultimately calls the App. Before it does, it asks this endpoint whether the agent's intent should be allowed; based on the response it forwards the original call or blocks it. The admin server itself never talks to the App.

The decision runs three checks, all of which must pass:

1. **Whitelist** — the `agent_id` must exist in the `agents` table.
2. **CBAC** — the agent's deployed policy must permit the `action_intent`.
3. **CoCA** — every layer of the signed delegation chain in `agent_envelope` is re-verified cryptographically (each block's signature is recomputed, not trusted from the embedded flag).

Request type: `application/json`

Request body:

- `agent_id` (string): on-chain identifier of the calling agent (matched against the `agents` table)
- `action_intent` (string): the action the agent intends to perform
- `agent_envelope` (object): the signed delegation chain (CoCA envelope) — a nested structure of signed blocks linked via `parent_block`. See `coca_envelope.json` for a complete example.

Response (`AuthorizeActionResponse`):

- `authorized` (bool): true if the action is allowed
- `message` (string): human-readable rationale

Sample authorized:

```json
{
  "authorized": true,
  "message": "Action 'create_issue' authorized for agent '<agent-id>'"
}
```

Sample denied (not whitelisted):

```json
{
  "authorized": false,
  "message": "Agent '<agent-id>' is not whitelisted"
}
```

Sample denied (CoCA failure):

```json
{
  "authorized": false,
  "message": "CoCA verification failed: invalid signature for layer 'WorkerAgent' (<did>)"
}
```

### POST `/update-agent-policies`

Replaces the policy file for an existing agent: stores the new file (UUID-suffixed), pushes the update to AgentDNA via `update_agent_policy(agent_id, ...)`, and updates the stored policy in the `agents` table (matched by `org_id` + `agent_name`).

Request type: `multipart/form-data`

Request fields:

- `policy` (file): the new policy file
- `creator_did` (string): DID of the admin updating the agent (must be registered via `/register-admin`)
- `org_id` (string): organization ID the agent belongs to
- `agent_name` (string): name of the agent
- `agent_id` (string): on-chain NFT id of the agent (returned by `/create-agent`)

Response: `AgentResponse` (`data` is `null`).

Sample success:

```json
{
  "status": true,
  "message": "Policy for agent 'agent-a' updated successfully",
  "data": null
}
```

Sample failure (admin not registered):

```json
{
  "status": false,
  "message": "Admin 'bafybeic...' is not registered locally. Try requesting registration of admin again.",
  "data": null
}
```

## Project structure

- `main.py`: FastAPI app, lifespan (DB init + recovery replay), and route handlers
- `schemas.py`: Pydantic request and response models
- `services.py`: business logic for admins, agents, policies, login, and authorization
- `db.py`: Postgres connection pool, schema, and queries
- `security.py`: bcrypt password hashing and JWT creation
- `recovery.py`: write-ahead reconciliation journal for chain → Postgres writes
- `config.py`: loads settings from the `.env` file
- `Dockerfile` / `docker-compose.yml`: containerized server + bundled Postgres
- `.env.sample`: template for environment variables
- `requirements.txt`: Python dependencies
- `coca_envelope.json`: a sample CoCA delegation-chain envelope for `/authorize-action`
- `postman/`: Postman collection and environment for trying the endpoints

## Postman

Import these files into Postman:

- `postman/admin-server.postman_collection.json`: the request collection
- `postman/admin-server.postman_environment.json`: a local environment with `base_url`, `creator_did`, `org_id`, `agent_name`, etc.

Notes:

- For multipart requests (`create-agent`, `update-agent-policies`), set the `policy` form field to a file from your disk before sending.
- The **Login** request saves the returned JWT into the `jwt_token` collection variable via a test script, so you can reference `{{jwt_token}}` in later requests once auth enforcement is added.
