from __future__ import annotations

import os
import re
from csv import DictWriter
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from ...engine import now, read_json, write_json

CLAIMS_FILE = "claims.json"

VALID_CLAIM_TYPES = {
    "adoption",
    "architecture",
    "benchmark",
    "cost",
    "demo",
    "deployment",
    "medical",
    "release",
    "safety",
    "security",
}
VALID_RISKS = {"low", "medium", "high", "critical"}
VALID_STATUS = {"needs-review", "tracking", "rejected", "validated"}
VALID_RECOMMENDATIONS = {"reject", "verify-first", "track", "validated"}
VALID_PHYSICAL_SYSTEMS = {
    "",
    "autonomous-driving",
    "embodied-agent",
    "robotaxi",
    "robotics",
    "world-model",
    "other",
}
VALID_EVIDENCE_STATUS = {
    "",
    "unverified",
    "source-only",
    "reported-metric",
    "reproduced",
    "validated",
}
VALID_SAFETY_GATES = {
    "",
    "none",
    "source-needed",
    "safety-eval-needed",
    "deployment-proof-needed",
    "regulatory-proof-needed",
    "financial-source-needed",
    "clinical-validation-needed",
}
VALID_DEPLOYMENT_STAGES = {"", "unknown", "research", "demo", "pilot", "production-claimed"}
MODEL_TERMS = (
    "GPT",
    "Claude",
    "Fable",
    "GLM",
    "Gemma",
    "DeepSeek",
    "Gemini",
    "Cursor",
    "Kimi",
    "Qwen",
    "Llama",
    "Mistral",
    "Grok",
    "Seed",
)


@dataclass(frozen=True)
class ClaimRecord:
    id: str
    subject: str
    claim_type: str
    claim: str
    source_url: str
    benchmark: str = ""
    cost_evidence: str = ""
    safety_evidence: str = ""
    reproduction_evidence: str = ""
    adoption_evidence: str = ""
    physical_system: str = ""
    evidence_status: str = ""
    safety_gate: str = ""
    deployment_stage: str = ""
    geography: str = ""
    metric: str = ""
    risk: str = "medium"
    status: str = "needs-review"
    recommendation: str = "verify-first"
    missing_evidence: list[str] | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["missing_evidence"] = self.missing_evidence or []
        stamp = now()
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


def state_path(filename: str = CLAIMS_FILE) -> Path:
    root = os.environ.get("MODEL_CLAIM_DILIGENCE_STATE_DIR")
    base = Path(root).expanduser() if root else Path.cwd() / ".model-claim-diligence"
    return base / filename


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return cleaned or "claim"


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or state_path()
    data = read_json(path, {"version": 1, "claims": []})
    if not isinstance(data.get("claims"), list):
        raise ValueError(f"invalid claims file: {path}")
    return data


def save(data: dict[str, Any], path: Path | None = None) -> None:
    write_json(path or state_path(), data)


def infer_risk(
    claim_type: str,
    *,
    safety_evidence: str = "",
    physical_system: str = "",
    safety_gate: str = "",
) -> str:
    if physical_system and safety_gate not in {"", "none"} and not safety_evidence.strip():
        return "high"
    if claim_type in {"medical", "safety", "security"} and not safety_evidence.strip():
        return "high"
    if claim_type in {"benchmark", "cost", "adoption", "deployment"}:
        return "medium"
    return "low"


