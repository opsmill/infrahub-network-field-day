"""Turn a device's raw comparison output into "does this device need pushing?".

**This module is why the reconciler is safe to run.** Phase 0 measured all three
comparators against the running lab and found that two of them report a
non-empty difference against an artifact the device already matches:

* **FRR** reports ``neighbor <addr> activate``, ``service
  integrated-vtysh-config`` and ``line vty`` every time, because the artifact
  states them and ``show running-config`` never echoes them back -- the first is
  FRR's default for IPv4 unicast, the other two are file directives rather than
  running state.
* **Junos** reports changed lines every time: the eleven zone-pair blocks in a
  different order, and the artifact's comment blocks round-tripping.

Read as-is, that means "this device differs", and a reconciler acting on it
replaces the configuration of every FRR router and the firewall **on every cycle,
forever**, while every log line says success.

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
# FRR
# --------------------------------------------------------------------------

# `frr-reload.py --test` prints sections, NOT `+`/`-` prefixed lines. A parser
# written against diff prefixes returns "no differences" for a device that has
# genuinely changed -- a false negative that reads exactly like success.
_FRR_SECTION = re.compile(r"^Lines To (Add|Delete)\s*$")
_FRR_RULE = re.compile(r"^=+\s*$")

# Suppressed, with the reason each one is not evidence of drift.
_FRR_SUPPRESSED = (
    # Activation for IPv4 unicast is FRR's default, so the running configuration
    # omits it while the artifact states it explicitly. Verified against
    # branch-rtr: `show running-config` carries remote-as, description and
    # route-map for the same neighbour, but never `activate`.
    re.compile(r"^\s*neighbor \S+ activate\s*$"),
    # A configuration-file directive. It is not running state and never appears
    # in `show running-config`.
    re.compile(r"^\s*service integrated-vtysh-config\s*$"),
    # Same: vtysh writes it into the file, the running configuration has no
    # equivalent to compare against.
    re.compile(r"^\s*line vty\s*$"),
)

# Block openers whose presence is only ever context. They are dropped when
# nothing survives inside them; kept when something does.
_FRR_SCAFFOLD = (
    # `router bgp <asn>` and its per-VRF form. The VRF variant is spelled out
    # because leaving it off is not a cosmetic miss: on a provider edge every
    # customer VRF carries its own `neighbor ... activate`, so the suppressed
    # inner line leaves an unsuppressed wrapper behind and the device reports a
    # difference forever. Found on isp-pe1 by the fail-noisy rule doing its job.
    re.compile(r"^\s*router bgp \d+( vrf \S+)?\s*$"),
    re.compile(r"^\s*address-family \S+ \S+\s*$"),
)

_FRR_TERMINATOR = re.compile(r"^\s*(exit|end)\s*$")


def _frr_significant(section: list[str]) -> list[str]:
    """Drop suppressed lines, then any scaffolding they leave empty."""
    kept: list[str] = []
    # Walk backwards so a scaffold line can see whether anything survived after
    # it at a deeper indent.
    survived_deeper: dict[int, bool] = {}
    for raw in reversed(section):
        if not raw.strip() or _FRR_TERMINATOR.match(raw):
            continue
        depth = len(raw) - len(raw.lstrip())
        if any(pattern.match(raw) for pattern in _FRR_SUPPRESSED):
            continue
        if any(pattern.match(raw) for pattern in _FRR_SCAFFOLD) and not any(
            deeper for at, deeper in survived_deeper.items() if at > depth
        ):
            continue
        kept.append(raw.rstrip())
        survived_deeper[depth] = True
        survived_deeper = {at: v for at, v in survived_deeper.items() if at <= depth or v}
    return list(reversed(kept))


def normalise_frr(raw: str) -> list[str]:
    """Significant lines from `frr-reload.py --test` output.

    Exit status is deliberately not consulted anywhere: `--test` returns 0
    whether or not the configuration matches (measured, research R2).
    """
    section: list[str] = []
    collecting = False
    for line in raw.splitlines():
        if _FRR_SECTION.match(line):
            collecting = True
            continue
        if _FRR_RULE.match(line):
            continue
        if collecting:
            section.append(line)
    return _frr_significant(section)


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
    "FRR Configuration": normalise_frr,
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
