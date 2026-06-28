from claim_gate.domains.infra_cost.core import (
    import_signals,
    make_signal,
    recommendation,
    render,
    score_signal,
    validate_signal,
    validate_state,
)


def test_actionable_gpu_waste_signal_scores_high():
    signal = make_signal(
        title="GPU utilization waste becomes a major AI cost driver",
        source_type="public_news",
        source_url="https://example.com/gpu-waste",
        signal_type="utilization-waste",
        cost_driver="gpu",
        summary="Public article claims many deployed accelerators sit underutilized.",
        metric="utilization below target",
        evidence="article cites utilization measurements and deployment constraints",
        decision_signal="prioritize utilization telemetry before buying more capacity",
        impact="high",
        status="actionable",
    ).to_dict()

    assert score_signal(signal) == 100
    assert recommendation(signal) == "act"
    assert validate_signal(signal) == []


def test_private_or_unsourced_signal_is_blocked():
    signal = make_signal(
        title="Internal note says GPU supply is worse than public filings",
        source_type="other",
        source_url="https://example.com/item",
        signal_type="gpu-supply",
        cost_driver="gpu",
        summary="Private chat says an internal supply issue is coming.",
        decision_signal="delay purchase",
        impact="high",
        status="actionable",
    ).to_dict()

    findings = validate_signal(signal)
    assert any(finding.code == "IC102" for finding in findings)
    assert any(finding.code == "IC103" for finding in findings)
    assert recommendation(signal) == "verify-first"


def test_validated_signal_requires_metric():
    signal = make_signal(
        title="Liquid cooling reduces power cost",
        source_type="paper",
        source_url="https://example.com/cooling-paper",
        signal_type="cooling-constraint",
        cost_driver="cooling",
        summary="Public paper evaluates cooling efficiency.",
        evidence="paper includes experiment setup",
        decision_signal="model cooling cost before dense rack purchases",
        impact="high",
        status="validated",
    ).to_dict()

    assert any(finding.code == "IC105" for finding in validate_signal(signal))
    signal["metric"] = "cooling efficiency measured on public benchmark"
    assert validate_signal(signal) == []
    assert recommendation(signal) == "feed-downstream"


def test_import_dedupes_by_generated_id():
    data = {"version": 1, "signals": []}
    payload = {
        "signals": [
            {
                "title": "AI cloud margin pressure",
                "source_type": "public_news",
                "source_url": "https://example.com/cloud-margin",
                "signal_type": "cloud-margin-risk",
                "cost_driver": "cloud",
                "summary": "Public article describes AI cloud financial mismatch.",
            },
            {
                "title": "AI cloud margin pressure",
                "source_type": "public_news",
                "source_url": "https://example.com/cloud-margin",
                "signal_type": "cloud-margin-risk",
                "cost_driver": "cloud",
                "summary": "Updated summary.",
                "evidence": "same public article",
            },
        ]
    }

    assert import_signals(data, payload) == 1
    assert len(data["signals"]) == 1
    assert "same public article" in data["signals"][0]["evidence"]
    assert validate_state(data) == []


def test_render_orders_by_score():
    low = make_signal(
        title="Low signal",
        source_type="public_news",
        source_url="https://example.com/low",
        signal_type="price-shift",
        cost_driver="other",
        summary="Low signal.",
        impact="low",
    ).to_dict()
    high = make_signal(
        title="High signal",
        source_type="public_news",
        source_url="https://example.com/high",
        signal_type="energy-constraint",
        cost_driver="energy",
        summary="High signal.",
        evidence="public evidence",
        decision_signal="watch power availability",
        impact="high",
    ).to_dict()

    output = render({"version": 1, "signals": [low, high]})
    assert output.index("High signal") < output.index("Low signal")

