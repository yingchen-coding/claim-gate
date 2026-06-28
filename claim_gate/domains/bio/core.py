from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ...engine import now, read_json, write_json

STATE_DIR_ENV = "BIO_AI_CLAIM_GATE_STATE_DIR"
DEFAULT_STATE_DIR = Path(".bio-ai-claim-gate")
CLAIMS_FILE = "claims.json"

VALID_HAZARD_CLASSES = {"unknown", "low", "dual-use", "regulated", "high"}
VALID_STATUS = {"needs-review", "tracking", "rejected", "validated"}
CONSTRUCTION_INTENT_TERMS = (
    "protocol",
    "wet-lab",
    "wet lab",
    "sequence design",
    "gene edit",
    "synthesize",
    "construct",
    "build organism",
    "lab procedure",
)


@dataclass(frozen=True)
class BioClaimRecord:
    id: str
    subject: str
    claim: str
    source_url: str
    hazard_class: str
    validation: str = ""
    independent_reproduction: str = ""
    safety_review: str = ""
    misuse_assessment: str = ""
    limitations: str = ""
    status: str = "needs-review"
    recommendation: str = "verify-first"
    blocked_uses: list[str] | None = None
    missing_evidence: list[str] | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        stamp = now()
        data = asdict(self)
        data["blocked_uses"] = self.blocked_uses or default_blocked_uses()
        data["missing_evidence"] = self.missing_evidence or []
        data["created_at"] = self.created_at or stamp
        data["updated_at"] = self.updated_at or stamp
        return data