def required_evidence(raw: dict[str, Any]) -> list[str]:
    claim_type = str(raw.get("claim_type", "")).strip()
    risk = str(raw.get("risk", "")).strip()
    missing: list[str] = []

    if claim_type == "benchmark" and not present(raw, "benchmark", "reproduction_evidence"):
        missing.append("benchmark or reproduction_evidence")
    if claim_type == "cost" and not present(raw, "cost_evidence"):
        missing.append("cost_evidence")
    if claim_type in {"safety", "security"} and not present(raw, "safety_evidence"):
        missing.append("safety_evidence")
    if claim_type == "medical":
        if not present(raw, "safety_evidence"):
            missing.append("safety_evidence")
        if not present(raw, "reproduction_evidence"):
            missing.append("clinical validation or reproduction_evidence")
        if not present(raw, "metric", "benchmark"):
            missing.append("clinical metric or benchmark")
    if claim_type == "deployment" and not present(raw, "reproduction_evidence"):
        missing.append("reproduction_evidence")
    if claim_type == "adoption" and not present(raw, "adoption_evidence"):
        missing.append("adoption_evidence")
    if risk in {"high", "critical"} and not present(
        raw, "reproduction_evidence", "safety_evidence"
    ):
        missing.append("reproduction_evidence or safety_evidence")
    if present(raw, "physical_system"):
        safety_gate = str(raw.get("safety_gate", "")).strip()
        deployment_stage = str(raw.get("deployment_stage", "")).strip()
        evidence_status = str(raw.get("evidence_status", "")).strip()
        if not evidence_status:
            missing.append("evidence_status")
        if not safety_gate:
            missing.append("safety_gate")
        if not deployment_stage:
            missing.append("deployment_stage")
        if safety_gate and safety_gate != "none" and not present(raw, "safety_evidence"):
            missing.append("safety_evidence")
        if deployment_stage in {"pilot", "production-claimed"} and not present(
            raw, "reproduction_evidence"
        ):
            missing.append("reproduction_evidence")
        if evidence_status in {"unverified", "source-only"} and not present(
            raw, "metric", "benchmark", "reproduction_evidence", "adoption_evidence"
        ):
            missing.append("metric, benchmark, reproduction_evidence, or adoption_evidence")
    return missing


def recommendation_for(raw: dict[str, Any]) -> str:
    source_url = str(raw.get("source_url", "")).strip()
    status = str(raw.get("status", "")).strip()
    missing = required_evidence(raw)
    if not source_url.startswith(("https://", "http://")):
        return "reject"
    if missing:
        return "verify-first"
    if status == "validated":
        return "validated"
    return "track"


def make_record(
    *,
    subject: str,
    claim_type: str,
    claim: str,
    source_url: str,
    benchmark: str = "",
    cost_evidence: str = "",
    safety_evidence: str = "",
    reproduction_evidence: str = "",
    adoption_evidence: str = "",
    physical_system: str = "",
    evidence_status: str = "",
    safety_gate: str = "",
    deployment_stage: str = "",
    geography: str = "",
    metric: str = "",
    risk: str = "",
    status: str = "needs-review",
) -> ClaimRecord:
    cleaned_claim_type = claim_type.strip()
    if cleaned_claim_type not in VALID_CLAIM_TYPES:
        valid_types = sorted(VALID_CLAIM_TYPES)
        raise ValueError(
            f"invalid claim_type {cleaned_claim_type!r}; expected one of {valid_types}"
        )
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(VALID_STATUS)}")

    cleaned_physical_system = physical_system.strip()
    cleaned_evidence_status = evidence_status.strip()
    cleaned_safety_gate = safety_gate.strip()
    cleaned_deployment_stage = deployment_stage.strip()
    validate_choice("physical_system", cleaned_physical_system, VALID_PHYSICAL_SYSTEMS)
    validate_choice("evidence_status", cleaned_evidence_status, VALID_EVIDENCE_STATUS)
    validate_choice("safety_gate", cleaned_safety_gate, VALID_SAFETY_GATES)
    validate_choice("deployment_stage", cleaned_deployment_stage, VALID_DEPLOYMENT_STAGES)

    chosen_risk = risk.strip() or infer_risk(
        cleaned_claim_type,
        safety_evidence=safety_evidence,
        physical_system=cleaned_physical_system,
        safety_gate=cleaned_safety_gate,
    )
    if chosen_risk not in VALID_RISKS:
        raise ValueError(f"invalid risk {chosen_risk!r}; expected one of {sorted(VALID_RISKS)}")

    raw = {
        "claim_type": cleaned_claim_type,
        "source_url": source_url.strip(),
        "benchmark": benchmark.strip(),
        "cost_evidence": cost_evidence.strip(),
        "safety_evidence": safety_evidence.strip(),
        "reproduction_evidence": reproduction_evidence.strip(),
        "adoption_evidence": adoption_evidence.strip(),
        "physical_system": cleaned_physical_system,
        "evidence_status": cleaned_evidence_status,
        "safety_gate": cleaned_safety_gate,
        "deployment_stage": cleaned_deployment_stage,
        "geography": geography.strip(),
        "metric": metric.strip(),
        "risk": chosen_risk,
        "status": status,
    }
    missing = required_evidence(raw)
    stamp = now()
    return ClaimRecord(
        id=slug(f"{subject}-{cleaned_claim_type}-{source_url or claim}")[:80],
        subject=subject.strip(),
        claim_type=cleaned_claim_type,
        claim=claim.strip(),
        source_url=source_url.strip(),
        benchmark=benchmark.strip(),
        cost_evidence=cost_evidence.strip(),
        safety_evidence=safety_evidence.strip(),
        reproduction_evidence=reproduction_evidence.strip(),
        adoption_evidence=adoption_evidence.strip(),
        physical_system=cleaned_physical_system,
        evidence_status=cleaned_evidence_status,
        safety_gate=cleaned_safety_gate,
        deployment_stage=cleaned_deployment_stage,
        geography=geography.strip(),
        metric=metric.strip(),
        risk=chosen_risk,
        status=status,
        recommendation=recommendation_for(raw),
        missing_evidence=missing,
        created_at=stamp,
        updated_at=stamp,
    )


