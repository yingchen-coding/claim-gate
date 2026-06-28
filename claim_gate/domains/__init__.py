"""Domain registry for claim-gate.

Each domain is a self-contained evidence ledger (its own record schema, vocabulary, validation
rules, scoring, and CLI). They share one package, one CLI harness, and one packaging/CI setup.
A domain is registered here by exposing a ``main(argv)`` entry point and a one-line summary.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .bio import cli as bio_cli
from .infra_cost import cli as infra_cost_cli
from .model import cli as model_cli


@dataclass(frozen=True)
class Domain:
    name: str
    summary: str
    main: Callable[[list[str] | None], int]


DOMAINS: dict[str, Domain] = {
    "infra-cost": Domain(
        "infra-cost",
        "Track public AI infrastructure cost signals.",
        infra_cost_cli.main,
    ),
    "bio": Domain(
        "bio",
        "Audit bio-AI claims against an evidence and safety gate before deployment.",
        bio_cli.main,
    ),
    "model": Domain(
        "model",
        "Diligence ledger for model benchmark, cost, safety, and adoption claims.",
        model_cli.main,
    ),
}


def get_domain(name: str) -> Domain | None:
    return DOMAINS.get(name)
