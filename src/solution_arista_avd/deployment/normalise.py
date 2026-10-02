"""Turn a device's raw comparison output into "does this device need pushing?".

**This module is why the reconciler is safe to run.** Phase 0 measured all three
comparators against the running lab and found that two of them reported a
non-empty difference against an artifact the device already matched:

* **FRR** reported ``neighbor <addr> activate``, ``service
  integrated-vtysh-config`` and ``line vty`` every time. That family is gone:
  the WAN re-platformed onto SR Linux, whose own ``diff flat`` is empty for an
  in-sync router -- measured on all six, see ``normalise_srl``.
* **Junos** reports changed lines every time: the zone-pair blocks in a
  different order, the artifact's comment blocks round-tripping, the
  `version` and `uid` Junos stamps on every commit, and -- against a freshly
  booted vSRX -- both password hashes re-salted.

The Junos comparison is also BLIND in one place, which is the opposite failure:
`show | compare` never prints a `plain-text-password-value` it is about to
delete. A freshly booted vSRX carries two of them from vrnetlab's `init.conf`,
and its whole diff normalised to empty, so the reconciler confirmed `fw1`
in sync with cleartext credentials on it and never pushed. The comparator
therefore asks the running configuration directly (`JUNOS_CLEARTEXT_PROBE`),
and a cleartext secret is a difference by a rule no suppression can override.

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

import hashlib
import re

from solution_arista_avd.deployment import devices

# --------------------------------------------------------------------------
# SR Linux
# --------------------------------------------------------------------------

# The one line sr_cli prints when a comparison leaves candidate mode. Status,
# never configuration. A comparison never commits, so the "committed" variant is
# deliberately NOT here: seen in a comparison it means something went wrong,
# and it counts. Everything else printed is a `diff flat` line and counts.
_SRL_STATUS = (re.compile(r"^All changes have been discarded\. Leaving candidate mode\.\s*$"),)


def normalise_srl(raw: str) -> list[str]:
    """Significant lines from the candidate's `diff flat` of a FULL replace.

    **No suppression at all**, like EOS and unlike the FRR it replaced. The
    comparison empties a candidate with `delete /`, rebuilds it from the whole
    artifact -- /system included -- and asks the router for `diff flat`, so the
    router compares intent against its entire running configuration itself.
    Measured on all six prototype routers straight after booting the full
    artifact: nothing but the status line. And the other way: hand edits inside
    /system and outside it show as exactly the lines that undo them, and a moved
    artifact as exactly its two changed lines out of roughly nine hundred
    (tests/unit/fixtures/deployment/srl_*).

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
#
# The comparison is `load override` of the WHOLE artifact against the WHOLE
# running configuration (cycle 035), so `system` is compared like everything
# else. Measured on a throwaway vSRX booted exactly like fw1; every rule below
# cites the capture that justified it, in tests/unit/fixtures/deployment/.

# `!` marks a block Junos considers changed *in position*. Every one measured on
# fw1 is a zone pair, and AGENTS.md already documents why their order cannot be
# modelled: a zone pair is derived from each rule's source and destination zone,
# so no object exists to carry an order, and Junos matches a packet to its pair
# by zone rather than by position. Presentation, not configuration.
_JUNOS_MOVED = re.compile(r"^\s*!")

# `[edit ...]` banners locate the following hunk. They are never changes.
_JUNOS_BANNER = re.compile(r"^\s*\[edit\b")

# Comment syntax. Junos does not round-trip the artifact's comment blocks, so
# re-loading an identical artifact shows them removed and re-added.
_JUNOS_COMMENT = re.compile(r"^\s*[+-]\s*(/\*|\*|\*/|#|##)")

# Statements Junos WRITES ITSELF on every commit, so the artifact never states
# them and every comparison shows them as deletions. Each is matched only as a
# deletion and only under the banner it was measured under (junos_clean.diff):
#
# * `version` -- stamped from the running software at commit. Rendering it
#   would tie the artifact to one firmware release for no behaviour.
# * `uid` -- assigned to a login that names none (2000 for the first). The
#   override re-assigns it, so a removal here is Junos's bookkeeping.
_JUNOS_COMMIT_STAMPED = (
    (re.compile(r"^\[edit\]$"), re.compile(r"^version \S+;$")),
    (re.compile(r"^\[edit system login user \S+\]$"), re.compile(r"^uid \d+;$")),
)

# A hashed secret. `## SECRET-DATA` is how Junos marks it in `show | compare`.
_JUNOS_SECRET = re.compile(r'^(encrypted-password) "([^"]+)";\s*## SECRET-DATA$')

