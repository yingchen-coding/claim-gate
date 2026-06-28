from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__, core, feed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-claim-diligence")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add or update one model claim")
    add.add_argument("--subject", required=True)
    add.add_argument("--claim-type", required=True, choices=sorted(core.VALID_CLAIM_TYPES))
    add.add_argument("--claim", required=True)
    add.add_argument("--source-url", required=True)
    add.add_argument("--benchmark", default="")
    add.add_argument("--cost-evidence", default="")
    add.add_argument("--safety-evidence", default="")
    add.add_argument("--reproduction-evidence", default="")
    add.add_argument("--adoption-evidence", default="")
    add.add_argument("--physical-system", default="", choices=sorted(core.VALID_PHYSICAL_SYSTEMS))
    add.add_argument("--evidence-status", default="", choices=sorted(core.VALID_EVIDENCE_STATUS))
    add.add_argument("--safety-gate", default="", choices=sorted(core.VALID_SAFETY_GATES))
    add.add_argument("--deployment-stage", default="", choices=sorted(core.VALID_DEPLOYMENT_STAGES))
    add.add_argument("--geography", default="")
    add.add_argument("--metric", default="")
    add.add_argument("--risk", default="", choices=["", *sorted(core.VALID_RISKS)])
    add.add_argument("--status", default="needs-review", choices=sorted(core.VALID_STATUS))

    importer = sub.add_parser("import-feed", help="import model claims from news or product maps")
    importer.add_argument("path", type=Path)
    importer.add_argument("--feed", default="model_claim_diligence_feed")

    sub.add_parser("list", help="list claim records")
    sub.add_parser("validate", help="validate the claim ledger")

    export = sub.add_parser("export", help="export claim records")
    export.add_argument(
        "--format",
        choices=["json", "markdown", "event-graph-csv"],
        default="markdown",
    )
    export.add_argument("--output", type=Path)
    export.add_argument("--only-validated", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "add":
        data = core.load()
        record = core.make_record(
            subject=args.subject,
            claim_type=args.claim_type,
            claim=args.claim,
            source_url=args.source_url,
            benchmark=args.benchmark,
            cost_evidence=args.cost_evidence,
            safety_evidence=args.safety_evidence,
            reproduction_evidence=args.reproduction_evidence,
            adoption_evidence=args.adoption_evidence,
            physical_system=args.physical_system,
            evidence_status=args.evidence_status,
            safety_gate=args.safety_gate,
            deployment_stage=args.deployment_stage,
            geography=args.geography,
            metric=args.metric,
            risk=args.risk,
            status=args.status,
        )
        stored = core.upsert(data, record)
        core.save(data)
        print(json.dumps(stored, ensure_ascii=False, indent=2))
        return 0

    if args.command == "import-feed":
        print(json.dumps(feed.import_claim_feed(args.path, feed=args.feed), indent=2))
        return 0

    if args.command == "list":
        data = core.load()
        rows = data.get("claims", [])
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        findings = [finding.to_dict() for finding in core.validate(core.load())]
        print(json.dumps({"findings": findings}, indent=2))
        return 0 if not findings else 2

    if args.command == "export":
        data = core.load()
        if args.only_validated:
            claims = [
                raw
                for raw in data.get("claims", [])
                if isinstance(raw, dict) and raw.get("recommendation") == "validated"
            ]
            data = {"version": data.get("version", 1), "claims": claims}
        if args.format == "json":
            output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        elif args.format == "event-graph-csv":
            output = core.export_event_graph_csv(data, only_validated=False)
        else:
            output = core.export_markdown(data, only_validated=False)
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")
