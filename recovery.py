"""Write-ahead reconciliation journal for chain -> Postgres dual writes.

The blockchain is append-only and authoritative; Postgres is a derived index.
When a chain write succeeds but the follow-up DB write fails (or the process
dies before it runs), we must not lose the DB write. So each DB write is
journaled to a per-record file under ``.log/`` *before* it is attempted, and
the file is deleted only after the write succeeds. On the next startup,
``replay()`` re-applies any leftover entries.

Replay handlers must be idempotent: the original write may actually have
landed before the crash, so re-applying it has to be a safe no-op.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from db import AgentConflictError, add_registered_agent, set_agent_policy

LOG_DIR = Path(__file__).parent / ".log"


def _apply_add_registered_agent(payload: dict) -> None:
    try:
        add_registered_agent(**payload)
    except AgentConflictError:
        # Row already exists — the original write did land. Idempotent success.
        pass


def _apply_set_agent_policy(payload: dict) -> None:
    # UPDATE is naturally idempotent; re-running it is harmless.
    set_agent_policy(**payload)


# Maps a journal op name to the DB write that applies it.
_HANDLERS = {
    "add_registered_agent": _apply_add_registered_agent,
    "set_agent_policy": _apply_set_agent_policy,
}


def journal(op: str, payload: dict) -> Path | None:
    """Durably record a pending DB write before attempting it (write-ahead).

    Returns the entry path, or None if journaling itself failed — in which case
    the caller still attempts the DB write, just without a recovery safety net.
    """
    if op not in _HANDLERS:
        raise ValueError(f"unknown journal op: {op}")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = LOG_DIR / f"{uuid4().hex}.json"
        tmp = Path(f"{entry}.tmp")
        tmp.write_text(json.dumps({"op": op, "payload": payload}), encoding="utf-8")
        os.replace(tmp, entry)  # atomic create — never observe a half-written entry
        return entry
    except Exception as exc:
        print(f"recovery: warning: failed to journal {op}, proceeding without safety net: {exc}")
        return None


def clear(entry: Path | None) -> None:
    """Remove a journal entry after its DB write succeeded."""
    if entry is None:
        return
    try:
        entry.unlink(missing_ok=True)
    except Exception as exc:
        print(f"recovery: warning: failed to clear journal entry {entry.name}: {exc}")


def replay() -> None:
    """Re-apply any pending DB writes left by a prior failed or crashed run.

    Called once at startup. Entries are processed in creation order so inserts
    precede dependent updates. An entry whose write succeeds is removed; one
    that fails (e.g. DB still unreachable) is kept for the next start.
    """
    if not LOG_DIR.exists():
        return

    entries = sorted(LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for entry in entries:
        try:
            record = json.loads(entry.read_text(encoding="utf-8"))
            op = record["op"]
            payload = record["payload"]
        except Exception as exc:
            print(f"recovery: warning: cannot parse {entry.name}, leaving in place: {exc}")
            continue

        handler = _HANDLERS.get(op)
        if handler is None:
            print(f"recovery: warning: unknown op '{op}' in {entry.name}, leaving in place")
            continue

        try:
            handler(payload)
        except Exception as exc:
            # DB still unavailable or some other failure — keep for next start.
            print(f"recovery: warning: replay of {entry.name} ({op}) failed, will retry: {exc}")
            continue

        clear(entry)
        print(f"recovery: reconciled '{op}' from {entry.name}")