# A CLEARTEXT secret, and the one rule here that runs before every suppression.
#
# vrnetlab's init.conf writes both logins as `plain-text-password-value
# "admin@123"`, and Junos keeps that leaf verbatim when the file is the boot
# configuration. A full `load override` deletes it -- measured: the first push
# onto a booted vSRX removed exactly those two `display set` lines -- but
# `show | compare` does NOT print the deletion. The only visible trace in the
# freshly-booted capture is the two re-salted `encrypted-password` pairs, which
# `junos_same_secret` correctly proves to be the same password and suppresses.
# So the whole diff normalised to empty, and fw1 was confirmed `in_sync` with
# cleartext credentials in its running configuration -- after every reboot.
#
# Hence two things. The comparator probes the running configuration for the
# leaf (`JUNOS_CLEARTEXT_PROBE`) and appends what it finds as deletions, because
# the push removes them. And any statement naming the leaf, from the probe or
# from `show | compare` itself, is kept whatever its sign and whatever else
# would match it, with the value redacted: the normalised diff is stored in
# Infrahub, and a credential must never be copied there.
_JUNOS_CLEARTEXT = re.compile(r"\bplain-text-password-value\b")
_JUNOS_CLEARTEXT_VALUE = re.compile(r'(\bplain-text-password-value\s+)("[^"]*"|[^\s;]+)')
_JUNOS_COMMENT_TEXT = ("/*", "*", "#")

# Operational mode, so it reads the COMMITTED configuration -- the thing a
# booted device carries -- and changes nothing. `| match` keeps the secret's
# neighbours, and everything else, out of the output.
JUNOS_CLEARTEXT_PROBE = "show configuration | display set | match plain-text-password-value"

# Locates the probe's lines in the raw comparison. Not an `[edit` banner, and
# carries no sign, so the normaliser never mistakes it for configuration.
JUNOS_CLEARTEXT_BANNER = "[running configuration: cleartext secrets the push removes]"

JUNOS_REDACTED = '"<redacted>"'


def redact_junos_cleartext(line: str) -> str:
    """The line with every `plain-text-password-value` value replaced."""
    return _JUNOS_CLEARTEXT_VALUE.sub(lambda m: m.group(1) + JUNOS_REDACTED, line)


def junos_running_cleartext(probe_output: str) -> list[str]:
    """Each cleartext statement the probe found, as a redacted deletion.

    Only `set` lines naming the leaf count; the echoed command and the prompts
    around it do not. Deletions, because that is what the push does to them.
    """
    return [
        f"- {redact_junos_cleartext(line.strip())}"
        for line in probe_output.splitlines()
        if line.strip().startswith("set ") and _JUNOS_CLEARTEXT.search(line)
    ]


# NOTE: there was an `fxp0` suppression here, and its removal is the point.
#
# `load replace` on the whole `interfaces` hierarchy deleted the vSRX's
# management interface on every push, and vrnetlab restored it as root seconds
# later -- so an in-sync firewall reported `- fxp0 {...}` forever and the
# reconciler had to ignore it. Suppressing it was correct given the push, and
# wrong about the cause: the push was the bug. fxp0 is modelled now, and under
# `load override` an fxp0 deletion in the diff means the artifact lost it --
# which the push's lifeline refuses. It is reported, never hidden.


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


# -- SHA-crypt, so a re-salted secret can be recognised -----------------------
#
# Python 3.13 removed the `crypt` module, and the reconciler image is 3.13, so
# this is the published algorithm (Drepper, "Unix crypt using SHA-256 and
# SHA-512") in the standard library's hashlib. Verified against `openssl
# passwd -6` and against the lab's own `$6$otternetlab$...` hash in the tests.

_B64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SHA512_ORDER = (
    (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48),
    (28, 49, 7), (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13),
    (56, 14, 35), (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41),
)  # fmt: skip
_SHA256_ORDER = (
    (0, 10, 20), (21, 1, 11), (12, 22, 2), (3, 13, 23), (24, 4, 14),
    (15, 25, 5), (6, 16, 26), (27, 7, 17), (18, 28, 8), (9, 19, 29),
)  # fmt: skip


def _b64_24(b2: int, b1: int, b0: int, count: int) -> str:
    word = (b2 << 16) | (b1 << 8) | b0
    out = []
    for _ in range(count):
        out.append(_B64[word & 0x3F])
        word >>= 6
    return "".join(out)


