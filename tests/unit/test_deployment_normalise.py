"""Tests for the normalisation that makes "differs" mean something.

**These run against real device output**, captured in `fixtures/deployment/`
from the running lab minutes after `invoke provision` had made every device
match its artifact. The `_clean` fixtures are therefore what an in-sync device
actually says, and the `_control` fixtures are the same device with one known
line injected.

Both halves matter and neither is sufficient alone:

* Without the `_clean` assertions, a normaliser that suppressed everything would
  pass -- and the reconciler would never push anything.
* Without the `_control` assertions, a normaliser that suppressed everything
  would *also* pass -- and the reconciler would push nothing while reporting
  in-sync. An empty result is only evidence when something non-empty is proven
  alongside it, which is the same reason this repository never trusts an
  artifact's `Ready` status.

The defect these tests exist to prevent: Junos reports a non-empty difference
against an artifact the device already matches -- as FRR did before the WAN
moved to SR Linux -- so a reconciler reading raw output replaces the firewall's
configuration on every cycle, forever, logging success throughout.

The SR Linux fixtures (`srl_*`) come from a throwaway six-router prototype, not
the lab, which still ran FRR when they were captured. Each is the router's own
`diff flat` of the WHOLE artifact loaded as a FULL replace (`delete /` first):
`_clean_<router>` straight after booting from it, `srl_drifted` branch-rtr after
hand edits inside /system and outside it, and `srl_changed` the artifact moving
while isp-pe1 stands still.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from solution_arista_avd.deployment.normalise import (
    junos_same_secret,
    normalise,
    normalise_eos,
    normalise_junos,
    normalise_srl,
    sha_crypt,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deployment"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestInSyncDevicesAreSilent:
    """The assertion the whole feature rests on."""

    def test_eos_in_sync_normalises_to_empty(self) -> None:
        assert normalise_eos(_fixture("eos_clean.diff")) == []

    @pytest.mark.parametrize(
        "router", ["isp-pe1", "isp-pe2", "internet-rtr", "cust-acme-ce", "cust-globex-ce", "branch-rtr"]
    )
    def test_srl_in_sync_normalises_to_empty(self, router: str) -> None:
        """No suppression rule is needed for this: the router prints only its status line."""
        raw = _fixture(f"srl_clean_{router}.txt")
        assert raw.strip(), "the fixture must hold real output, not nothing"
        assert normalise_srl(raw) == []

    def test_junos_in_sync_normalises_to_empty(self) -> None:
        """Captured right after a full `load override` push, comparing the same
        artifact again. Not empty: Junos stamps `version` and assigns `uid` on
        every commit, so the artifact (which states neither) always shows them
        as deletions."""
        raw = _fixture("junos_clean.diff")
        assert "- version " in raw and "uid 2000;" in raw, "fixture should carry the real non-empty output"
        assert normalise_junos(raw) == []

    def test_a_freshly_booted_junos_normalises_to_empty(self) -> None:
        """The state every lab deploy starts in, and the first comparison live
        fw1 will see: booted from vrnetlab's init.conf plus junos.conf, never
        pushed. Its raw diff is the noisiest one measured -- comment blocks
        round-tripping, zone pairs moved, and BOTH password hashes re-salted:
        the lab's `$6$otternetlab$...` shown as `$6$<random>$...`."""
        raw = _fixture("junos_clean_boot.diff")
        assert len(raw.splitlines()) > 150, "fixture should carry the real non-empty output"
        assert raw.count("## SECRET-DATA") == 4
        assert normalise_junos(raw) == []


class TestTelemetryEnablementIsSilent:
    """Cycle 034 added device-side telemetry, and a line a device does not echo
    back verbatim would read as a permanent difference -- a push on every cycle.

    Captured from devices whose artifacts carry the new stanza: a leaf with
    `management api gnmi`, and the firewall with its `snmp` stanza bound to
    mgmt_junos -- the latter now under the full-override comparison, so it is
    the same capture as the in-sync fixture, asserted to carry the stanza.
    """

    def test_eos_with_gnmi_normalises_to_empty(self) -> None:
        assert normalise_eos(_fixture("eos_clean_gnmi.diff")) == []

    def test_junos_with_snmp_normalises_to_empty(self) -> None:
        artifact = (Path(__file__).parent / "fixtures" / "junos" / "vsrx_after_override.set").read_text()
        assert "set snmp community otternet-ro" in artifact, "the compared device must carry the stanza"
        assert normalise_junos(_fixture("junos_clean.diff")) == []


