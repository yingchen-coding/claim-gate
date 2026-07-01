"""Tests for the shared ledger-store primitives — the plumbing every domain sits on."""
import json

import pytest

from claim_gate.engine import read_json, write_json


def test_write_json_round_trips(tmp_path):
    p = tmp_path / "ledger.json"
    write_json(p, {"claims": [{"id": "a"}], "n": 1})
    assert read_json(p, {}) == {"claims": [{"id": "a"}], "n": 1}


def test_write_json_is_atomic_and_leaves_no_temp_files(tmp_path):
    p = tmp_path / "ledger.json"
    write_json(p, {"claims": ["x"]})
    # an interrupted write must never leave a half-file or stray temp beside the ledger
    leftovers = [f.name for f in tmp_path.iterdir() if ".tmp." in f.name]
    assert leftovers == []
    assert json.loads(p.read_text())["claims"] == ["x"]


def test_write_json_creates_parent_dirs(tmp_path):
    p = tmp_path / "nested" / "deep" / "ledger.json"
    write_json(p, {"ok": True})
    assert read_json(p, {}) == {"ok": True}


def test_read_json_missing_returns_default(tmp_path):
    assert read_json(tmp_path / "nope.json", {"default": 1}) == {"default": 1}


def test_read_json_corrupt_ledger_raises_clear_error_not_traceback(tmp_path):
    # A ledger is the record of truth: on corruption we must refuse loudly (so it can be restored),
    # never silently reset and lose every claim.
    p = tmp_path / "ledger.json"
    p.write_text("{ half-written garbage", encoding="utf-8")  # e.g. a prior crash mid-write
    with pytest.raises(ValueError, match="not valid JSON"):
        read_json(p, {})


def test_read_json_rejects_non_object(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON object"):
        read_json(p, {})