def upsert(data: dict[str, Any], record: ClaimRecord) -> dict[str, Any]:
    claims = data.setdefault("claims", [])
    if not isinstance(claims, list):
        raise ValueError("state claims must be a list")
    record_dict = record.to_dict()
    for index, existing in enumerate(claims):
        if isinstance(existing, dict) and existing.get("id") == record.id:
            record_dict["created_at"] = str(existing.get("created_at") or record_dict["created_at"])
            record_dict["updated_at"] = now()
            claims[index] = record_dict
            return record_dict
    claims.append(record_dict)
    return record_dict


def validate_record(raw: dict[str, Any]) -> list[Finding]:
    rid = str(raw.get("id") or "(missing-id)")
    findings: list[Finding] = []
    for key in ("id", "subject", "claim_type", "claim", "source_url"):
        if not str(raw.get(key, "")).strip():
            findings.append(Finding("missing-field", rid, f"missing required field: {key}"))
    claim_type = str(raw.get("claim_type", "")).strip()
    if claim_type and claim_type not in VALID_CLAIM_TYPES:
        findings.append(Finding("invalid-claim-type", rid, f"invalid claim_type: {claim_type}"))
    risk = str(raw.get("risk", "")).strip()
    if risk and risk not in VALID_RISKS:
        findings.append(Finding("invalid-risk", rid, f"invalid risk: {risk}"))
    status = str(raw.get("status", "")).strip()
    if status and status not in VALID_STATUS:
        findings.append(Finding("invalid-status", rid, f"invalid status: {status}"))
    recommendation = str(raw.get("recommendation", "")).strip()
    if recommendation and recommendation not in VALID_RECOMMENDATIONS:
        findings.append(
            Finding("invalid-recommendation", rid, f"invalid recommendation: {recommendation}")
        )
    for key, valid in (
        ("physical_system", VALID_PHYSICAL_SYSTEMS),
        ("evidence_status", VALID_EVIDENCE_STATUS),
        ("safety_gate", VALID_SAFETY_GATES),
        ("deployment_stage", VALID_DEPLOYMENT_STAGES),
    ):
        value = str(raw.get(key, "")).strip()
        if value and value not in valid:
            findings.append(Finding(f"invalid-{key}", rid, f"invalid {key}: {value}"))
    if str(raw.get("source_url", "")).strip() and recommendation_for(raw) == "reject":
        findings.append(Finding("invalid-source", rid, "source_url must be http(s)"))
    missing = required_evidence(raw)
    if missing and recommendation not in {"reject", "verify-first"}:
        findings.append(
            Finding("missing-evidence", rid, f"recommendation ignores missing evidence: {missing}")
        )
    if status == "validated" and recommendation != "validated":
        findings.append(Finding("not-validated", rid, "validated records need complete evidence"))
    return findings


def validate(data: dict[str, Any]) -> list[Finding]:
    claims = data.get("claims", [])
    if not isinstance(claims, list):
        return [Finding("invalid-state", "(state)", "claims must be a list")]
    findings: list[Finding] = []
    seen: set[str] = set()
    for raw in claims:
        if not isinstance(raw, dict):
            findings.append(Finding("invalid-record", "(state)", "claim entries must be objects"))
            continue
        rid = str(raw.get("id") or "")
        if rid in seen:
            findings.append(Finding("duplicate-id", rid, "duplicate claim id"))
        seen.add(rid)
        findings.extend(validate_record(raw))
    return findings


