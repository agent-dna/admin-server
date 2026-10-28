"""Shared fixtures for DB tests.

DB tests run real queries against a throwaway Postgres container started by
testcontainers, so Docker must be running. One container is shared by the
whole test session; each test gets its own schema, dropped afterwards.

Use `test_pool` for an empty schema, or `seed` for one populated with the
sample data in SeedData.
"""

import uuid
from dataclasses import dataclass

import psycopg
import pytest
from psycopg_pool import ConnectionPool
from testcontainers.community.postgres import PostgresContainer

import db

# Same image as docker-compose.yml.
POSTGRES_IMAGE = "postgres:18.3"


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer(POSTGRES_IMAGE, driver=None) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def test_pool(postgres_url, monkeypatch):
    """Point db.pool at a fresh schema with the app's tables created."""
    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')

    pool = ConnectionPool(
        postgres_url,
        kwargs={"options": f"-c search_path={schema}"},
        min_size=1,
    )
    monkeypatch.setattr(db, "pool", pool)
    with pool.connection() as conn:
        conn.execute(db.SCHEMA)

    yield pool

    pool.close()
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


@dataclass(frozen=True)
class SeedData:
    """Sample rows inserted by the `seed` fixture. DIDs are IPFS CIDv1 values."""

    active_agent: str = "bafybeie5nqv6kd3qnfjupgvz34woh3oksc3iau6abmyajn7qvtf6d2ho34"
    inactive_agent: str = "bafybeicg2rebjoofv4kbyovkw7af3rpiitvnl6i7ckcywaq6xjcxnc2mby"
    user_email: str = "user@example.com"
    user_api_key: str = "user-api-key"
    active_user: str = "bafybeiasb5vpmaounyilfuxbd3lryvosl4yefqrfahsb2esg46q6tu6y5q"
    inactive_user: str = "bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq"
    # Not inserted anywhere.
    unknown: str = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"


@pytest.fixture
def seed(test_pool) -> SeedData:
    """Populate the test schema with SeedData and return it.

    Rows are inserted with plain SQL rather than db.py functions, so tests
    don't depend on the code they're testing to set up their data.
    """
    data = SeedData()
    with test_pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO agents (did, agent_name, org_id, deployer_did, policy, is_active)
            VALUES (%s, 'active-agent', 'org-1', 'deployer', '', TRUE),
                   (%s, 'inactive-agent', 'org-1', 'deployer', '', FALSE)
            """,
            (data.active_agent, data.inactive_agent),
        )
        conn.execute(
            "INSERT INTO users (email, api_key) VALUES (%s, %s)",
            (data.user_email, data.user_api_key),
        )
        conn.execute(
            """
            INSERT INTO user_id (id, email, is_active)
            VALUES (%s, %s, TRUE),
                   (%s, %s, FALSE)
            """,
            (data.active_user, data.user_email, data.inactive_user, data.user_email),
        )
    return data
