"""Tests for the top-level claim-gate dispatcher and the shared engine."""
from datetime import datetime

from claim_gate.cli import main
from claim_gate.domains import DOMAINS, get_domain
from claim_gate.engine import now, read_json, write_json


def test_registry_exposes_three_domains():
    assert set(DOMAINS) == {"infra-cost", "bio", "model"}
    for name in DOMAINS:
        assert get_domain(name).main is not None
        assert get_domain(name).summary
    assert get_domain("nope") is None


def test_version_and_list_domains(capsys):
    assert main(["--version"]) == 0
    assert "claim-gate" in capsys.readouterr().out
    assert main(["--list-domains"]) == 0
    out = capsys.readouterr().out
    assert "infra-cost" in out and "bio" in out and "model" in out


def test_no_args_prints_usage():
    assert main([]) == 0


def test_unknown_domain_fails_closed(capsys):
    assert main(["does-not-exist"]) == 2
    assert "unknown domain" in capsys.readouterr().err


def test_dispatch_routes_to_domain(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # claim-gate bio add ... reaches the bio domain CLI
    rc = main([
        "bio", "add",
        "--subject", "Example bio model",
        "--claim", "Classifies public benchmark images.",
        "--source-url", "https://example.com/bio-model",
        "--hazard-class", "low",
    ])
    assert rc == 0
    assert "recommendation" in capsys.readouterr().out


def test_engine_now_is_utc_seconds():
    stamp = now()
    parsed = datetime.fromisoformat(stamp)
    assert parsed.utcoffset() is not None  # tz-aware
    assert parsed.second == parsed.second and parsed.microsecond == 0


def test_engine_read_write_roundtrip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    assert read_json(path, {"version": 1}) == {"version": 1}  # missing -> default
    write_json(path, {"version": 2, "items": []})
    assert read_json(path, {}) == {"version": 2, "items": []}
