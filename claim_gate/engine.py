"""Shared engine primitives for every claim-gate domain.

Domains differ in their record schema, vocabulary, validation rules, and scoring — but they all
sit on the same ledger plumbing. The genuinely common, behaviour-neutral primitives live here so
each domain doesn't re-implement them. Domain-specific concerns (slug rules, state layout,
validation, scoring, recommendation) stay in the domain module on purpose.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    """UTC timestamp, seconds precision — the canonical stamp for every ledger record."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    """Read a JSON object from ``path``, or return ``default`` if it does not exist."""
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A ledger is the record of truth; unlike a cache we must NOT silently reset it. Surface a
        # clear, actionable error instead of a raw traceback so the user can restore from git/backup.
        raise ValueError(
            f"ledger is not valid JSON: {path} ({exc}). Restore it from version control or a backup; "
            f"claim-gate will not overwrite a corrupt ledger automatically."
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write ``value`` as pretty JSON, atomically, creating parent directories as needed.

    The ledger is the product's whole value; a truncate-then-write (plain write_text) that is
    interrupted — process killed, disk full, two commands racing — leaves a half-written file and
    loses every recorded claim. Writing to a same-directory temp file and os.replace()-ing it in is
    atomic on POSIX and Windows, so a reader (or a crash) never sees a partial ledger.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
