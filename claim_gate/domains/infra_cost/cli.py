from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import __version__
from .core import (
    VALID_COST_DRIVERS,
    VALID_IMPACT,
    VALID_SIGNAL_TYPES,
    VALID_SOURCE_TYPES,
    VALID_STATUS,
    import_signals,
    load,
    make_signal,
    render,
    render_markdown,
    save,
    upsert,
    validate_state,
)

STATE_ENV = "INFRA_COST_RADAR_STATE"
DEFAULT_STATE = Path(".infra-cost-radar/signals.json")


def state_path() -> Path:
    configured = os.environ.get(STATE_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_STATE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track public AI infrastructure cost signals.")
    parser.add_argument(
        "--state", type=Path, help=f"state file; defaults to ${STATE_ENV} or {DEFAULT_STATE}"
    )
    parser.add_argument("--version", action="version", version=f"ai-infra-cost-radar {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add or update a public AI infra cost signal")
    add.add_argument("--title", required=True)
    add.add_argument("--source-type", required=True, choices=sorted(VALID_SOURCE_TYPES))
    add.add_argument("--source-url", required=True)
    add.add_argument("--signal-type", required=True, choices=sorted(VALID_SIGNAL_TYPES))
    add.add_argument("--cost-driver", required=True, choices=sorted(VALID_COST_DRIVERS))
    add.add_argument("--summary", required=True)
    add.add_argument("--observed-on", default="")
    add.add_argument("--metric", default="")
    add.add_argument("--evidence", default="")
    add.add_argument("--decision-signal", default="")
    add.add_argument("--impact", default="medium", choices=sorted(VALID_IMPACT))
    add.add_argument("--status", default="needs-review", choices=sorted(VALID_STATUS))

    importer = sub.add_parser("import", help="import signals from JSON")
    importer.add_argument("path", type=Path)

    sub.add_parser("list", help="list signals")

    validate = sub.add_parser("validate", help="validate state")
    validate.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="export state")
    export.add_argument("--format", choices=["json", "markdown"], default="markdown")
    export.add_argument("--output", type=Path)
    export.add_argument("--only-validated", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = args.state or state_path()

    if args.command == "add":
        data = load(path)
        signal = make_signal(
            title=args.title,
            source_type=args.source_type,
            source_url=args.source_url,
            signal_type=args.signal_type,
            cost_driver=args.cost_driver,
            summary=args.summary,
            observed_on=args.observed_on,
            metric=args.metric,
            evidence=args.evidence,
            decision_signal=args.decision_signal,
            impact=args.impact,
            status=args.status,
        )
        record = upsert(data, signal)
        save(data, path)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    if args.command == "import":
        data = load(path)
        imported = json.loads(args.path.read_text(encoding="utf-8"))
        if not isinstance(imported, dict):
            raise ValueError(f"expected JSON object: {args.path}")
        count = import_signals(data, imported)
        save(data, path)
        print(json.dumps({"imported": count}, indent=2))
        return 0
    if args.command == "list":
        print(render(load(path)))
        return 0
    if args.command == "validate":
        findings = validate_state(load(path))
        if args.json:
            print(
                json.dumps(
                    [finding.to_dict() for finding in findings], ensure_ascii=False, indent=2
                )
            )
        else:
            print("\n".join(f"{f.code} {f.signal_id}: {f.message}" for f in findings) or "OK")
        return 0 if not findings else 2
    if args.command == "export":
        data = load(path)
        if args.only_validated:
            data = {
                "version": data.get("version", 1),
                "signals": [
                    raw
                    for raw in data.get("signals", [])
                    if isinstance(raw, dict) and raw.get("status") == "validated"
                ],
            }
        output = (
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(data)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    raise AssertionError(args.command)

