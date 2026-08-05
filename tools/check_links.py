#!/usr/bin/env python3
"""Validate the static site before it ships.

Checks that every internal link resolves to a real file, that every #fragment
points at an element that exists, that referenced assets are present, and that
images carry alt text.

    python3 tools/check_links.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag

ROOT = Path(__file__).resolve().parents[1]

REF_ATTRS = {"href", "src"}
EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|data:|#|//)")


class PageParser(HTMLParser):
    """Collects outgoing references, element ids and images lacking alt text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.ids: set[str] = set()
        self.images_without_alt: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: (value or "") for key, value in attrs}

        if "id" in values:
            self.ids.add(values["id"])
        if "name" in values and tag == "a":
            self.ids.add(values["name"])

        for attr in REF_ATTRS:
            if attr in values and values[attr]:
                self.refs.append(values[attr])

        if tag == "img" and "alt" not in values:
            self.images_without_alt.append(values.get("src", "(no src)"))


def parse(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def resolve(target: str) -> Path | None:
    """Map a site-absolute URL path to the file the server would return."""
    rel = unquote(target).lstrip("/")
    candidates = [ROOT / rel]
    if target.endswith("/") or "." not in Path(rel).name:
        candidates.append(ROOT / rel / "index.html")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    pages = [p for p in sorted(ROOT.rglob("*.html")) if "tools" not in p.parts]
    if not pages:
        sys.exit("no pages found")

    parsed = {path: parse(path) for path in pages}
    problems: list[str] = []

    for path, page in parsed.items():
        where = path.relative_to(ROOT)

        for src in page.images_without_alt:
            problems.append(f"{where}: <img> without alt — {src}")

        for ref in page.refs:
            if EXTERNAL.match(ref):
                # Same-page fragments still need a matching element.
                if ref.startswith("#") and ref != "#" and ref[1:] not in page.ids:
                    problems.append(f"{where}: no element with id '{ref[1:]}'")
                continue

            if not ref.startswith("/"):
                problems.append(f"{where}: relative reference '{ref}' — use a site-absolute path")
                continue

            target, fragment = urldefrag(ref)
            resolved = resolve(target)
            if resolved is None:
                problems.append(f"{where}: broken link '{ref}'")
                continue

            if fragment and resolved.suffix == ".html":
                if fragment not in parsed.setdefault(resolved, parse(resolved)).ids:
                    problems.append(f"{where}: '{target}' has no id '{fragment}'")

    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in sorted(set(problems)):
            print(f"  {problem}")
        return 1

    print(f"ok — {len(pages)} pages, no broken references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