def export_markdown(data: dict[str, Any], *, only_validated: bool = False) -> str:
    rows = []
    for raw in data.get("claims", []):
        if not isinstance(raw, dict):
            continue
        if only_validated and raw.get("recommendation") != "validated":
            continue
        rows.append(raw)
    lines = ["# Model Claim Diligence", ""]
    for raw in rows:
        lines.extend(
            [
                f"## {raw.get('subject', '')}",
                "",
                f"- Claim type: `{raw.get('claim_type', '')}`",
                f"- Risk: `{raw.get('risk', '')}`",
                f"- Recommendation: `{raw.get('recommendation', '')}`",
                f"- Source: {raw.get('source_url', '') or '(missing)'}",
                f"- Missing evidence: {', '.join(raw.get('missing_evidence') or []) or 'none'}",
                physical_claim_line(raw),
                "",
                str(raw.get("claim", "")),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def export_event_graph_csv(data: dict[str, Any], *, only_validated: bool = False) -> str:
    rows = []
    for raw in data.get("claims", []):
        if not isinstance(raw, dict):
            continue
        if only_validated and raw.get("recommendation") != "validated":
            continue
        if not str(raw.get("physical_system", "")).strip():
            continue
        rows.extend(physical_event_rows(raw))

    output = StringIO()
    fieldnames = [
        "ts",
        "src",
        "dst",
        "rel",
        "details",
        "source_url",
        "claim_type",
        "evidence_status",
        "safety_gate",
        "deployment_stage",
        "metric",
    ]
    writer = DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def physical_event_rows(raw: dict[str, Any]) -> list[dict[str, str]]:
    claim_id = str(raw.get("id", "")).strip()
    source = f"claim:{claim_id}"
    edges = [
        (f"subject:{raw.get('subject', '')}", "about_subject"),
        (f"system:{raw.get('physical_system', '')}", "about_system"),
        (f"evidence:{raw.get('evidence_status', '')}", "has_evidence_status"),
        (f"safety_gate:{raw.get('safety_gate', '')}", "requires_safety_gate"),
        (f"stage:{raw.get('deployment_stage', '')}", "has_deployment_stage"),
    ]
    geography = str(raw.get("geography", "")).strip()
    if geography:
        edges.append((f"geo:{geography}", "has_geography"))
    return [physical_event_row(raw, source, dst, rel) for dst, rel in edges if dst.split(":", 1)[1]]


def physical_event_row(raw: dict[str, Any], source: str, dst: str, rel: str) -> dict[str, str]:
    return {
        "ts": str(raw.get("updated_at") or raw.get("created_at") or now()),
        "src": source,
        "dst": dst,
        "rel": rel,
        "details": str(raw.get("claim", "")),
        "source_url": str(raw.get("source_url", "")),
        "claim_type": str(raw.get("claim_type", "")),
        "evidence_status": str(raw.get("evidence_status", "")),
        "safety_gate": str(raw.get("safety_gate", "")),
        "deployment_stage": str(raw.get("deployment_stage", "")),
        "metric": str(raw.get("metric", "")),
    }


def physical_claim_line(raw: dict[str, Any]) -> str:
    physical_system = str(raw.get("physical_system", "")).strip()
    if not physical_system:
        return "- Physical AI gate: `not-applicable`"
    parts = [
        f"system={physical_system}",
        f"evidence={raw.get('evidence_status', '') or 'missing'}",
        f"safety_gate={raw.get('safety_gate', '') or 'missing'}",
        f"stage={raw.get('deployment_stage', '') or 'missing'}",
    ]
    return f"- Physical AI gate: `{'; '.join(parts)}`"


def validate_choice(field: str, value: str, valid: set[str]) -> None:
    if value not in valid:
        raise ValueError(f"invalid {field} {value!r}; expected one of {sorted(valid)}")


def present(raw: dict[str, Any], *keys: str) -> bool:
    return any(str(raw.get(key, "")).strip() for key in keys)