class TestRealChangesSurvive:
    """Without these, a normaliser that suppressed everything would pass."""

    def test_eos_control_line_survives(self) -> None:
        result = normalise_eos(_fixture("eos_control.diff"))
        assert result
        assert any("probe-marker" in line for line in result)

    def test_srl_drift_on_the_device_survives_inside_system_too(self) -> None:
        """Three hand edits on branch-rtr, two of them in /system, the artifact unchanged.

        The full replace is what makes the /system ones visible at all: the old
        subtree replace never compared /system. The diff is what a push would do
        to undo them -- put the logging rotation and the NETCONF port back, drop
        the description.
        """
        assert normalise_srl(_fixture("srl_drifted.txt")) == [
            "delete / interface ethernet-1/1 description",
            "insert / system ssh-server mgmt-netconf port 830",
            "insert / system logging buffer messages rotate 3",
        ]

    def test_srl_a_moved_artifact_survives(self) -> None:
        """Intent changed by a route and a description; exactly those two lines, out of ~900."""
        assert normalise_srl(_fixture("srl_changed.txt")) == [
            "insert / network-instance CUST_ACME static-routes route 10.60.99.0/24 next-hop-group acme-dr",
            'insert / network-instance default protocols bgp neighbor 10.50.255.2 description "isp-pe2 (core link)"',
        ]

    def test_junos_control_line_survives(self) -> None:
        """The control injects a real static route, NOT a comment.

        A comment-based control passes trivially against a broken normaliser,
        because a comment is exactly what Junos does not round-trip and what the
        suppression rules are meant to drop. The first version of this fixture
        made that mistake and tested nothing.

        Re-captured under `load override`: the route was added on the device by
        hand, so the artifact's comparison shows it as a deletion.
        """
        result = normalise_junos(_fixture("junos_control.diff"))
        assert result == ["-    route 10.255.255.0/24 next-hop 10.250.110.1;"]

    def test_drift_inside_system_survives(self) -> None:
        """The hierarchy the old `load replace` never compared at all.

        A syslog host and an NTP server committed by hand on the prototype --
        configuration nothing in the model states, so a full replace deletes it
        and the comparison has to say so.
        """
        result = normalise_junos(_fixture("junos_system_drift.diff"))
        assert "-   syslog {" in result
        assert "-       server 192.0.2.123;" in result
        assert not [line for line in result if "version" in line or "uid" in line]

    def test_a_changed_password_survives(self) -> None:
        """Root's hash replaced on the device with one of a DIFFERENT password.
        No known password explains it, so it is drift -- and the push restores
        the lab's."""
        result = normalise_junos(_fixture("junos_changed_password.diff"))
        assert len(result) == 2
        assert all("encrypted-password" in line for line in result)


class TestReSaltedSecrets:
    """Junos re-salts `## SECRET-DATA` on load; the same password under a new
    salt is not drift, a different password is. Only proof suppresses."""

    LAB_HASH = "$6$otternetlab$1ni88meu2WmQvWmveReLJXVojb6LSSOmcM75qXpzCLKzUzoU63yFywA2YQLoFI2QDjo4RXF28DbWY9wg9gKT71"

    def test_sha_crypt_reproduces_the_labs_hash(self) -> None:
        """The lab file says it was made with `openssl passwd -6 -salt otternetlab`."""
        assert sha_crypt("admin@123", self.LAB_HASH) == self.LAB_HASH

    def test_sha_crypt_reproduces_a_hash_junos_generated(self) -> None:
        """A salt Junos chose itself, taken from the boot capture."""
        raw = _fixture("junos_clean_boot.diff")
        generated = [h for h in re.findall(r'encrypted-password "([^"]+)"', raw) if h != self.LAB_HASH]
        assert generated
        for value in generated:
            assert sha_crypt("admin@123", value) == value

    def test_sha256_crypt_and_custom_rounds(self) -> None:
        """Both checked against `openssl passwd -5` / `-6` with the same settings."""
        assert sha_crypt("Hello world!", "$5$saltstring") == "$5$saltstring$5B8vYYiY.CVt1RlTTf8KbXBH3hsxY/GNooZaBBGWEc5"
        assert sha_crypt("Hello world!", "$6$rounds=10000$saltstringsaltstring") == (
            "$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v."
        )

    def test_an_unknown_scheme_is_never_proven(self) -> None:
        assert sha_crypt("admin@123", "$1$abcdefgh$") is None
        assert not junos_same_secret("$1$a$b", "$1$c$d", ("admin@123",))

    def test_the_same_password_resalted_on_the_device_is_not_drift(self) -> None:
        """Captured: the admin hash set by hand to `openssl passwd -6 -salt
        resalted 'admin@123'` -- same password, new salt."""
        assert normalise_junos(_fixture("junos_resalted_same_password.diff")) == []

    def test_proof_needs_the_password(self) -> None:
        """With no known password nothing is proven, so the same capture differs.
        Fail noisy: an unexplained hash is a changed one."""
        result = normalise_junos(_fixture("junos_resalted_same_password.diff"), passwords=())
        assert len(result) == 2

    def test_an_unpaired_secret_is_never_suppressed(self) -> None:
        raw = f'[edit system root-authentication]\n+   encrypted-password "{self.LAB_HASH}"; ## SECRET-DATA\n'
        assert normalise_junos(raw) == [f'+   encrypted-password "{self.LAB_HASH}"; ## SECRET-DATA']


