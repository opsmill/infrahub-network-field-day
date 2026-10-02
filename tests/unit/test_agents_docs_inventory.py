"""AGENTS.md and the developer guide must name everything `.infrahub.yml` registers.

AGENTS.md used to carry the whole inventory and was slimmed to a set of pointers into
`docs/docs/developer-guide/`. The risk of that split is silent: a generator, transform or
check registered later (or renamed) is documented nowhere and nothing says so. This holds
the registration file against the prose, and every relative link in AGENTS.md against the
filesystem, so a moved page cannot leave a dangling pointer.

Parsing nothing would make every assertion vacuous, so each test first asserts it found
something -- the shape of failure `test_handover_scope.py` exists to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
DOCS = ROOT / "docs" / "docs"

# `[text](target)`; the target ends at the first closing parenthesis.
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _registered(section: str) -> list[str]:
    config = yaml.safe_load((ROOT / ".infrahub.yml").read_text())
    names = [str(entry["name"]) for entry in config.get(section, [])]
    assert names, f"no {section} parsed out of .infrahub.yml; the parser, not the repository, is wrong"
    return names


def _documentation() -> str:
    pages = [AGENTS, *sorted(DOCS.rglob("*.md"))]
    return "\n".join(page.read_text() for page in pages)


@pytest.mark.parametrize("section", ["generator_definitions", "python_transforms", "check_definitions"])
def test_every_registered_name_is_documented(section: str) -> None:
    text = _documentation()
    missing = [name for name in _registered(section) if name not in text]
    assert not missing, (
        f"{section} registered in .infrahub.yml but named in neither AGENTS.md nor docs/docs/: {missing}. "
        "Describe each in docs/docs/developer-guide/generator-transform-inventory.md."
    )


def test_the_unregistered_cloudvision_check_is_still_explained() -> None:
    """It is kept in code but not registered, so the registration loop cannot see it."""
    assert "cv-config-validation" in _documentation()


def test_every_relative_link_in_agents_md_resolves() -> None:
    targets = [
        t
        for t in LINK.findall(re.sub(r"`[^`]*`", "", AGENTS.read_text()))
        if not re.match(r"[a-z]+:", t) and not t.startswith("#")
    ]
    assert targets, "no relative links found in AGENTS.md; the parser, not the file, is wrong"

    broken = [t for t in targets if not (AGENTS.parent / t.split("#")[0]).exists()]
    assert not broken, f"AGENTS.md links to files that do not exist: {broken}"


def test_every_developer_guide_page_is_in_the_sidebar() -> None:
    sidebar = (ROOT / "docs" / "sidebars.ts").read_text()
    pages = sorted((DOCS / "developer-guide").glob("*.md"))
    assert pages
    missing = [p.stem for p in pages if f"developer-guide/{p.stem}'" not in sidebar]
    assert not missing, f"developer-guide pages absent from docs/sidebars.ts: {missing}"