@dataclass(frozen=True)
class Finding:
    code: str
    record_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def slug(value: str, default: str = "claim", limit: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned[:limit] or default


def state_dir() -> Path:
    configured = os.environ.get(STATE_DIR_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_STATE_DIR


def state_path(name: str = CLAIMS_FILE) -> Path:
    return state_dir() / name


def default_blocked_uses() -> list[str]:
    return [
        "biological construction guidance",
        "wet-lab protocol generation",
        "sequence or organism design",
        "deployment or clinical use",
    ]


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or state_path()
    data = read_json(path, {"version": 1, "claims": []})
    if not isinstance(data.get("claims"), list):
        raise ValueError(f"invalid bio-AI claims file: {path}")
    return data


def save(data: dict[str, Any], path: Path | None = None) -> None:
    write_json(path or state_path(), data)


def missing_evidence(raw: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _present(raw, "validation"):
        missing.append("validation")
    if not _present(raw, "independent_reproduction"):
        missing.append("independent_reproduction")
    if not _present(raw, "safety_review"):
        missing.append("safety_review")
    hazard_class = str(raw.get("hazard_class", "unknown"))
    if hazard_class in {"dual-use", "regulated", "high"} and not _present(
        raw,
        "misuse_assessment",
    ):
        missing.append("misuse_assessment")
    if not _present(raw, "limitations"):
        missing.append("limitations")
    return missing


def recommendation_for(raw: dict[str, Any]) -> str:
    source = str(raw.get("source_url", "")).strip()
    hazard_class = str(raw.get("hazard_class", "unknown")).strip()
    status = str(raw.get("status", "needs-review")).strip()
    claim_text = f"{raw.get('subject', '')} {raw.get('claim', '')}".lower()
    if not source.startswith(("https://", "http://")):
        return "reject"
    if any(term in claim_text for term in CONSTRUCTION_INTENT_TERMS):
        return "reject"
    if missing_evidence(raw):
        return "verify-first"
    if status == "validated" and hazard_class in {"unknown", "low"}:
        return "track"
    return "verify-first"


def make_record(
    *,
    subject: str,
    claim: str,
    source_url: str,
    hazard_class: str = "unknown",
    validation: str = "",
    independent_reproduction: str = "",
    safety_review: str = "",
    misuse_assessment: str = "",
    limitations: str = "",
    status: str = "needs-review",
) -> BioClaimRecord:
    hazard_class = hazard_class.strip() or "unknown"
    if hazard_class not in VALID_HAZARD_CLASSES:
        raise ValueError(
            f"invalid hazard_class {hazard_class!r}; expected one of {sorted(VALID_HAZARD_CLASSES)}"
        )
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(VALID_STATUS)}")
    raw = {
        "subject": subject.strip(),
        "claim": claim.strip(),
        "source_url": source_url.strip(),
        "hazard_class": hazard_class,
        "validation": validation.strip(),
        "independent_reproduction": independent_reproduction.strip(),
        "safety_review": safety_review.strip(),
        "misuse_assessment": misuse_assessment.strip(),
        "limitations": limitations.strip(),
        "status": status,
    }
    return BioClaimRecord(
        id=slug(f"{subject}-{source_url or claim}"),
        subject=raw["subject"],
        claim=raw["claim"],
        source_url=raw["source_url"],
        hazard_class=hazard_class,
        validation=raw["validation"],
        independent_reproduction=raw["independent_reproduction"],
        safety_review=raw["safety_review"],
        misuse_assessment=raw["misuse_assessment"],
        limitations=raw["limitations"],
        status=status,
        recommendation=recommendation_for(raw),
        blocked_uses=default_blocked_uses(),
        missing_evidence=missing_evidence(raw),
        created_at=now(),
        updated_at=now(),
    )


def upsert(data: dict[str, Any], record: BioClaimRecord) -> dict[str, Any]:
    claims = data.setdefault("claims", [])
    if not isinstance(claims, list):
        raise ValueError("state claims must be a list")
    raw = record.to_dict()
    for index, existing in enumerate(claims):
        if isinstance(existing, dict) and existing.get("id") == record.id:
            raw["created_at"] = str(existing.get("created_at") or raw["created_at"])
            raw["updated_at"] = now()
            claims[index] = raw
            return raw
    claims.append(raw)
    return raw


def validate_record(raw: dict[str, Any]) -> list[Finding]:
    rid = str(raw.get("id") or "(missing-id)")
    findings: list[Finding] = []
    for key in ("subject", "claim", "source_url", "hazard_class"):
        if not str(raw.get(key, "")).strip():
            findings.append(Finding("BIO001", rid, f"missing required field: {key}"))
    hazard_class = str(raw.get("hazard_class", "")).strip()
    if hazard_class and hazard_class not in VALID_HAZARD_CLASSES:
        findings.append(Finding("BIO002", rid, f"invalid hazard_class: {hazard_class}"))
    if not str(raw.get("source_url", "")).startswith(("https://", "http://")):
        findings.append(Finding("BIO101", rid, "claim needs a public source URL"))
    for missing in missing_evidence(raw):
        findings.append(Finding("BIO102", rid, f"missing evidence: {missing}"))
    if raw.get("recommendation") == "reject":
        findings.append(Finding("BIO201", rid, "claim is rejected for construction or source risk"))
    if raw.get("status") == "validated" and raw.get("recommendation") != "track":
        findings.append(
            Finding("BIO202", rid, "validated bio-AI claim still lacks safe tracking gate")
        )
    return findings


def validate_state(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for raw in data.get("claims", []):
        if not isinstance(raw, dict):
            findings.append(Finding("BIO000", "(unknown)", "claim must be an object"))
            continue
        rid = str(raw.get("id") or "")
        if rid in seen:
            findings.append(Finding("BIO103", rid, "duplicate bio-AI claim id"))
        seen.add(rid)
        findings.extend(validate_record(raw))
    return findings


def render(data: dict[str, Any]) -> str:
    claims = [raw for raw in data.get("claims", []) if isinstance(raw, dict)]
    if not claims:
        return "No bio-AI claims."
    lines: list[str] = []
    for raw in claims:
        missing = raw.get("missing_evidence") or missing_evidence(raw)
        missing_text = f" missing={'; '.join(missing)}" if missing else ""
        lines.append(
            f"{raw.get('id', '')} [{raw.get('hazard_class', '')}/{raw.get('status', '')}] "
            f"{raw.get('recommendation', recommendation_for(raw))}{missing_text}"
        )
        lines.append(f"  {raw.get('subject', '')}: {raw.get('claim', '')}")
        lines.append(f"  source: {raw.get('source_url', '')}")
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    claims = [raw for raw in data.get("claims", []) if isinstance(raw, dict)]
    lines = ["# Bio-AI Claim Gate", "", f"Claims: {len(claims)}", ""]
    lines.append(
        "This file is an evidence ledger. It is not biological construction guidance, "
        "wet-lab protocol guidance, sequence design guidance, or deployment approval."
    )
    lines.append("")
    for raw in claims:
        missing = raw.get("missing_evidence") or missing_evidence(raw)
        lines.append(f"## {raw.get('subject', '(unknown)')}")
        lines.append(f"- ID: `{raw.get('id', '')}`")
        lines.append(f"- Hazard class: {raw.get('hazard_class', '')}")
        lines.append(f"- Status: {raw.get('status', '')}")
        lines.append(f"- Recommendation: {raw.get('recommendation', recommendation_for(raw))}")
        lines.append(f"- Source: {raw.get('source_url', '')}")
        blocked_uses = raw.get("blocked_uses") or default_blocked_uses()
        lines.append(f"- Blocked uses: {'; '.join(blocked_uses)}")
        if missing:
            lines.append(f"- Missing evidence: {'; '.join(missing)}")
        for key, label in (
            ("validation", "Validation"),
            ("independent_reproduction", "Independent reproduction"),
            ("safety_review", "Safety review"),
            ("misuse_assessment", "Misuse assessment"),
            ("limitations", "Limitations"),
        ):
            value = str(raw.get(key, "")).strip()
            if value:
                lines.append(f"- {label}: {value}")
        lines.append("")
        lines.append(str(raw.get("claim", "")).strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _present(raw: dict[str, Any], *keys: str) -> bool:
    return any(str(raw.get(key, "")).strip() for key in keys)

