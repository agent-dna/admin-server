# Tests

## Running

```bash
uv run pytest
```

Docker must be running: DB tests start a throwaway Postgres container
(`postgres:18.3`, same as docker-compose) via
[testcontainers](https://testcontainers.com/?language=python). One container is
shared by the whole run, and each test gets its own schema.

## Layout

| Folder | Covers | DB |
|---|---|---|
| `controllers/` | API endpoints: request validation, service logic, response shape | Mocked (`services.<db function>`) |
| `database/` | Functions in `db.py`, run against real Postgres | Testcontainers (fixtures in `database/conftest.py`) |

Test file names must be unique across folders.

### Controller fixtures

| Fixture | Gives you |
|---|---|
| `client` | A FastAPI `TestClient` for the app, without running its startup (no DB connection) |

### DB fixtures

| Fixture | Gives you |
|---|---|
| `test_pool` | An empty schema with the app's tables, with `db.pool` pointed at it |
| `seed` | `test_pool` populated with the sample data below; returns a `SeedData` with these values |

| `SeedData` field | Row |
|---|---|
| `admin_did`, `admin_username`, `admin_org`, `admin_email`, `admin_password_hash` | One admin in `admin` |
| `active_agent` / `inactive_agent` (+ `_name`) | Agents in `agents`, `is_active` true / false; both in `admin_org`, deployed by `admin_did`, with `agent_policy` |
| `user_email`, `user_api_key` | One user in `users` |
| `active_user` / `inactive_user` | That user's DIDs in `user_id`, `is_active` true / false |
| `unknown` | A DID that isn't in any table |

Add to `SeedData` and the `seed` fixture when a new test needs more rows, rather than inserting rows inside the test.

## Tests

We test behaviour that could realistically break, not every line. One test per behaviour.
Each controller file also has a parametrized `test_db_error_returns_failed_status` checking that a DB
exception becomes `status: false` rather than a 500.

### Controllers

#### Admin endpoints

Covers `register-admin`, `login` and `update-password`. Rubix `Signer` / `RubixClient` and DB functions are mocked.

| Test | Checks |
|---|---|
| `test_register_admin_stores_hashed_password_and_returns_did` | Stores the signer's DID and a bcrypt hash (not the plain password); returns the DID in `message` |
| `test_register_admin_conflict` | A duplicate admin returns `status: false` |
| `test_register_admin_signer_failure_stores_nothing` | If the signer can't be created, nothing is written |
| `test_login_returns_jwt_with_admin_claims` | The JWT decodes with `sub`, `did`, `org_id` of the admin |
| `test_login_failures_share_one_message[unknown-username\|wrong-password]` | Both failures return the same generic message (no username enumeration) |
| `test_update_password_stores_new_hash` | Stores a bcrypt hash of the new password |
| `test_update_password_unknown_admin` | Unknown username fails without writing |

#### Agent endpoints

AgentDNA and DB functions are mocked. Policy files and recovery journal entries go to a temp dir.

| Test | Checks |
|---|---|
| `test_create_agent_deploys_and_records_agent` | Policy stored with a UUID-suffixed name; deployed via AgentDNA; recorded in the DB; journal entry cleared |
| `test_create_agent_unregistered_admin` | Fails before deploying; policy dir removed |
| `test_create_agent_deploy_failure_cleans_up` | AgentDNA failure removes the policy dir and writes nothing to the DB |
| `test_create_agent_db_failure_after_deploy_is_journaled` | DB failure after a successful deploy still succeeds and leaves a journal entry for replay |
| `test_create_agent_cbac_precompute_failure` | With CBAC enabled, a precompute failure returns `status: false` |
| `test_update_agent_policies_updates_chain_and_db` | Updates the policy via AgentDNA, then in the DB by `(org_id, agent_name)` |
| `test_update_agent_policies_unregistered_admin` | Fails before calling AgentDNA |
| `test_update_agent_policies_chain_failure_skips_db` | AgentDNA failure leaves the DB untouched |
| `test_list_agents` / `test_get_agent` / `test_get_agent_not_found` | Read endpoints return the DB result; unknown DID gives `status: false` |
| `test_set_agent_status[revoke-agent\|whitelist]` | Revoke sets `is_active` false, whitelist sets it true |
| `test_set_agent_status_unknown_agent[...]` | Unknown agent returns `status: false` |
| `test_check_agent_whitelist` | `GET /whitelist/{did}` returns the agent's whitelist status |

#### User endpoints

| Test | Checks |
|---|---|
| `test_register_user_passes_fields_in_order` | `_register_user` gets `(email, api_key, user_id)` in that order |
| `test_register_user_conflict` | A registration conflict returns `status: false` with the reason |
| `test_update_user_status[True\|False]` | Sets the flag; message says whitelisted / blacklisted |
| `test_get_user_status` | Returns the user DID's status |
| `test_list_users[some\|none]` | Returns the list; empty list says "no users found" |

#### Batch whitelist check

Covers `POST /agent-admin/v1/whitelist/check`.

| Test | Checks |
|---|---|
| `test_splits_dids_into_whitelist_and_blacklist` | DIDs are split into `whitelist` / `blacklist`; duplicates dropped, input order kept, unknown DIDs blacklisted |
| `test_db_error_returns_failed_status` | A DB failure returns `status: false` with empty lists |
| `test_rejects_empty_did_list` | An empty `dids` list is rejected with 422 |

### Database

#### Admins

| Test | Checks |
|---|---|
| `test_add_admin_stores_admin` | All columns are stored |
| `test_add_admin_rejects_duplicate[did\|username]` | Duplicate DID or username raises `AdminConflictError` |
| `test_get_username_by_did` | Known DID → username; unknown → `None` |
| `test_get_admin_by_username` | Known → `did`, `org`, `password`; unknown → `None` |
| `test_update_admin_password` | Updates the hash; unknown username → `False` |

#### Agents

| Test | Checks |
|---|---|
| `test_add_registered_agent_stores_active_agent` | All columns stored; new agents start active |
| `test_add_registered_agent_rejects_duplicate_did` | Raises `AgentConflictError` |
| `test_get_all_agents_omits_policy` | Lists every agent without the policy body |
| `test_get_agent_by_did_includes_policy` | Full record including policy; unknown → `None` |
| `test_set_agent_policy_matches_org_and_name` | Updates only the matching `(org_id, agent_name)`; no match → `False` |
| `test_set_agent_active_status` | Flips `is_active`; unknown DID → `False` |

#### Users

| Test | Checks |
|---|---|
| `test_register_user_creates_user_and_id` | First registration creates the user and an active user DID |
| `test_register_user_adds_id_to_existing_user` | Same email + API key adds another DID |
| `test_register_user_rejects_conflicts_without_writing[...]` | Different API key, API key of another email, or duplicate DID raises `ValueError` and writes nothing |
| `test_get_user_active_status[active\|inactive\|unknown]` | `True` / `False` / `False` |
| `test_set_user_active_status` | Flips `is_active`; unknown DID → `False` |
| `test_get_all_users` | Lists every user DID with its status |

#### Whitelist

| Test | Checks |
|---|---|
| `test_is_agent_whitelisted[active\|inactive\|unknown]` | `True` / `False` / `False` |
| `test_get_whitelisted_actors_checks_agents_and_users` | Returns active DIDs from both `agents` and `user_id`; inactive and unknown DIDs are excluded |
