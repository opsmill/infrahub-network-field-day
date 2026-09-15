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

The defect these tests exist to prevent: FRR and Junos report a non-empty
difference against an artifact the device already matches, so a reconciler
reading raw output replaces the configuration of every FRR router and the
firewall on every cycle, forever, logging success throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from solution_arista_avd.deployment.normalise import (
    normalise,
    normalise_eos,
    normalise_frr,
    normalise_junos,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deployment"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestInSyncDevicesAreSilent:
    """The assertion the whole feature rests on."""

    def test_eos_in_sync_normalises_to_empty(self) -> None:
        assert normalise_eos(_fixture("eos_clean.diff")) == []

    def test_frr_in_sync_normalises_to_empty(self) -> None:
        """The raw output is NOT empty -- that is the point.

        An in-sync FRR router reports `neighbor <addr> activate`,
        `service integrated-vtysh-config` and `line vty` every single time.
        """
        raw = _fixture("frr_clean.txt")
        assert "Lines To Add" in raw, "fixture should carry the real non-empty output"
        assert normalise_frr(raw) == []

    def test_frr_provider_edge_with_vrfs_normalises_to_empty(self) -> None:
        """A provider edge carries `router bgp <asn> vrf <NAME>` per customer.

        Captured from isp-pe1. The first version of the scaffold rule matched
        only the bare `router bgp <asn>`, so each VRF wrapper survived its
        suppressed contents and the device reported a difference on every cycle
        forever. The live dry run surfaced it because an unrecognised line counts
        as a difference -- which is the whole point of the fail-noisy rule.
        """
        assert normalise_frr(_fixture("frr_vrf_clean.txt")) == []

    def test_junos_in_sync_normalises_to_empty(self) -> None:
        """An in-sync firewall reports 55 changed lines. Also the point."""
        raw = _fixture("junos_clean.diff")
        assert len(raw.splitlines()) > 40, "fixture should carry the real non-empty output"
        assert normalise_junos(raw) == []


class TestRealChangesSurvive:
    """Without these, a normaliser that suppressed everything would pass."""

    def test_eos_control_line_survives(self) -> None:
        result = normalise_eos(_fixture("eos_control.diff"))
        assert result
        assert any("probe-marker" in line for line in result)

    def test_frr_control_line_survives(self) -> None:
        result = normalise_frr(_fixture("frr_control.txt"))
        assert result
        assert any("10.255.255.0/24" in line for line in result)

    def test_junos_control_line_survives(self) -> None:
        """The control injects a real static route, NOT a comment.

        A comment-based control passes trivially against a broken normaliser,
        because a comment is exactly what Junos does not round-trip and what the
        suppression rules are meant to drop. The first version of this fixture
        made that mistake and tested nothing.
        """
        result = normalise_junos(_fixture("junos_control.diff"))
        assert result
        assert any("10.255.255.0/24" in line for line in result)


class TestFailNoisy:
    """An unrecognised line must count as a difference (FR-011a)."""

    def test_an_unknown_frr_line_is_not_suppressed(self) -> None:
        raw = "Lines To Add\n============\nip route 192.0.2.0/24 Null0\n"
        assert normalise_frr(raw) == ["ip route 192.0.2.0/24 Null0"]

    def test_an_unknown_junos_line_is_not_suppressed(self) -> None:
        raw = "[edit security]\n+   some-new-stanza {\n"
        assert normalise_junos(raw) == ["+   some-new-stanza {"]

    def test_a_deletion_counts_as_a_difference(self) -> None:
        """Drift that removes configuration matters as much as drift that adds."""
        assert normalise_eos("--- system:/running-config\n-ip host gone 10.0.0.1\n") == ["-ip host gone 10.0.0.1"]

    def test_an_unknown_family_raises_rather_than_guessing(self) -> None:
        with pytest.raises(ValueError, match="no normaliser"):
            normalise("IOS-XR Configuration", "anything")


class TestExitStatusIsNeverConsulted:
    def test_frr_differences_are_found_despite_a_zero_exit(self) -> None:
        """`frr-reload.py --test` returns 0 whether or not the config matches.

        The control fixture was captured from a run that exited 0 and had a real
        difference. Nothing in this module may look at a return code.
        """
        assert normalise_frr(_fixture("frr_control.txt"))


class TestSuppressionReasons:
    """Each suppression is here for a stated reason. These pin the reasons."""

    def test_frr_neighbour_activate_is_suppressed(self) -> None:
        raw = "Lines To Add\n============\nrouter bgp 65030\n address-family ipv4 unicast\n  neighbor 10.0.0.1 activate\n exit\nexit\n"
        assert normalise_frr(raw) == []

    def test_frr_scaffolding_is_kept_when_something_real_is_inside_it(self) -> None:
        """Dropping an empty `router bgp` is right; dropping a populated one hides drift."""
        raw = (
            "Lines To Add\n============\nrouter bgp 65030\n address-family ipv4 unicast\n"
            "  neighbor 10.0.0.1 activate\n  redistribute static\n exit\nexit\n"
        )
        result = normalise_frr(raw)
        assert any("redistribute static" in line for line in result)
        assert any("router bgp" in line for line in result)

    def test_junos_zone_pair_reordering_is_suppressed(self) -> None:
        raw = "[edit security policies]\n!    from-zone wan to-zone branch { ... }\n"
        assert normalise_junos(raw) == []

    def test_an_fxp0_deletion_is_never_suppressed_because_it_signals_a_regression(self) -> None:
        """This assertion is the inverse of what it used to be, deliberately.

        `load replace` on the whole `interfaces` hierarchy deleted the vSRX's
        management interface on every push; vrnetlab restored it as root, so an
        in-sync firewall reported `- fxp0 {...}` forever and this module
        suppressed it. `_junos_replace_tagged` now tags each modelled interface
        instead of the stanza, so the candidate leaves fxp0 alone and the diff
        no longer mentions it.

        If it ever appears again, the tagging has regressed and the firewall's
        management path is being deleted on every push. That must be reported,
        not hidden.
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
