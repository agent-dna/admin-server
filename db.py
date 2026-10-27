from typing import Any, List

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
    policy       TEXT NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE IF NOT EXISTS admin (
    did      TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email    TEXT NOT NULL DEFAULT '',
    org      TEXT NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    api_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_id (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL REFERENCES users(email),
    is_active BOOL NOT NULL DEFAULT TRUE
);
"""


class AgentConflictError(Exception):
    pass


class AdminConflictError(Exception):
    pass

def migrate_db() -> None:
    with pool.connection() as conn:
        conn.execute("""
            ALTER TABLE admin
            ADD COLUMN IF NOT EXISTS email TEXT NOT NULL DEFAULT '';
        """)
        conn.execute("""
            ALTER TABLE agents
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
        """)

def init_db() -> None:
    """Open the connection pool and ensure the schema exists. Call once at startup."""
    pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA)
    
    migrate_db()

def add_registered_agent(
    id: str,
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
                (id, agent_name, org_id, deployer_did, policy),
            )
    except UniqueViolation as exc:
        raise AgentConflictError(f"agent with did '{id}' is already registered") from exc


def add_admin(did: str, username: str, org: str, password_hash: str, email: str) -> None:
    """Persist an admin. Raises AdminConflictError if the did or username exists."""
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO admin (did, username, org, password, email) VALUES (%s, %s, %s, %s, %s)",
                (did, username, org, password_hash, email),
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


def get_admin_password_by_username(username: str) -> str | None:
    """Return the stored password hash for an admin username, or None if unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT password FROM admin WHERE username = %s",
            (username,),
        ).fetchone()
    return row[0] if row else None


def get_admin_by_username(username: str) -> dict[str, str] | None:
    """Return an admin's did, org, and password hash by username, or None if unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT did, org, password FROM admin WHERE username = %s",
            (username,),
        ).fetchone()
    if row is None:
        return None
    return {"did": row[0], "org": row[1], "password": row[2]}

def get_all_agents() -> list[dict[str, str]]:
    """Return all registered agents (without policy — see get_agent_by_did for that)."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT did, agent_name, org_id, deployer_did, is_active FROM agents"
        ).fetchall()
    return [
        {
            "did": row[0],
            "agent_name": row[1],
            "org_id": row[2],
            "deployer_did": row[3],
            "is_active": row[4],
        }
        for row in rows
    ]


def get_agent_by_did(did: str) -> dict[str, str] | None:
    """Return a single agent's full record (including policy), or None if unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT did, agent_name, org_id, deployer_did, policy, is_active FROM agents WHERE did = %s",
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
        "is_active": row[5],
    }

def is_agent_whitelisted(did: str) -> bool:
    """Return True if the agent is whitelisted (is_active), False otherwise."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT is_active FROM agents WHERE did = %s",
            (did,),
        ).fetchone()
    if row is None:
        return False
    return row[0]

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


def agent_exists(did: str) -> bool:
    """Return True if an agent with this did is registered in the agents table."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM agents WHERE did = %s",
            (did,),
        ).fetchone()
    return row is not None


def set_agent_active_status(did: str, is_active: bool) -> bool:
    """Set an agent's is_active flag, matched by did.

    Returns True if a row was updated, False if no matching agent exists.
    """
    with pool.connection() as conn:
        cur = conn.execute(
            "UPDATE agents SET is_active = %s WHERE did = %s",
            (is_active, did),
        )
    return cur.rowcount > 0


def update_admin_password(username: str, password_hash: str) -> bool:
    """Update an admin's stored password hash, matched by username.

    Returns True if a row was updated, False if no matching admin exists.
    """
    with pool.connection() as conn:
        cur = conn.execute(
            "UPDATE admin SET password = %s WHERE username = %s",
            (password_hash, username),
        )
    return cur.rowcount > 0


def _register_user(email: str, api_key: str, user_id: str):
    """Register a user ID, creating the user on its first registration.

    A user (email, api_key) can own several user IDs, so repeat calls with the
    same email and api_key add another user ID to the existing user.

    Raises ValueError if the email is registered with a different api_key,
    the api_key belongs to another email, or the user ID is already registered.
    The user and user ID are created atomically.
    """

    try:
        with pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO users (email, api_key)
                    VALUES (%s, %s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (email, api_key),
                )

                row = conn.execute(
                    "SELECT api_key FROM users WHERE email = %s",
                    (email,),
                ).fetchone()
                if row[0] != api_key:
                    raise ValueError(
                        "The email is already registered with a different API key"
                    )

                conn.execute(
                    """
                    INSERT INTO user_id (id, email)
                    VALUES (%s, %s)
                    """,
                    (user_id, email),
                )

    except UniqueViolation as exc:
        raise ValueError(
            "The user ID is already registered, or the API key belongs to another email"
        ) from exc


def _set_user_active_status(user_id: str, is_active: bool) -> bool:
    """Update a user ID's active status.

    Returns False if the user ID does not exist.
    """
    with pool.connection() as conn:
        cur = conn.execute(
            """
            UPDATE user_id
            SET is_active = %s
            WHERE id = %s
            """,
            (is_active, user_id),
        )

    return cur.rowcount > 0


def _get_user_active_status(user_id: str) -> bool:
    """Return the active status, or None if the user ID is unknown."""
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT is_active
            FROM user_id
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()

    return row[0] if row else False

def _get_all_users() -> List[Any]:
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, is_active
            FROM user_id
            """
        )
        user_ids = [{"user_id": row[0], "is_active": row[1]} for row in rows.fetchall()]
        print(user_ids)

    return user_ids