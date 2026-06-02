import json
import os
from pathlib import Path

ADMIN_DATA_DIR = Path(__file__).parent / ".admin_data" / "metadata"
ADMIN_STORE_FILE = ADMIN_DATA_DIR / "admins.json"


class AdminConflictError(Exception):
    pass


def _load() -> list[dict]:
    if not ADMIN_STORE_FILE.exists():
        return []
    data = json.loads(ADMIN_STORE_FILE.read_text(encoding="utf-8"))
    return data.get("admins", [])


def _save(records: list[dict]) -> None:
    ADMIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ADMIN_STORE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"admins": records}, indent=2), encoding="utf-8")
    os.replace(tmp, ADMIN_STORE_FILE)


def add_admin(username: str, did: str) -> None:
    records = _load()
    for r in records:
        if r["username"] == username and r["did"] == did:
            return
        if r["username"] == username:
            raise AdminConflictError(
                f"username '{username}' already registered with a different did"
            )
        if r["did"] == did:
            raise AdminConflictError(
                f"did '{did}' already registered under a different username"
            )
    records.append({"username": username, "did": did})
    _save(records)


def get_did_by_username(username: str) -> str | None:
    for r in _load():
        if r["username"] == username:
            return r["did"]
    return None


def get_username_by_did(did: str) -> str | None:
    for r in _load():
        if r["did"] == did:
            return r["username"]
    return None
