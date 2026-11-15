"""Emit dashboard theme CSS variables from apps.salons.themes (single source of truth)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.salons.themes import DASHBOARD_THEME_TOKENS, GLOBAL_DASHBOARD_THEME, SHARED_STATUS_TOKENS  # noqa: E402

OUT = ROOT / "static" / "src" / "_theme_tokens.css"

SHARED_LINES = "\n".join(f"  {k}: {v};" for k, v in SHARED_STATUS_TOKENS.items())

theme_order = [GLOBAL_DASHBOARD_THEME] + [k for k in DASHBOARD_THEME_TOKENS if k != GLOBAL_DASHBOARD_THEME]
blocks: list[str] = []
for theme_key in theme_order:
    tokens = DASHBOARD_THEME_TOKENS[theme_key]
    lines = "\n".join(f"  {k}: {v};" for k, v in tokens.items())
    blocks.append(
        f'html[data-theme="{theme_key}"],\n'
        f'body[data-theme="{theme_key}"] {{\n'
        f"{lines}\n"
        f"{SHARED_LINES}\n"
        f"}}"
    )

content = (
    "/* Auto-generated — do not edit. Run: python scripts/write_theme_tokens_css.py */\n\n"
    + "\n\n".join(blocks)
    + "\n"
)

OUT.write_text(content, encoding="utf-8")
print(f"Wrote {OUT}")
