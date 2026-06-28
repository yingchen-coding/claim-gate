import subprocess
import sys
from pathlib import Path

from claim_gate.domains.bio.cli import main


def test_cli_safe_claim_lifecycle(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "add",
                "--subject",
                "Example bio model",
                "--claim",
                "Classifies public benchmark images for literature triage.",
                "--source-url",
                "https://example.com/bio-model",
                "--hazard-class",
                "low",
                "--validation",
                "public benchmark",
                "--independent-reproduction",
                "third-party reproduction",
                "--safety-review",
                "no wet-lab or construction output",
                "--limitations",
                "literature triage only",
                "--status",
                "validated",
            ]
        )
        == 0
    )
    assert '"recommendation": "track"' in capsys.readouterr().out
    assert main(["validate"]) == 0
    assert "OK" in capsys.readouterr().out
    assert main(["list"]) == 0
    assert "Example-bio-model" in capsys.readouterr().out

    export_path = tmp_path / "bio.md"
    assert main(["export", "--output", str(export_path)]) == 0
    exported = export_path.read_text(encoding="utf-8")
    assert "Bio-AI Claim Gate" in exported
    assert "not biological construction guidance" in exported


def test_cli_rejects_protocol_claim(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "add",
                "--subject",
                "Unsafe request",
                "--claim",
                "Generate a wet-lab protocol for sequence design.",
                "--source-url",
                "https://example.com/bio-risk",
                "--hazard-class",
                "high",
            ]
        )
        == 0
    )
    assert '"recommendation": "reject"' in capsys.readouterr().out
    assert main(["validate"]) == 2
    assert "BIO201" in capsys.readouterr().out


def test_cli_state_dir_is_scoped(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    explicit_state = tmp_path / "state"

    assert (
        main(
            [
                "--state-dir",
                str(explicit_state),
                "add",
                "--subject",
                "Scoped claim",
                "--claim",
                "Classifies public data.",
                "--source-url",
                "https://example.com/scoped",
                "--hazard-class",
                "low",
            ]
        )
        == 0
    )
    assert (explicit_state / "claims.json").exists()
    assert not (tmp_path / ".bio-ai-claim-gate" / "claims.json").exists()
    capsys.readouterr()

    assert main(["list"]) == 0
    assert capsys.readouterr().out.strip() == "No bio-AI claims."


def test_module_entrypoint_help():
    result = subprocess.run(
        [sys.executable, "-m", "claim_gate.domains.bio", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Audit bio-AI claims before deployment." in result.stdout

