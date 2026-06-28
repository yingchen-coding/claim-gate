from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit bio-AI claims before deployment.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help=f"state directory; defaults to .bio-ai-claim-gate or ${core.STATE_DIR_ENV}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="record a bio-AI claim gate")
    add.add_argument("--subject", required=True)
    add.add_argument("--claim", required=True)
    add.add_argument("--source-url", required=True)
    add.add_argument("--hazard-class", default="unknown", choices=sorted(core.VALID_HAZARD_CLASSES))
    add.add_argument("--validation", default="")
    add.add_argument("--independent-reproduction", default="")
    add.add_argument("--safety-review", default="")
    add.add_argument("--misuse-assessment", default="")
    add.add_argument("--limitations", default="")
    add.add_argument("--status", default="needs-review", choices=sorted(core.VALID_STATUS))

    sub.add_parser("list", help="list bio-AI claims")

    validate = sub.add_parser("validate", help="validate bio-AI claim gates")
    validate.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="export bio-AI claim gates")
    export.add_argument("--format", choices=["json", "markdown"], default="markdown")
    export.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    previous_state_dir = os.environ.get(core.STATE_DIR_ENV)
    if args.state_dir:
        os.environ[core.STATE_DIR_ENV] = str(args.state_dir)
    try:
        return _run(args)
    finally:
        if args.state_dir:
            if previous_state_dir is None:
                os.environ.pop(core.STATE_DIR_ENV, None)
            else:
                os.environ[core.STATE_DIR_ENV] = previous_state_dir


def _run(args: argparse.Namespace) -> int:
    if args.command == "add":
        data = core.load()
        record = core.make_record(
            subject=args.subject,
            claim=args.claim,
            source_url=args.source_url,
            hazard_class=args.hazard_class,
            validation=args.validation,
            independent_reproduction=args.independent_reproduction,
            safety_review=args.safety_review,
            misuse_assessment=args.misuse_assessment,
            limitations=args.limitations,
            status=args.status,
        )
        stored = core.upsert(data, record)
        core.save(data)
        print(json.dumps(stored, ensure_ascii=False, indent=2))
        return 0
    if args.command == "list":
        print(core.render(core.load()))
        return 0
    if args.command == "validate":
        findings = core.validate_state(core.load())
        if args.json:
            print(json.dumps([finding.to_dict() for finding in findings], indent=2))
        else:
            print("\n".join(f"{f.code} {f.record_id}: {f.message}" for f in findings) or "OK")
        return 0 if not findings else 2
    if args.command == "export":
        data = core.load()
        output = (
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else core.render_markdown(data)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    raise AssertionError(args.command)

