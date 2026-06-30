from __future__ import annotations

import json
from pathlib import Path

from claim_gate.domains.model import core, feed
from claim_gate.domains.model.cli import main


def test_cost_claim_requires_cost_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    record = core.make_record(
        subject="ExampleModel",
        claim_type="cost",
        claim="Vendor says long-context use is cheaper.",
        source_url="https://example.com/cost",
    )

    assert record.recommendation == "verify-first"
    assert record.missing_evidence == ["cost_evidence"]


def test_missing_source_rejects_even_when_claim_has_text():
    record = core.make_record(
        subject="ExampleModel",
        claim_type="demo",
        claim="Someone posted a model demo.",
        source_url="",
    )

    assert record.recommendation == "reject"


def test_validated_claim_exports_as_validated(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = core.load()
    record = core.make_record(
        subject="ExampleModel",
        claim_type="benchmark",
        claim="Independent benchmark result reproduced.",
        source_url="https://example.com/benchmark",
        benchmark="public benchmark suite",
        reproduction_evidence="reproduced locally",
        status="validated",
    )

    stored = core.upsert(data, record)
    core.save(data)

    assert stored["recommendation"] == "validated"
    assert core.validate(core.load()) == []
    exported = core.export_markdown(core.load(), only_validated=True)
    assert "ExampleModel" in exported
    assert "validated" in exported


def test_feed_imports_product_map_idempotently(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    product_map = tmp_path / "product-map.json"
    product_map.write_text(
        json.dumps(
            {
                "product_ideas": {
                    "model_claim_diligence_feed": {
                        "items": [
                            {
                                "title": "DeepSeek token price beats competitors",
                                "summary": "Needs exact source verification.",
                                "source_url": "https://example.com/deepseek-cost",
                            },
                            {
                                "title": "Fable model security incident blocks medical answer",
                                "summary": "Article claims refusal behavior changed.",
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    first = feed.import_claim_feed(product_map)
    second = feed.import_claim_feed(product_map)

    assert first["items"] == 2
    assert first["imported"] == 2
    assert second["updated"] == 2
    claims = core.load()["claims"]
    by_subject = {claim["subject"]: claim for claim in claims}
    assert by_subject["DeepSeek"]["claim_type"] == "cost"
    assert by_subject["DeepSeek"]["recommendation"] == "verify-first"
    assert by_subject["Fable"]["recommendation"] == "reject"
    assert by_subject["Fable"]["risk"] == "high"


def test_feed_imports_generic_items(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "claims.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "headline": "Gemma wins public benchmark",
                        "link": "https://example.com/gemma-benchmark",
                        "notes": "Needs independent reproduction.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "Gemma"
    assert claim["claim_type"] == "benchmark"
    assert "benchmark or reproduction_evidence" in claim["missing_evidence"]


def test_subject_fallback_prefers_concrete_latin_product_token():
    subject = feed.subject_for(
        "ABCoder+MCP+Trae Agent的实战应用，揭秘AI Agent如何提升开发效率！",
        "",
    )

    assert subject == "ABCoder"


def test_subject_fallback_uses_first_clause_for_chinese_headline_without_brand():
    subject = feed.subject_for(
        "漏洞挖掘从数月缩至数小时，网络安全治理走到十字路口",
        "",
    )

    assert subject == "漏洞挖掘从数月缩至数小时"


def test_physical_ai_claim_requires_safety_and_deployment_evidence():
    record = core.make_record(
        subject="Momenta",
        claim_type="deployment",
        claim="Article claims robotaxi deployment is accelerating.",
        source_url="https://example.com/momenta-robotaxi",
        physical_system="robotaxi",
        evidence_status="source-only",
        safety_gate="regulatory-proof-needed",
        deployment_stage="production-claimed",
    )

    assert record.risk == "high"
    assert record.recommendation == "verify-first"
    assert "safety_evidence" in record.missing_evidence
    assert "reproduction_evidence" in record.missing_evidence


def test_medical_ai_claim_requires_clinical_evidence():
    record = core.make_record(
        subject="DentFound",
        claim_type="medical",
        claim="Article claims a vision-language model supports dental diagnosis.",
        source_url="https://example.com/dentfound",
        safety_gate="clinical-validation-needed",
        evidence_status="source-only",
    )

    assert record.risk == "high"
    assert record.recommendation == "verify-first"
    assert "safety_evidence" in record.missing_evidence
    assert "clinical validation or reproduction_evidence" in record.missing_evidence
    assert "clinical metric or benchmark" in record.missing_evidence


def test_feed_marks_medical_dental_items_as_clinical_gate(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "medical.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "DentFound dental AI diagnosis model reported in Nature",
                        "source_url": "https://example.com/dentfound",
                        "summary": "Needs clinical validation review before use.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "DentFound"
    assert claim["claim_type"] == "medical"
    assert claim["risk"] == "high"
    assert claim["safety_gate"] == "clinical-validation-needed"
    assert claim["recommendation"] == "verify-first"


def test_physical_ai_claim_exports_event_graph_csv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = core.load()
    record = core.make_record(
        subject="Cosmos",
        claim_type="release",
        claim="Public release claim with checked evidence.",
        source_url="https://example.com/cosmos",
        physical_system="world-model",
        evidence_status="validated",
        safety_gate="none",
        deployment_stage="demo",
        safety_evidence="public safety evaluation notes",
        reproduction_evidence="local article and release notes checked",
        metric="release date",
        status="validated",
    )
    stored = core.upsert(data, record)

    assert stored["recommendation"] == "validated"
    exported = core.export_event_graph_csv(data, only_validated=True)
    assert "claim:" in exported
    assert "system:world-model" in exported
    assert "stage:demo" in exported


def test_feed_marks_physical_ai_items_as_gated(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "physical.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "Momenta robotaxi license revenue grows",
                        "source_url": "https://example.com/momenta",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "Momenta"
    assert claim["physical_system"] == "robotaxi"
    assert claim["safety_gate"] == "financial-source-needed"


def test_feed_marks_robot_safety_stack_as_high_risk(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "halos.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "NVIDIA Halos robot safety system for physical AI",
                        "source_url": "https://example.com/halos",
                        "summary": "Article claims a full-stack robot safety architecture.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "NVIDIA"
    assert claim["claim_type"] == "safety"
    assert claim["physical_system"] == "robotics"
    assert claim["risk"] == "high"
    assert claim["safety_gate"] == "safety-eval-needed"
    assert claim["recommendation"] == "verify-first"


def test_feed_marks_mythos_vulnerability_claim_as_security(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "security.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "GLM-5.2 漏洞挖掘能力达到 Mythos 水平",
                        "source_url": "https://example.com/glm-mythos",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "GLM-5.2"
    assert claim["claim_type"] == "security"
    assert claim["risk"] == "high"
    assert "safety_evidence" in claim["missing_evidence"]


def test_feed_marks_ai_memory_as_architecture_claim(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "memory.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "Karpathy 投了一家 AI 记忆公司，撞名 DeepSeek Engram 记忆架构",
                        "source_url": "https://example.com/engram",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "Engram"
    assert claim["claim_type"] == "architecture"
    assert claim["recommendation"] == "track"


def test_example_sina_feed_imports_public_safe_claims(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = Path(__file__).parents[1] / "examples" / "sina-2026-06-29-claim-feed.json"

    result = feed.import_claim_feed(source)

    assert result["items"] == 7
    assert result["imported"] == 7
    claims = core.load()["claims"]
    by_subject = {claim["subject"]: claim for claim in claims}
    assert by_subject["GLM-5.2"]["claim_type"] == "security"
    assert by_subject["Momenta"]["physical_system"] == "robotaxi"
    assert by_subject["GPTZero"]["claim_type"] == "security"
    assert by_subject["GPTZero"]["recommendation"] == "verify-first"
    assert by_subject["Adobe"]["claim_type"] == "release"
    assert by_subject["DeepTech"]["claim_type"] == "medical"
    assert by_subject["DeepTech"]["risk"] == "high"


def test_feed_marks_world_model_claim_as_physical_ai(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "world-model.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "Cosmos world model helps AI understand the physical world",
                        "source_url": "https://example.com/world-model",
                        "summary": "Demo article needs benchmark and safety evidence.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = feed.import_claim_feed(source)

    assert result["imported"] == 1
    claim = core.load()["claims"][0]
    assert claim["subject"] == "Cosmos"
    assert claim["physical_system"] == "world-model"
    assert claim["safety_gate"] == "safety-eval-needed"
    assert claim["recommendation"] == "verify-first"


def test_cli_round_trip(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "add",
                "--subject",
                "ExampleModel",
                "--claim-type",
                "cost",
                "--claim",
                "Cheaper for coding agents.",
                "--source-url",
                "https://example.com/cost",
            ]
        )
        == 0
    )
    assert main(["list"]) == 0
    assert "ExampleModel" in capsys.readouterr().out
    assert main(["validate"]) == 0
    assert main(["export", "--format", "json", "--only-validated"]) == 0
    assert '"claims": []' in capsys.readouterr().out


def test_cli_adds_physical_ai_claim_and_exports_csv(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "add",
                "--subject",
                "Waymo",
                "--claim-type",
                "deployment",
                "--claim",
                "Public report claims wider robotaxi deployment.",
                "--source-url",
                "https://example.com/waymo",
                "--physical-system",
                "robotaxi",
                "--evidence-status",
                "reported-metric",
                "--safety-gate",
                "regulatory-proof-needed",
                "--deployment-stage",
                "pilot",
                "--safety-evidence",
                "public regulator page checked",
                "--reproduction-evidence",
                "deployment page checked",
                "--metric",
                "coverage area",
            ]
        )
        == 0
    )
    assert main(["export", "--format", "event-graph-csv"]) == 0
    output = capsys.readouterr().out
    assert "safety_gate:regulatory-proof-needed" in output
    assert "stage:pilot" in output
