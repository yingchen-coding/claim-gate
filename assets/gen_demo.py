#!/usr/bin/env python3
"""Generate assets/demo.svg — a reproducible terminal-cast hero for this repo's README.

Pure stdlib, deterministic (no timestamps/random). Regenerate with: python3 assets/gen_demo.py
"""
from __future__ import annotations

import html
from pathlib import Path

TITLE = 'claim-gate — no hyped model claim ships unverified'
LINES = [
    ('$ claim-gate model import-feed today.json', 'cmd'),
    ('  imported 12 model claims from the news feed', 'dim'),
    ('', 'blank'),
    ('$ claim-gate model check abcoder-mcp', 'cmd'),
    ('  ✗ BLOCKED — no local verification; source is a launch blog', 'err'),
    ('', 'blank'),
    ('$ claim-gate model verify abcoder-mcp --command "python eval.py" --passed', 'cmd'),
    ('  ✓ evidence recorded', 'ok'),
    ('$ claim-gate model check abcoder-mcp', 'cmd'),
    ('  ✓ may be acted on — backed by 1 passing local check', 'ok'),
]

PALETTE = {
    "cmd": "#e6edf3", "ok": "#3fb950", "err": "#f85149",
    "dim": "#8b949e", "comment": "#8b949e", "blank": "#e6edf3",
}
PAD_X, PAD_TOP, LINE_H, FONT = 22, 58, 22, 13.5
W = 780
H = PAD_TOP + LINE_H * len(LINES) + 20


def main() -> None:
    rows = []
    y = PAD_TOP
    for text, role in LINES:
        if text:
            rows.append(
                f'<text x="{PAD_X}" y="{y}" fill="{PALETTE[role]}" '
                f'xml:space="preserve">{html.escape(text)}</text>'
            )
        y += LINE_H
    dots = "".join(
        f'<circle cx="{18 + i * 20}" cy="20" r="6" fill="{c}"/>'
        for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f"))
    )
    mono = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    title_font = 'font-family="monospace" font-size="12" text-anchor="middle"'
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(TITLE)}">',
        f'  <rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#30363d"/>',
        f'  <rect width="{W}" height="40" rx="10" fill="#161b22"/>',
        f'  <rect y="30" width="{W}" height="10" fill="#161b22"/>',
        f"  {dots}",
        f'  <text x="{W // 2}" y="24" fill="#8b949e" {title_font}>'
        f"{html.escape(TITLE)}</text>",
        f'  <g font-family="{mono}" font-size="{FONT}">',
        f'    {"".join(rows)}',
        "  </g>",
        "</svg>",
        "",
    ]
    out = Path(__file__).resolve().parent / "demo.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out} ({len(LINES)} lines)")


if __name__ == "__main__":
    main()
