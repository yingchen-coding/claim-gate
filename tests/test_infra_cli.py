from pathlib import Path

from claim_gate.domains.infra_cost.cli import main


def test_cli_add_validate_export(tmp_path: Path, capsys):
    state = tmp_path / "signals.json"
    out = tmp_path / "signals.md"

    assert (
        main(
            [
                "--state",
                str(state),
                "add",
                "--title",
                "GPU utilization waste becomes a major AI cost driver",
                "--source-type",
                "public_news",
                "--source-url",
                "https://example.com/gpu-waste",
                "--signal-type",
                "utilization-waste",
                "--cost-driver",
                "gpu",
                "--summary",
                "Public article claims many deployed accelerators sit underutilized.",
                "--metric",
                "utilization below target",
                "--evidence",
                "article cites utilization measurements",
                "--decision-signal",
                "prioritize utilization telemetry",
                "--impact",
                "high",
                "--status",
                "actionable",
            ]
        )
        == 0
    )
    assert main(["--state", str(state), "validate"]) == 0
    assert "OK" in capsys.readouterr().out
    assert main(["--state", str(state), "list"]) == 0
    assert "recommendation=act" in capsys.readouterr().out
    assert main(["--state", str(state), "export", "--output", str(out)]) == 0
    assert "AI Infra Cost Radar" in out.read_text(encoding="utf-8")


def test_cli_validate_returns_nonzero_for_missing_public_source(tmp_path: Path):
    state = tmp_path / "signals.json"
    assert (
        main(
            [
                "--state",
                str(state),
                "add",
                "--title",
                "Unsourced infra claim",
                "--source-type",
                "other",
                "--source-url",
                "local-note",
                "--signal-type",
                "gpu-supply",
                "--cost-driver",
                "gpu",
                "--summary",
                "A local note claims supply changed.",
            ]
        )
        == 0
    )
    assert main(["--state", str(state), "validate"]) == 2


def test_cli_import_and_validated_export(tmp_path: Path, capsys):
    state = tmp_path / "signals.json"
    feed = tmp_path / "feed.json"
    feed.write_text(
        """
        {
          "signals": [
            {
              "title": "Liquid cooling changes rack economics",
              "source_type": "paper",
              "source_url": "https://example.com/liquid-cooling",
              "signal_type": "cooling-constraint",
              "cost_driver": "cooling",
              "summary": "Public paper evaluates cooling efficiency.",
              "metric": "cooling efficiency benchmark",
              "evidence": "paper includes experiment setup",
              "decision_signal": "model cooling cost before dense rack purchases",
              "impact": "high",
              "status": "validated"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    assert main(["--state", str(state), "import", str(feed)]) == 0
    assert '"imported": 1' in capsys.readouterr().out
    assert main(["--state", str(state), "export", "--format", "json", "--only-validated"]) == 0
    output = capsys.readouterr().out
    assert "Liquid cooling" in output
    assert "validated" in output

