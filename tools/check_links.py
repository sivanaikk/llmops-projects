"""Fail if any relative link in the course's markdown points at a missing file or heading.

    python tools/check_links.py

A learner who clicks a dead link in a lesson stops trusting the lesson.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", ".terraform", "node_modules", "results"}


def slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation except - and _, spaces to -."""
    h = heading.strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def anchors(md: Path) -> set[str]:
    out, seen = set(), {}
    in_code = False
    for line in md.read_text().splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if in_code or not line.startswith("#"):
            continue
        s = slug(line.lstrip("#"))
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    return out


def main() -> int:
    broken = []
    for md in ROOT.rglob("*.md"):
        if SKIP_DIRS & set(md.relative_to(ROOT).parts):
            continue
        text = re.sub(r"```.*?```", "", md.read_text(), flags=re.DOTALL)
        for target in LINK.findall(text):
            if re.match(r"^[a-z]+://|^mailto:", target):
                continue
            path, _, anchor = target.partition("#")
            dest = (md.parent / path).resolve() if path else md
            if not dest.exists():
                broken.append(f"{md.relative_to(ROOT)}: missing {target}")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                broken.append(f"{md.relative_to(ROOT)}: no heading #{anchor} in {path or md.name}")
    for b in broken:
        print(b)
    print(f"{len(broken)} broken link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