def sha_crypt(password: str, setting: str) -> str | None:
    """`crypt(3)` for `$5$` and `$6$` settings, or None for any other scheme.

    `setting` may be a full hash; only its scheme, rounds and salt are read.
    """
    parts = setting.split("$")
    if len(parts) < 3 or parts[0] or parts[1] not in {"5", "6"}:
        return None
    ident, rest = parts[1], parts[2:]
    rounds, custom = 5000, False
    if rest and rest[0].startswith("rounds="):
        try:
            rounds = max(1000, min(999_999_999, int(rest[0][len("rounds=") :])))
        except ValueError:
            return None
        custom, rest = True, rest[1:]
    if not rest:
        return None
    salt = rest[0][:16].encode()
    digest = hashlib.sha512 if ident == "6" else hashlib.sha256
    size = digest().digest_size
    key = password.encode()

    alternate = digest(key + salt + key).digest()
    ctx = digest(key + salt)
    remaining = len(key)
    while remaining > size:
        ctx.update(alternate)
        remaining -= size
    ctx.update(alternate[:remaining])
    bits = len(key)
    while bits:
        ctx.update(alternate if bits & 1 else key)
        bits >>= 1
    current = ctx.digest()

    p_bytes = (digest(key * len(key)).digest() * (len(key) // size + 1))[: len(key)]
    s_bytes = (digest(salt * (16 + current[0])).digest() * (len(salt) // size + 1))[: len(salt)]

    for index in range(rounds):
        ctx = digest(p_bytes if index & 1 else current)
        if index % 3:
            ctx.update(s_bytes)
        if index % 7:
            ctx.update(p_bytes)
        ctx.update(current if index & 1 else p_bytes)
        current = ctx.digest()

    if ident == "6":
        encoded = "".join(_b64_24(current[a], current[b], current[c], 4) for a, b, c in _SHA512_ORDER)
        encoded += _b64_24(0, 0, current[63], 2)
    else:
        encoded = "".join(_b64_24(current[a], current[b], current[c], 4) for a, b, c in _SHA256_ORDER)
        encoded += _b64_24(0, current[31], current[30], 3)
    prefix = f"${ident}$" + (f"rounds={rounds}$" if custom else "")
    return f"{prefix}{salt.decode()}${encoded}"


def junos_same_secret(first: str, second: str, passwords: tuple[str, ...]) -> bool:
    """True only when both hashes are PROVEN to be one of `passwords`.

    Junos re-salts a `## SECRET-DATA` value when it loads it -- measured: the
    lab's `$6$otternetlab$...` hash came back as `$6$<random>$...` of the same
    password on every load against a freshly booted vSRX -- so two different
    strings can be one password. The only way to know is to hash a candidate
    password with each salt. A hash no known password explains is a CHANGED
    secret, and reads as drift: proving sameness is what suppresses, never
    failing to prove difference.
    """
    if first == second:
        return True
    return any(
        password and sha_crypt(password, first) == first and sha_crypt(password, second) == second
        for password in passwords
    )


def _known_passwords() -> tuple[str, ...]:
    """The credential the reconciler itself logs in with, and nothing else."""
    return (devices.VSRX_PASSWORD,)


def normalise_junos(raw: str, passwords: tuple[str, ...] | None = None) -> list[str]:
    """Significant lines from `show | compare` after a `load override`.

    `raw` is what `compare.compare_junos` returns: the compare output, then
    any cleartext statements the running configuration carries under
    `JUNOS_CLEARTEXT_BANNER`. A cleartext statement is always significant.

    `passwords` are the secrets a re-salted hash may be proven against; by
    default the reconciler's own login password.
    """
    known = _known_passwords() if passwords is None else passwords
    kept: list[str | None] = []
    banner = ""
    # Secret lines in the current hunk: (position in kept, sign, leaf, hash).
    secrets: list[tuple[int, str, str, str]] = []

    def flush() -> None:
        removed = [s for s in secrets if s[1] == "-"]
        added = [s for s in secrets if s[1] == "+"]
        paired = len(removed) == 1 and len(added) == 1 and removed[0][2] == added[0][2]
        if paired and junos_same_secret(removed[0][3], added[0][3], known):
            kept[removed[0][0]] = None
            kept[added[0][0]] = None
        secrets.clear()

    for line in raw.splitlines():
        sign, _indent, text = _junos_split(line)

        if _JUNOS_BANNER.match(line):
            flush()
            banner = line.strip()
            continue
        # Before every suppression, whatever its sign -- see _JUNOS_CLEARTEXT.
        if _JUNOS_CLEARTEXT.search(text) and not text.startswith(_JUNOS_COMMENT_TEXT):
            kept.append(redact_junos_cleartext(line.rstrip()))
            continue
        if not text or _JUNOS_MOVED.match(line):
            continue
        if not sign or _JUNOS_COMMENT.match(line):
            continue
        if sign == "-" and any(b.match(banner) and s.match(text) for b, s in _JUNOS_COMMIT_STAMPED):
            continue
        secret = _JUNOS_SECRET.match(text)
        if secret:
            secrets.append((len(kept), sign, secret.group(1), secret.group(2)))
        kept.append(line.rstrip())
    flush()

    return [line for line in kept if line is not None]


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
