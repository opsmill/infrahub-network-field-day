"""Versions that are written down in more than one place must agree.

**The Infrahub release.** The `Dockerfile`'s `ARG INFRAHUB_BASE_VERSION` default
is the one source: `invoke` exports it to every compose command, and
docker-compose.yml's upstream image falls back to `INFRAHUB_BASE_VERSION` before
its own literal. The literals that remain -- compose fallbacks for a bare
`docker compose` run, the CI workflow, the README, the constitution -- cannot read
a Dockerfile, so this holds each of them to it. A bump that misses one fails
here, naming the file and line, rather than as a stack running two releases.

The scan is by PATTERN across the repository, not by a list of files, so a new
place that pins the version is covered without anyone remembering to add it.
Prose that records what was measured against a release ("returns 500 on
1.10.6") is history, not a pin, and matches none of the patterns.

**Container images.** Every image is pinned to an exact tag: no `:latest` and
no untagged reference, which is `:latest` by another name. A floating tag makes
a rebuild pull something nobody tested, with nothing in the diff to say so.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

SEMVER = r"(\d+\.\d+\.\d+)"

# Each pattern captures the version in a form that only ever means "the Infrahub
# release this project runs".
INFRAHUB_PIN_PATTERNS = (
    # ARG default, ${INFRAHUB_BASE_VERSION:-x}, `export ...=x`, `--build-arg ...=x`
    re.compile(r"INFRAHUB_BASE_VERSION(?:=|:-)" + SEMVER),
    re.compile(r"\$\{VERSION:-" + SEMVER + r"\}"),
    re.compile(r"opsmill/infrahub(?:-solution-arista-avd)?:" + SEMVER),
    re.compile(r'INFRAHUB_TESTING_IMAGE_VER: "' + SEMVER + '"'),
    re.compile(r"extending Infrahub " + SEMVER),
)

# Places that MUST carry a pin. Without this, a pattern that stopped matching
# would turn the agreement check into a check over nothing.
REQUIRED_PIN_FILES = (
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.override.yml",
    ".github/workflows/ci.yml",
    "README.md",
    ".specify/memory/constitution.md",
)

SKIPPED_DIRECTORIES = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    ".yarn",
    # Vendored agent content, other worktrees, and generated lab state.
    ".agents",
    ".claude",
    ".superset",
    "clab-otternet",
    # Spec-kit cycles record what each one did, at the version it was done on.
    "specs",
}

SKIPPED_FILES = {
    # Its comments quote a compose line as an example of what its sed rewrites;
    # the example is illustration, not a pin.
    ".github/workflows/update-infrahub.yml",
    "tests/unit/test_pinned_versions.py",
}

SCANNED_SUFFIXES = {".yml", ".yaml", ".md", ".py", ".toml", ".sh", ".ts", ".json", ".ini", ".cfg"}


def _scanned_files() -> list[Path]:
    files = []
    for directory, subdirectories, names in os.walk(ROOT):
        subdirectories[:] = [d for d in subdirectories if d not in SKIPPED_DIRECTORIES]
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if relative in SKIPPED_FILES:
                continue
            if path.suffix in SCANNED_SUFFIXES or name.startswith("Dockerfile") or name == "Makefile":
                files.append(path)
    return files


def _infrahub_source_version() -> str:
    match = re.search(r"^ARG INFRAHUB_BASE_VERSION=(\S+)$", (ROOT / "Dockerfile").read_text(), re.MULTILINE)
    assert match, "Dockerfile has no `ARG INFRAHUB_BASE_VERSION=<version>` default -- that line is the one source"
    return match.group(1)


def _infrahub_pins() -> list[tuple[str, int, str]]:
    pins = []
    for path in _scanned_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for pattern in INFRAHUB_PIN_PATTERNS:
                pins.extend(
                    (path.relative_to(ROOT).as_posix(), number, found.group(1)) for found in pattern.finditer(line)
                )
    return pins


def test_every_infrahub_version_pin_agrees_with_the_dockerfile() -> None:
    expected = _infrahub_source_version()
    disagreeing = [f"{file}:{line}: {version}" for file, line, version in _infrahub_pins() if version != expected]
    assert not disagreeing, (
        f"The Dockerfile targets Infrahub {expected}, but these pins say otherwise:\n  "
        + "\n  ".join(disagreeing)
        + "\nA version bump has to move every one of them; .github/workflows/update-infrahub.yml is meant to."
    )


@pytest.mark.parametrize("required", REQUIRED_PIN_FILES)
def test_each_known_pin_location_is_still_found(required: str) -> None:
    files = {file for file, _, _ in _infrahub_pins()}
    assert required in files, (
        f"{required} no longer matches any Infrahub version pattern. Either the pin moved -- update "
        "INFRAHUB_PIN_PATTERNS -- or it was removed, and REQUIRED_PIN_FILES should say so."
    )


def test_semaphore_installs_the_locked_infrahub_sdk() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked = next(package["version"] for package in lock["package"] if package["name"] == "infrahub-sdk")
    match = re.search(r"^ARG INFRAHUB_SDK_VERSION=(\S+)$", (ROOT / "semaphore/Dockerfile").read_text(), re.MULTILINE)
    assert match, "semaphore/Dockerfile no longer pins infrahub-sdk through ARG INFRAHUB_SDK_VERSION"
    assert match.group(1) == locked, (
        f"semaphore/Dockerfile installs infrahub-sdk {match.group(1)}, uv.lock resolves {locked}"
    )


# --------------------------------------------------------------------- images

FLOATING = re.compile(r"(^|:)latest$")


def _is_pinned(reference: str) -> bool:
    """A reference is pinned when it carries a digest or a non-`latest` tag."""
    if "@sha256:" in reference:
        return True
    # A registry port (`host:5000/name`) is not a tag: only the last path segment counts.
    last = reference.rsplit("/", 1)[-1]
    if ":" not in last:
        return False
    return not FLOATING.search(last)


def _from_images() -> list[tuple[str, str]]:
    images = []
    for path in _scanned_files():
        if not path.name.startswith("Dockerfile"):
            continue
        text = path.read_text(encoding="utf-8")
        args = dict(re.findall(r"^ARG (\w+)=(\S+)$", text, re.MULTILINE))
        for reference in re.findall(r"^FROM\s+(?:--\S+\s+)*(\S+)", text, re.MULTILINE):
            resolved = re.sub(r"\$\{(\w+)\}", lambda m, args=args: args.get(m.group(1), m.group(0)), reference)
            images.append((path.relative_to(ROOT).as_posix(), resolved))
    return images


def _default(value: str) -> str:
    """`${VAR:-x}` / `${VAR:=x}` -> x, innermost first, so nested fallbacks resolve."""
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\$\{\w+:[-=]([^${}]*)\}", r"\1", value)
    return value


def _yaml_images(relative: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str):
                    found.append((relative, _default(value)))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for document in yaml.safe_load_all((ROOT / relative).read_text(encoding="utf-8")):
        walk(document)
    return found


def test_dockerfiles_name_their_base_images() -> None:
    images = _from_images()
    assert len(images) >= 5, "found too few Dockerfiles; the scan is no longer looking where they are"
    floating = [f"{file}: FROM {image}" for file, image in images if not _is_pinned(image)]
    assert not floating, "Base images must be pinned to an exact tag:\n  " + "\n  ".join(floating)


@pytest.mark.parametrize(
    "relative",
    ["docker-compose.yml", "docker-compose.override.yml", "lab/otternet.clab.yml", "tooling/10-dex.yaml"],
)
def test_manifests_pin_their_images(relative: str) -> None:
    images = _yaml_images(relative)
    assert images, f"{relative} names no image; the walk is no longer finding them"
    floating = [image for _, image in images if not _is_pinned(image)]
    assert not floating, f"{relative} pulls a floating image: {floating}"


def test_seeded_containerlab_images_are_pinned() -> None:
    text = (ROOT / "objects/03_device_type.yml").read_text(encoding="utf-8")
    images = re.findall(r"containerlab_image:\s*(\S+)", text)
    assert images
    floating = [image for image in images if not _is_pinned(image)]
    assert not floating, f"objects/03_device_type.yml seeds a floating containerlab image: {floating}"
