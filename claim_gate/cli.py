"""Top-level claim-gate CLI: dispatch to a domain ledger.

Usage:
    claim-gate <domain> <command> [args...]
    claim-gate --list-domains
    claim-gate --version

Everything after the domain name is handed verbatim to that domain's own CLI, so each domain keeps
its full command set (add / list / validate / export / ...).
"""
from __future__ import annotations

import sys

from . import __version__
from .domains import DOMAINS, get_domain


def _usage() -> str:
    lines = [
        "usage: claim-gate <domain> <command> [args...]",
        "",
        "domains:",
    ]
    for name, domain in DOMAINS.items():
        lines.append(f"  {name:<12} {domain.summary}")
    lines += [
        "",
        "run `claim-gate <domain> --help` for a domain's commands",
        "options:",
        "  --list-domains   list available domains",
        "  --version        show version",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in {"-h", "--help"}:
        print(_usage())
        return 0
    if argv[0] == "--version":
        print(f"claim-gate {__version__}")
        return 0
    if argv[0] == "--list-domains":
        for name, domain in DOMAINS.items():
            print(f"{name}: {domain.summary}")
        return 0

    domain = get_domain(argv[0])
    if domain is None:
        valid = ", ".join(DOMAINS)
        print(f"unknown domain {argv[0]!r}; expected one of: {valid}", file=sys.stderr)
        print("", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    return domain.main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
