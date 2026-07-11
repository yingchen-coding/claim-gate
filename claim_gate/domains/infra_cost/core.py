from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ...engine import now, read_json, write_json

VALID_SIGNAL_TYPES = {
    "capex-pressure",
    "cloud-margin-risk",
    "cooling-constraint",
    "energy-constraint",
    "gpu-supply",
    "networking-bottleneck",
    "price-shift",
    "utilization-waste",
}
VALID_COST_DRIVERS = {
    "chip",
    "cloud",
    "cooling",
    "datacenter",
    "energy",
    "gpu",
    "networking",
    "server",
    "storage",
    "other",
}
VALID_SOURCE_TYPES = {"company_blog", "public_news", "paper", "filing", "benchmark", "other"}
VALID_IMPACT = {"low", "medium", "high"}
VALID_STATUS = {"needs-review", "watch", "actionable", "validated", "rejected"}
PROHIBITED_SOURCE_HINTS = {"private chat", "dm", "email", "internal", "rumor", "leak"}


@dataclass(frozen=True)
class InfraCostSignal:
    id: str
    title: str
    source_type: str
    source_url: str
    signal_type: str
    cost_driver: str
    summary: str
    observed_on: str = ""
    metric: str = ""
    evidence: str = ""
    decision_signal: str = ""
    impact: str = "medium"
    status: str = "needs-review"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        stamp = now()
        data["created_at"] = self.created_at or stamp
        data["updated_at"] = self.updated_at or stamp
        data["score"] = score_signal(data)
        data["recommendation"] = recommendation(data)
        return data


@dataclass(frozen=True)
class Finding:
    code: str
    signal_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned[:96] or "signal"


def empty_state() -> dict[str, Any]:
    return {"version": 1, "signals": []}


def load(path: Path) -> dict[str, Any]:
    data = read_json(path, empty_state())
    if not isinstance(data.get("signals"), list):
        raise ValueError(f"invalid infra-cost state: {path}")
    return data


def save(data: dict[str, Any], path: Path) -> None:
    write_json(path, data)


def make_signal(
    *,
    title: str,
    source_type: str,
    source_url: str,
    signal_type: str,
    cost_driver: str,
    summary: str,
    observed_on: str = "",
    metric: str = "",
    evidence: str = "",
    decision_signal: str = "",
    impact: str = "medium",
    status: str = "needs-review",
) -> InfraCostSignal:
    if source_type not in VALID_SOURCE_TYPES:
        valid_sources = sorted(VALID_SOURCE_TYPES)
        raise ValueError(f"invalid source_type {source_type!r}; expected {valid_sources}")
    if signal_type not in VALID_SIGNAL_TYPES:
        valid_signals = sorted(VALID_SIGNAL_TYPES)
        raise ValueError(f"invalid signal_type {signal_type!r}; expected {valid_signals}")
    if cost_driver not in VALID_COST_DRIVERS:
        valid_drivers = sorted(VALID_COST_DRIVERS)
        raise ValueError(f"invalid cost_driver {cost_driver!r}; expected {valid_drivers}")
    if impact not in VALID_IMPACT:
        raise ValueError(f"invalid impact {impact!r}; expected {sorted(VALID_IMPACT)}")
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}; expected {sorted(VALID_STATUS)}")
    stamp = now()
    return InfraCostSignal(
        id=slug(f"{signal_type}-{cost_driver}-{source_url or title}"),
        title=title.strip(),
        source_type=source_type,
        source_url=source_url.strip(),
        signal_type=signal_type,
        cost_driver=cost_driver,
        summary=summary.strip(),
        observed_on=observed_on.strip(),
        metric=metric.strip(),
        evidence=evidence.strip(),
        decision_signal=decision_signal.strip(),
        impact=impact,
        status=status,
        created_at=stamp,
        updated_at=stamp,
    )


def upsert(data: dict[str, Any], signal: InfraCostSignal) -> dict[str, Any]:
    signals = data.setdefault("signals", [])
    if not isinstance(signals, list):
        raise ValueError("state signals must be a list")
    record = signal.to_dict()
    for index, existing in enumerate(signals):
        if isinstance(existing, dict) and existing.get("id") == signal.id:
            record["created_at"] = str(existing.get("created_at") or record["created_at"])
            record["updated_at"] = now()
            signals[index] = record
            return record
    signals.append(record)
    return record


def import_signals(data: dict[str, Any], payload: dict[str, Any]) -> int:
    raw_signals = payload.get("signals")
    if not isinstance(raw_signals, list):
        raise ValueError("import file must contain signals list")
    before = len(data.get("signals", []))
    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        signal = make_signal(
            title=str(raw.get("title", "")),
            source_type=str(raw.get("source_type", "other")),
            source_url=str(raw.get("source_url", "")),
            signal_type=str(raw.get("signal_type", "price-shift")),
            cost_driver=str(raw.get("cost_driver", "other")),
            summary=str(raw.get("summary", "")),
            observed_on=str(raw.get("observed_on", "")),
            metric=str(raw.get("metric", "")),
            evidence=str(raw.get("evidence", "")),
            decision_signal=str(raw.get("decision_signal", "")),
            impact=str(raw.get("impact", "medium")),
            status=str(raw.get("status", "needs-review")),
        )
        upsert(data, signal)
    return len(data.get("signals", [])) - before


