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
| `active_agent` / `inactive_agent` | Agents in `agents`, `is_active` true / false |
| `user_email`, `user_api_key` | One user in `users` |
| `active_user` / `inactive_user` | That user's DIDs in `user_id`, `is_active` true / false |
| `unknown` | A DID that isn't in any table |

Add to `SeedData` and the `seed` fixture when a new test needs more rows, rather than inserting rows inside the test.

## Tests

We test behaviour that could realistically break, not every line. One test per behaviour.

### `controllers/test_whitelist_check.py` — `POST /agent-admin/v1/whitelist/check`

| Test | Checks |
|---|---|
| `test_splits_dids_into_whitelist_and_blacklist` | DIDs are split into `whitelist` / `blacklist`; duplicates dropped, input order kept, unknown DIDs blacklisted |
| `test_db_error_returns_failed_status` | A DB failure returns `status: false` with empty lists |
| `test_rejects_empty_did_list` | An empty `dids` list is rejected with 422 |

### `database/test_whitelist.py` — `db.get_whitelisted_actors`

| Test | Checks |
|---|---|
| `test_get_whitelisted_actors_checks_agents_and_users` | Returns active DIDs from both `agents` and `user_id`; inactive and unknown DIDs are excluded |
