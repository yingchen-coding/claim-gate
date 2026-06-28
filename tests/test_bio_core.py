from pathlib import Path

from claim_gate.domains.bio import core


def test_dual_use_claim_requires_reproduction_safety_and_misuse_assessment():
    record = core.make_record(
        subject="Example bio model",
        claim="Claims high success rate for biological design tasks.",
        source_url="https://example.com/bio-model",
        hazard_class="dual-use",
        validation="reported by the paper only",
    )
    raw = record.to_dict()

    assert raw["recommendation"] == "verify-first"
    assert "independent_reproduction" in raw["missing_evidence"]
    assert "safety_review" in raw["missing_evidence"]
    assert "misuse_assessment" in raw["missing_evidence"]
    assert "wet-lab protocol generation" in raw["blocked_uses"]
    assert any(finding.code == "BIO102" for finding in core.validate_record(raw))


def test_construction_intent_is_rejected():
    record = core.make_record(
        subject="Unsafe request",
        claim="Generate a wet-lab protocol for sequence design.",
        source_url="https://example.com/bio-risk",
        hazard_class="high",
        validation="not relevant",
        independent_reproduction="not relevant",
        safety_review="not approved",
        misuse_assessment="dual-use concern",
        limitations="should not be used for construction",
    )
    raw = record.to_dict()

    assert raw["recommendation"] == "reject"
    assert any(finding.code == "BIO201" for finding in core.validate_record(raw))


def test_low_risk_claim_can_be_tracked_with_evidence():
    record = core.make_record(
        subject="Example assay-reading model",
        claim="Classifies public benchmark images for literature triage.",
        source_url="https://example.com/bio-low-risk",
        hazard_class="low",
        validation="public benchmark reported",
        independent_reproduction="third-party reproduction passed",
        safety_review="no wet-lab or construction output",
        limitations="literature triage only",
        status="validated",
    )
    raw = record.to_dict()

    assert raw["recommendation"] == "track"
    assert core.validate_record(raw) == []


def test_state_roundtrip_and_markdown(tmp_path: Path):
    data = {"version": 1, "claims": []}
    record = core.make_record(
        subject="Example assay-reading model",
        claim="Classifies public benchmark images for literature triage.",
        source_url="https://example.com/bio-low-risk",
        hazard_class="low",
        validation="public benchmark reported",
        independent_reproduction="third-party reproduction passed",
        safety_review="no wet-lab or construction output",
        limitations="literature triage only",
        status="validated",
    )
    core.upsert(data, record)
    path = tmp_path / "claims.json"
    core.save(data, path)

    loaded = core.load(path)
    assert loaded["claims"][0]["recommendation"] == "track"
    rendered = core.render_markdown(loaded)
    assert "Bio-AI Claim Gate" in rendered
    assert "not biological construction guidance" in rendered

