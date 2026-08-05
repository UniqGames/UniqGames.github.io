#!/usr/bin/env python3
"""Propagate the shared header and footer across every page.

The deployed site is plain static HTML with no build step, so the shell is
physically duplicated in each file. This script keeps those copies honest:
index.html is the single source of truth, and every other page receives the
same markup between its <!-- shell:header --> / <!-- shell:footer --> markers.

It also marks the current page in the navigation with aria-current="page".

    python3 tools/sync_shell.py          # rewrite pages
    python3 tools/sync_shell.py --check  # fail if anything is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "index.html"
BLOCKS = ("header", "footer")


def extract(html: str, name: str) -> str:
    match = re.search(
        rf"<!-- shell:{name} -->(.*?)<!-- /shell:{name} -->", html, re.DOTALL
    )
    if not match:
        sys.exit(f"index.html is missing the shell:{name} block")
    return match.group(1)


def page_url(path: Path) -> str:
    """Map a file on disk to the URL the server will publish it under."""
    rel = path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def mark_current(block: str, url: str) -> str:
    """Flag navigation links that point at the page currently being written."""
    block = block.replace(' aria-current="page"', "")
    if url == "/":
        return block
    return re.sub(
        rf'(<a\b[^>]*\bhref="{re.escape(url)}")',
        r'\1 aria-current="page"',
        block,
    )


def apply_block(html: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- shell:{name} -->).*?(<!-- /shell:{name} -->)", re.DOTALL
    )
    if not pattern.search(html):
        return html
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), html, count=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args()

    source_html = SOURCE.read_text(encoding="utf-8")
    blocks = {name: extract(source_html, name) for name in BLOCKS}

    stale: list[str] = []
    touched = 0

    for path in sorted(ROOT.rglob("*.html")):
        if path == SOURCE or "tools" in path.parts:
            continue

        original = path.read_text(encoding="utf-8")
        updated = original
        url = page_url(path)
        for name, body in blocks.items():
            updated = apply_block(updated, name, mark_current(body, url))

        if updated == original:
            continue

        stale.append(str(path.relative_to(ROOT)))
        if not args.check:
            path.write_text(updated, encoding="utf-8")
            touched += 1

    if args.check:
        if stale:
            print("shell out of date:\n  " + "\n  ".join(stale))
            return 1
        print("shell in sync")
        return 0

    print(f"synced {touched} page(s)" if touched else "nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
