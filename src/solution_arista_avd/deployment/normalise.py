"""Turn a device's raw comparison output into "does this device need pushing?".

**This module is why the reconciler is safe to run.** Phase 0 measured all three
comparators against the running lab and found that two of them reported a
non-empty difference against an artifact the device already matched:

* **FRR** reported ``neighbor <addr> activate``, ``service
  integrated-vtysh-config`` and ``line vty`` every time. That family is gone:
  the WAN re-platformed onto SR Linux, whose own ``diff flat`` is empty for an
  in-sync router -- measured on all six, see ``normalise_srl``.
* **Junos** reports changed lines every time: the eleven zone-pair blocks in a
  different order, and the artifact's comment blocks round-tripping.

Read as-is, that means "this device differs", and a reconciler acting on it
replaces the firewall's configuration **on every cycle, forever**, while every
log line says success.

So: ``differs`` is computed from ``normalise(...)``, never from the raw text.

Three rules govern this module, and the third is the one that keeps it honest:

1. **Allowlist, never denylist.** Only patterns named here are suppressed.
2. **Every suppression carries its reason**, because "why is this ignored?" is
   the question someone will ask at 3am.
3. **Fail noisy.** Anything unrecognised counts as a difference. The failure mode
   of a gap in this file is an unnecessary push, never a missed one.

**A suppression can be a bug in disguise.** This module used to suppress the
``fxp0`` management interface, because ``load replace`` on the whole
``interfaces`` hierarchy deleted it on every push and vrnetlab restored it. The
suppression was right about the diff and wrong about the cause. Fixing the push
-- tagging each modelled interface rather than the stanza -- removed the diff and
the suppression with it. Before adding a rule here, ask whether the device is
telling you something true.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------
# SR Linux
# --------------------------------------------------------------------------

# The two lines sr_cli prints when it leaves candidate mode. Status, never
# configuration. Everything else the comparison prints is a `diff flat` line --
# `insert / ...`, `delete / ...` -- and counts.
_SRL_STATUS = (
    re.compile(r"^All changes have been discarded\. Leaving candidate mode\.\s*$"),
    re.compile(r"^All changes have been committed\. Leaving candidate mode\.\s*$"),
)


def normalise_srl(raw: str) -> list[str]:
    """Significant lines from the candidate's `diff flat`.

    **No suppression at all**, like EOS and unlike the FRR it replaced. The
    comparison deletes the three owned subtrees and re-sets them from the
    artifact inside one candidate, so the router compares intent against
    running itself: an in-sync router prints nothing but the status line.
    Measured on all six prototype routers straight after boot, and then the
    other way -- a hand edit on the device shows as exactly the lines that undo
    it (tests/unit/fixtures/deployment/srl/).

    A value change is printed as a single `insert` of the new value, not a
    delete-and-insert pair, so the line count of a diff is not a count of
    changed leaves.

    Unrecognised output counts, per the fail-noisy rule. The comparator raises
    before this is reached when sr_cli exits non-zero -- an aborted candidate
    prints no diff, and an empty diff must never come from a candidate that did
    not load.
    """
    return [
        line.rstrip()
        for line in raw.splitlines()
        if line.strip() and not any(pattern.match(line.strip()) for pattern in _SRL_STATUS)
    ]


# --------------------------------------------------------------------------
# Junos
# --------------------------------------------------------------------------

# `!` marks a block Junos considers changed *in position*. Every one measured on
# fw1 is a zone pair, and AGENTS.md already documents why their order cannot be
# modelled: a zone pair is derived from each rule's source and destination zone,
# so no object exists to carry an order, and Junos matches a packet to its pair
# by zone rather than by position. Presentation, not configuration.
_JUNOS_MOVED = re.compile(r"^\s*!")

# `[edit ...]` banners locate the following hunk. They are never changes.
_JUNOS_BANNER = re.compile(r"^\s*\[edit\b")

# Comment syntax. Junos does not round-trip the artifact's comment blocks, so
# re-loading an identical artifact shows them removed and re-added. The
# `## SECRET-DATA` re-salting this repository already documents is the same
# phenomenon wearing a different hat.
_JUNOS_COMMENT = re.compile(r"^\s*[+-]\s*(/\*|\*|\*/|#|##)")

# NOTE: there was an `fxp0` suppression here, and its removal is the point.
#
# `load replace` on the whole `interfaces` hierarchy deleted the vSRX's
# management interface on every push, and vrnetlab restored it as root seconds
# later -- so an in-sync firewall reported `- fxp0 {...}` forever and the
# reconciler had to ignore it. Suppressing it was correct given the push, and
# wrong about the cause: the push was the bug.
#
# `_junos_replace_tagged` now tags each modelled interface instead of the
# stanza, so the candidate leaves fxp0 alone and the diff no longer mentions it.
# The suppression is gone deliberately rather than left as insurance: if the
# tagging ever regresses, this module reports the firewall as differing --
# loudly, every cycle -- instead of hiding it. That is the fail-noisy rule
# applied to itself.


def _junos_split(line: str) -> tuple[str, int, str]:
    """Split a compare line into (sign, indent, text).

    The indent is measured **after** the sign. Measuring it before was a real
    bug: the fxp0 block then never found its closing brace and swallowed the
    following hunk, which happened to be the injected control line -- so the
    normaliser reported "no difference" for a device that had genuinely changed.
    Exactly the false negative this module exists to prevent, one level up.
    """
    stripped = line.lstrip()
    if stripped[:1] in {"+", "-"}:
        sign, rest = stripped[0], stripped[1:]
        return sign, len(rest) - len(rest.lstrip()), rest.strip()
    return "", len(line) - len(stripped), stripped


def normalise_junos(raw: str) -> list[str]:
    """Significant lines from `show | compare` after a `load replace`."""
    kept: list[str] = []

    for line in raw.splitlines():
        sign, _indent, text = _junos_split(line)

        if not text or _JUNOS_BANNER.match(line):
            continue
        if _JUNOS_MOVED.match(line):
            continue
        if sign and _JUNOS_COMMENT.match(line):
            continue
        if sign:
            kept.append(line.rstrip())

    return kept


# --------------------------------------------------------------------------
# EOS
# --------------------------------------------------------------------------

_EOS_HEADER = re.compile(r"^(---|\+\+\+)\s")


def normalise_eos(raw: str) -> list[str]:
    """Significant lines from `show session-config named <s> diffs`.

    No suppression. Measured empty for an unchanged device (research R1), which
    is why EOS is the family the design review's assumption actually held for.
    """
    return [line.rstrip() for line in raw.splitlines() if line.startswith(("+", "-")) and not _EOS_HEADER.match(line)]


NORMALISERS = {
    "AVD EOS Configuration": normalise_eos,
    "SR Linux Configuration": normalise_srl,
    "Junos Configuration": normalise_junos,
}


def normalise(artifact_name: str, raw: str) -> list[str]:
    """Significant difference lines for one device, or an empty list."""
    try:
        return NORMALISERS[artifact_name](raw)
    except KeyError:  # pragma: no cover - a new family must fail loudly
        raise ValueError(
            f"no normaliser for artifact {artifact_name!r}; add one rather than "
            "comparing its raw output, which would churn the device every cycle"
        ) from None
