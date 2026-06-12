from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool

from config import settings

# Opened lazily at app startup (see init_db) rather than at import time so the
# process can start without a reachable database during tooling/imports.
pool = ConnectionPool(conninfo=settings.database_url, open=False)


SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    did          TEXT PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    org_id       TEXT NOT NULL,
    deployer_did TEXT NOT NULL,
    policy       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin (
    did      TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    org      TEXT NOT NULL
);
"""


class AgentConflictError(Exception):
    pass


class AdminConflictError(Exception):
    pass


def init_db() -> None:
    """Open the connection pool and ensure the schema exists. Call once at startup."""
    pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def add_registered_agent(
    did: str,
    agent_name: str,
    org_id: str,
    deployer_did: str,
    policy: str,
) -> None:
    """Persist a freshly deployed agent. Raises AgentConflictError if the did exists."""
    try:
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO agents (did, agent_name, org_id, deployer_did, policy)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (did, agent_name, org_id, deployer_did, policy),
            )
    except UniqueViolation as exc:
        raise AgentConflictError(f"agent with did '{did}' is already registered") from exc


def add_admin(did: str, username: str, org: str) -> None:
    """Persist an admin. Raises AdminConflictError if the did or username exists."""
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO admin (did, username, org) VALUES (%s, %s, %s)",
                (did, username, org),
            )
    except UniqueViolation as exc:
        raise AdminConflictError(
            f"admin with did '{did}' or username '{username}' is already registered"
        ) from exc


def get_username_by_did(did: str) -> str | None:
    """Return the username registered for a did, or None if unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT username FROM admin WHERE did = %s",
            (did,),
        ).fetchone()
    return row[0] if row else None

def get_all_agents() -> list[dict[str, str]]:
    """Return all registered agents (without policy — see get_agent_by_did for that)."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT did, agent_name, org_id, deployer_did FROM agents"
        ).fetchall()
    return [
        {
            "did": row[0],
            "agent_name": row[1],
            "org_id": row[2],
            "deployer_did": row[3],
        }
        for row in rows
    ]


def get_agent_by_did(did: str) -> dict[str, str] | None:
    """Return a single agent's full record (including policy), or None if unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT did, agent_name, org_id, deployer_did, policy FROM agents WHERE did = %s",
            (did,),
        ).fetchone()
    if row is None:
        return None
    return {
        "did": row[0],
        "agent_name": row[1],
        "org_id": row[2],
        "deployer_did": row[3],
        "policy": row[4],
    }


def set_agent_policy(org_id: str, agent_name: str, policy: str) -> bool:
    """Update an agent's stored policy, matched by (org_id, agent_name).

    Returns True if a row was updated, False if no matching agent exists.
    """
    with pool.connection() as conn:
        cur = conn.execute(
            "UPDATE agents SET policy = %s WHERE org_id = %s AND agent_name = %s",
            (policy, org_id, agent_name),
        )
    return cur.rowcount > 0