def validate_signal(raw: dict[str, Any]) -> list[Finding]:
    signal_id = str(raw.get("id") or "(missing-id)")
    findings: list[Finding] = []
    required = ("title", "source_type", "source_url", "signal_type", "cost_driver", "summary")
    for field in required:
        if not str(raw.get(field, "")).strip():
            findings.append(Finding("IC001", signal_id, f"missing required field: {field}"))
    if str(raw.get("source_type", "")) not in VALID_SOURCE_TYPES:
        findings.append(Finding("IC002", signal_id, "invalid source_type"))
    if str(raw.get("signal_type", "")) not in VALID_SIGNAL_TYPES:
        findings.append(Finding("IC003", signal_id, "invalid signal_type"))
    if str(raw.get("cost_driver", "")) not in VALID_COST_DRIVERS:
        findings.append(Finding("IC004", signal_id, "invalid cost_driver"))
    if str(raw.get("impact", "")) not in VALID_IMPACT:
        findings.append(Finding("IC005", signal_id, "invalid impact"))
    if str(raw.get("status", "")) not in VALID_STATUS:
        findings.append(Finding("IC006", signal_id, "invalid status"))
    if not str(raw.get("source_url", "")).startswith(("https://", "http://")):
        findings.append(Finding("IC101", signal_id, "signal needs a public source URL"))
    joined = " ".join(str(raw.get(key, "")) for key in sorted(raw)).lower()
    for hint in PROHIBITED_SOURCE_HINTS:
        if _contains_hint(joined, hint):
            message = f"private or unreliable source hint: {hint}"
            findings.append(Finding("IC102", signal_id, message))
    if raw.get("impact") == "high" and not str(raw.get("evidence", "")).strip():
        findings.append(Finding("IC103", signal_id, "high-impact signal needs evidence"))
    if raw.get("status") in {"actionable", "validated"} and not str(
        raw.get("decision_signal", "")
    ).strip():
        findings.append(Finding("IC104", signal_id, "actionable signal needs decision_signal"))
    if raw.get("status") == "validated" and not str(raw.get("metric", "")).strip():
        findings.append(Finding("IC105", signal_id, "validated signal needs metric"))
    return findings


def validate_state(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for raw in data.get("signals", []):
        if not isinstance(raw, dict):
            findings.append(Finding("IC000", "(unknown)", "signal must be an object"))
            continue
        signal_id = str(raw.get("id") or "")
        if signal_id in seen:
            findings.append(Finding("IC106", signal_id, "duplicate signal id"))
        seen.add(signal_id)
        findings.extend(validate_signal(raw))
    return findings


def score_signal(raw: dict[str, Any]) -> int:
    score = 0
    if raw.get("impact") == "high":
        score += 40
    elif raw.get("impact") == "medium":
        score += 20
    if raw.get("signal_type") in {"utilization-waste", "energy-constraint", "cooling-constraint"}:
        score += 20
    if str(raw.get("metric", "")).strip():
        score += 15
    if str(raw.get("evidence", "")).strip():
        score += 15
    if str(raw.get("decision_signal", "")).strip():
        score += 10
    return min(score, 100)


def recommendation(raw: dict[str, Any]) -> str:
    if raw.get("status") == "rejected":
        return "ignore"
    if validate_signal(raw):
        return "verify-first"
    score = score_signal(raw)
    if raw.get("status") == "validated":
        return "feed-downstream"
    if score >= 70:
        return "act"
    if score >= 40:
        return "watch"
    return "archive"


def render(data: dict[str, Any]) -> str:
    signals = [raw for raw in data.get("signals", []) if isinstance(raw, dict)]
    if not signals:
        return "No infra cost signals."
    ordered = sorted(signals, key=lambda raw: (-score_signal(raw), str(raw.get("id", ""))))
    lines: list[str] = []
    for raw in ordered:
        lines.append(
            f"{raw.get('id', '')} [{raw.get('impact', '')}/{raw.get('status', '')}] "
            f"score={score_signal(raw)} recommendation={recommendation(raw)}"
        )
        lines.append(
            f"  {raw.get('signal_type', '')} | {raw.get('cost_driver', '')} | "
            f"{raw.get('title', '')}"
        )
        lines.append(f"  source: {raw.get('source_url', '')}")
        if raw.get("decision_signal"):
            lines.append(f"  decision: {raw.get('decision_signal', '')}")
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    signals = [raw for raw in data.get("signals", []) if isinstance(raw, dict)]
    lines = ["# AI Infra Cost Radar", "", f"Signals: {len(signals)}", ""]
    for raw in sorted(signals, key=lambda item: (-score_signal(item), str(item.get("id", "")))):
        lines.append(f"## {raw.get('title', '(unknown)')}")
        lines.append(f"- ID: `{raw.get('id', '')}`")
        lines.append(f"- Signal type: {raw.get('signal_type', '')}")
        lines.append(f"- Cost driver: {raw.get('cost_driver', '')}")
        lines.append(f"- Impact: {raw.get('impact', '')}")
        lines.append(f"- Status: {raw.get('status', '')}")
        lines.append(f"- Score: {score_signal(raw)}")
        lines.append(f"- Recommendation: {recommendation(raw)}")
        lines.append(f"- Source: {raw.get('source_url', '')}")
        if raw.get("metric"):
            lines.append(f"- Metric: {raw.get('metric', '')}")
        if raw.get("decision_signal"):
            lines.append(f"- Decision signal: {raw.get('decision_signal', '')}")
        if raw.get("evidence"):
            lines.append(f"- Evidence: {raw.get('evidence', '')}")
        lines.append("")
        lines.append(str(raw.get("summary", "")).strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _contains_hint(text: str, hint: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(hint) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None