class TestFailNoisy:
    """An unrecognised line must count as a difference (FR-011a)."""

    def test_an_unknown_srl_line_is_not_suppressed(self) -> None:
        raw = "Warning: something unforeseen\nAll changes have been discarded. Leaving candidate mode.\n"
        assert normalise_srl(raw) == ["Warning: something unforeseen"]

    def test_a_commit_line_in_a_comparison_counts(self) -> None:
        """Only the discard line is status. A comparison never commits, so anything
        saying it did is unrecognised -- and counts, rather than being explained away."""
        assert normalise_srl("Commit confirmed (automatic rollback in 2 minutes)\n") == [
            "Commit confirmed (automatic rollback in 2 minutes)"
        ]

    def test_an_unknown_junos_line_is_not_suppressed(self) -> None:
        raw = "[edit security]\n+   some-new-stanza {\n"
        assert normalise_junos(raw) == ["+   some-new-stanza {"]

    def test_a_deletion_counts_as_a_difference(self) -> None:
        """Drift that removes configuration matters as much as drift that adds."""
        assert normalise_eos("--- system:/running-config\n-ip host gone 10.0.0.1\n") == ["-ip host gone 10.0.0.1"]

    def test_an_unknown_family_raises_rather_than_guessing(self) -> None:
        with pytest.raises(ValueError, match="no normaliser"):
            normalise("IOS-XR Configuration", "anything")


class TestSuppressionReasons:
    """Each suppression is here for a stated reason. These pin the reasons."""

    def test_junos_commit_stamps_are_suppressed_only_where_measured(self) -> None:
        """`version` at `[edit]` and `uid` under a login, as deletions only.
        The same text anywhere else, or as an addition, is a difference."""
        assert normalise_junos("[edit]\n- version 22.3R1.11;\n") == []
        assert normalise_junos("[edit system login user admin]\n-    uid 2000;\n") == []
        assert normalise_junos("[edit system login user admin]\n+    uid 2001;\n")
        assert normalise_junos("[edit system]\n-   version 22.3R1.11;\n")
        assert normalise_junos("[edit interfaces]\n-    uid 2000;\n")

    def test_junos_zone_pair_reordering_is_suppressed(self) -> None:
        raw = "[edit security policies]\n!    from-zone wan to-zone branch { ... }\n"
        assert normalise_junos(raw) == []

    def test_an_fxp0_deletion_is_never_suppressed_because_it_signals_a_regression(self) -> None:
        """This assertion is the inverse of what it used to be, deliberately.

        `load replace` on the whole `interfaces` hierarchy deleted the vSRX's
        management interface on every push; vrnetlab restored it as root, so an
        in-sync firewall reported `- fxp0 {...}` forever and this module
        suppressed it. fxp0 is modelled now, and under `load override` an fxp0
        deletion means the artifact lost it -- which the push's lifeline refuses.
        That must be reported, not hidden.
        """
        raw = (
            "[edit interfaces]\n"
            "-   fxp0 {\n"
            "-       unit 0 {\n"
            "-           family inet {\n"
            "-               address 10.0.0.15/24;\n"
            "-           }\n"
            "-       }\n"
            "-   }\n"
        )
        assert normalise_junos(raw), "an fxp0 deletion must surface as a difference"

    def test_a_different_interface_is_not_suppressed(self) -> None:
        """The fxp0 rule must not become "ignore interface changes"."""
        raw = "[edit interfaces]\n-   ge-0/0/1 {\n-       unit 0;\n-   }\n"
        assert normalise_junos(raw)
