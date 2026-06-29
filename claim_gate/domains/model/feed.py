from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import core

TITLE_FIELDS = ("title", "headline", "name", "title_ocr")
URL_FIELDS = ("source_url", "url", "article_url", "link")
SUMMARY_FIELDS = ("summary", "notes", "why")


def import_claim_feed(
    path: Path,
    *,
    feed: str = "model_claim_diligence_feed",
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = claim_items(payload, feed)
    data = core.load()
    imported = 0
    updated = 0
    skipped = 0
    claim_ids: list[str] = []
    existing_ids = {
        str(raw.get("id"))
        for raw in data.get("claims", [])
        if isinstance(raw, dict) and raw.get("id")
    }

    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        title = first_text(item, TITLE_FIELDS)
        if not title:
            skipped += 1
            continue
        record = record_from_item(item, title)
        stored = core.upsert(data, record)
        claim_ids.append(stored["id"])
        if stored["id"] in existing_ids:
            updated += 1
        else:
            imported += 1
            existing_ids.add(stored["id"])

    core.save(data)
    return {
        "source_file": path.name,
        "feed": feed,
        "items": len(items),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "claim_ids": claim_ids,
    }


def claim_items(payload: Any, feed: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("claim feed JSON must be an object or list")
    product_ideas = payload.get("product_ideas")
    if isinstance(product_ideas, dict):
        selected = product_ideas.get(feed)
        if isinstance(selected, dict) and isinstance(selected.get("items"), list):
            return selected["items"]
    for key in ("claims", "items", "queue", "cards", "articles"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    raise ValueError("claim feed JSON does not contain a supported item list")


def record_from_item(item: dict[str, Any], title: str) -> core.ClaimRecord:
    summary = first_text(item, SUMMARY_FIELDS)
    source_url = first_text(item, URL_FIELDS)
    claim_type = claim_type_for(title, summary)
    return core.make_record(
        subject=subject_for(title, summary),
        claim_type=claim_type,
        claim=claim_text(title, summary),
        source_url=source_url,
        physical_system=physical_system_for(title, summary),
        evidence_status=evidence_status_for(title, summary),
        safety_gate=safety_gate_for(title, summary),
        deployment_stage=deployment_stage_for(title, summary),
        risk=risk_for(claim_type, title, summary),
        status="needs-review",
    )


def claim_type_for(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(
        term in text
        for term in (
            "medical",
            "clinical",
            "dental",
            "dentfound",
            "doctor",
            "医疗",
            "临床",
            "牙科",
            "诊断",
            "医生",
        )
    ):
        return "medical"
    if any(
        term in text
        for term in (
            "mythos",
            "vulnerability",
            "漏洞",
            "攻防",
            "网络安全",
            "security",
            "exploit",
            "攻击",
            "防御",
            "gptzero",
            "ai detection",
            "ai 写",
            "ai写",
        )
    ):
        return "security"
    if any(
        term in text
        for term in (
            "halos",
            "robot safety",
            "safety system",
            "安全系统",
            "安全架构",
            "安全栈",
        )
    ):
        return "safety"
    if any(
        term in text
        for term in (
            "engram",
            "memory",
            "记忆",
            "context window",
            "上下文窗口",
            "架构",
            "architecture",
        )
    ):
        return "architecture"
    if any(
        term in text
        for term in (
            "robotaxi",
            "自动驾驶",
            "物理ai",
            "physical ai",
            "world model",
            "世界模型",
            "robotics",
            "机器人",
        )
    ):
        return "deployment"
    if any(term in text for term in ("token", "price", "cost", "成本", "价格", "费用")):
        return "cost"
    if any(term in text for term in ("安全", "攻击", "封号", "jailbreak", "risk", "ban")):
        return "security"
    if any(
        term in text
        for term in ("benchmark", "实测", "榜", "超过", "wins", "beats", "任务完成率", "completion")
    ):
        return "benchmark"
    if any(term in text for term in ("发布", "上线", "release", "launch", "开源")):
        return "release"
    if any(term in text for term in ("企业", "adoption", "用户", "客户")):
        return "adoption"
    if any(term in text for term in ("failure", "失控", "事故")):
        return "safety"
    return "demo"


def risk_for(claim_type: str, title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if claim_type in {"security", "safety"}:
        return "high"
    if claim_type == "medical" or any(
        term in text for term in ("medical", "癌症", "诊断", "clinical", "牙科", "医生")
    ):
        return "high"
    if claim_type in {"benchmark", "cost", "adoption"}:
        return "medium"
    return "low"


def subject_for(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    for term in (
        "Anthropic",
        "OpenAI",
        "Codex",
        "Claude",
        "Patronus AI",
        "GPTZero",
        "Grammarly",
        "Adobe",
        "Topaz Labs",
        "Engram",
        "Karpathy",
        "DentFound",
        "Momenta",
        "Waymo",
        "Tesla",
        "NVIDIA",
        "Cosmos",
    ):
        match = term_match(text, term)
        if match:
            return match.group(0)
    for term in core.MODEL_TERMS:
        match = model_term_match(text, term)
        if match:
            return match.group(0)
    cleaned = re.sub(r"\s+", " ", title).strip()
    return f"Model claim: {cleaned[:60]}"


def term_match(text: str, term: str) -> re.Match[str] | None:
    return re.search(
        rf"(?<![A-Za-z0-9_.-]){re.escape(term)}(?![A-Za-z0-9_.-])",
        text,
        flags=re.IGNORECASE,
    )


def model_term_match(text: str, term: str) -> re.Match[str] | None:
    return re.search(
        rf"(?<![A-Za-z0-9_.-]){re.escape(term)}[A-Za-z0-9_.-]*",
        text,
        flags=re.IGNORECASE,
    )


def claim_text(title: str, summary: str) -> str:
    if summary:
        return f"{title}\n\n{summary}"
    return title


def physical_system_for(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(term in text for term in ("robotaxi", "waymo", "momenta", "特斯拉", "tesla")):
        return "robotaxi"
    if any(term in text for term in ("自动驾驶", "autonomous")):
        return "autonomous-driving"
    if any(term in text for term in ("cosmos", "world model", "世界模型")):
        return "world-model"
    if any(
        term in text
        for term in (
            "halos",
            "robot safety",
            "safety system",
            "robot",
            "机器人",
            "物理ai",
            "physical ai",
        )
    ):
        return "robotics"
    return ""


def evidence_status_for(title: str, summary: str) -> str:
    if physical_system_for(title, summary):
        return "source-only"
    if claim_type_for(title, summary) == "medical":
        return "source-only"
    return ""


def safety_gate_for(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if not physical_system_for(title, summary):
        if claim_type_for(title, summary) == "medical":
            return "clinical-validation-needed"
        return ""
    if any(term in text for term in ("halos", "安全系统", "安全架构", "safety system")):
        return "safety-eval-needed"
    if any(term in text for term in ("营收", "revenue", "许可", "license")):
        return "financial-source-needed"
    if any(term in text for term in ("上路", "robotaxi", "自动驾驶", "waymo", "tesla", "momenta")):
        return "regulatory-proof-needed"
    return "safety-eval-needed"


def deployment_stage_for(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if not physical_system_for(title, summary):
        return ""
    if any(term in text for term in ("上线", "运营", "上路", "production")):
        return "production-claimed"
    if any(term in text for term in ("试点", "pilot")):
        return "pilot"
    if any(term in text for term in ("发布", "release", "launch")):
        return "demo"
    return "unknown"


def first_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
