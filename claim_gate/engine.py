"""Shared engine primitives for every claim-gate domain.

Domains differ in their record schema, vocabulary, validation rules, and scoring — but they all
sit on the same ledger plumbing. The genuinely common, behaviour-neutral primitives live here so
each domain doesn't re-implement them. Domain-specific concerns (slug rules, state layout,
validation, scoring, recommendation) stay in the domain module on purpose.
"""
from __future__ import annotations

import json
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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write ``value`` as pretty JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
