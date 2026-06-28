"""claim-gate — one evidence-gated claim/signal ledger, many domains.

A single tool that ingests public AI claims and signals, holds them in a local evidence ledger,
validates them against domain-specific evidence rules, and emits an act / hold / verify-first
recommendation. Each domain (infra-cost, bio, model) plugs in its own schema and rules behind a
shared CLI and packaging harness.
"""

__version__ = "0.2.0"
