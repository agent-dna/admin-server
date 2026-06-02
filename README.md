# admin-server

Admin server to manage deployed agents.

## Overview

This is a Python (FastAPI) server that lets you create agents and update their policies. Policy files are uploaded via multipart form data and stored on disk under `policy_store/<org_id>/<agent_name>/` with a UUID4 suffix appended to the original filename (extension preserved). On create, the agent is also registered with AgentDNA; on update, the new policy is pushed via AgentDNA's `update_policy()`.

## Requirements

- Python 3.10 or newer
- pip

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy the sample env file and edit values if needed:

   ```bash
   cp .env.sample .env
   ```

   Available variables:

   - `ADMIN_SERVER_PORT`: the port the server listens on. Defaults to `8000`.
   - `AGENTDNA_API_KEY`: API key passed to the AgentDNA SDK.
   - `AGENTDNA_CHAIN_URL`: chain URL passed to the AgentDNA SDK.

## Running

Start the server:

```bash
python main.py
```

The server will listen on `http://localhost:<ADMIN_SERVER_PORT>`.

You can also browse the auto generated API docs at `http://localhost:<ADMIN_SERVER_PORT>/docs`.

## Endpoints

### POST `/agent-admin/v1/create-agent`

Creates a new agent, stores its policy file (UUID-suffixed), and deploys the agent NFT via AgentDNA. The caller's DID (`creator_did`) must already be registered locally via `/register-admin`.

Request type: `multipart/form-data`

Request fields:

- `policy` (file): the policy file to upload
- `creator_did` (string): DID of the admin creating the agent
- `org_id` (string): organization ID the agent belongs to
- `agent_name` (string): name of the agent

Response (JSON):

- `status` (bool): true if the agent was created
- `message` (string): human readable result
- `agent_id` (string \| null): on-chain NFT id for the deployed agent (null on failure)
- `agent_did` (string \| null): DID of the deployed agent (null on failure)

Sample success:

```json
{
  "status": true,
  "message": "Agent 'agent-a' created successfully",
  "agent_id": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtnft00001",
  "agent_did": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtdid00001"
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

### POST `/agent-admin/v1/register-admin`

Registers an admin user by initializing a Rubix signer for them and returning the resulting DID.

Request type: `application/json`

Request body:

- `username` (string): username of the admin to register

Response (JSON):

- `status` (bool): true if the signer was initialized successfully
- `message` (string): on success, the admin's DID (IPFS CID v1); on failure, a human-readable error

Sample success:

```json
{
  "status": true,
  "message": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
}
```

Sample failure (conflict with existing record):

```json
{
  "status": false,
  "message": "Admin registration conflict: username 'admin-user' already registered with a different did"
}
```

### POST `/agent-admin/v1/update-agent-policies`

Replaces the policy file for an existing agent.

Request type: `multipart/form-data`

Request fields:

- `policy` (file): the new policy file
- `creator_did` (string): DID of the admin updating the agent (must be registered via `/register-admin`)
- `org_id` (string): organization ID the agent belongs to
- `agent_name` (string): name of the agent
- `agent_id` (string): on-chain NFT id of the agent (returned by `/create-agent`)

Response (JSON):

- `status` (bool): true if the policy was updated
- `message` (string): human readable result

Sample success:

```json
{
  "status": true,
  "message": "Policy for agent 'agent-a' updated successfully"
}
```

Sample failure (admin not registered):

```json
{
  "status": false,
  "message": "Admin 'bafybeic...' is not registered locally. Try requesting registration of admin again."
}
```

## Project structure

- `main.py`: FastAPI app and route handlers
- `schemas.py`: Pydantic request and response models
- `services.py`: business logic for creating agents and updating policies
- `config.py`: loads settings from the `.env` file
- `.env.sample`: template for environment variables
- `requirements.txt`: Python dependencies
- `postman/`: Postman collection and environment for trying the endpoints

## Postman

Import these files into Postman:

- `postman/admin-server.postman_collection.json`: the request collection
- `postman/admin-server.postman_environment.json`: a local environment with `base_url`, `creator_did`, `org_id`, and `agent_name`

In each request, set the `policy` form field to a file from your disk before sending.
