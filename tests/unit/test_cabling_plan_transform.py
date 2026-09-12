"""The cabling-plan transform's GraphQL query, pinned at the fragment level.

WHY THIS EXISTS. The transform rendered a CSV header and nothing else, on a
fabric with seven cables in the graph, and every gate in the repository passed:
the artifact generated, its status was Ready, and no test looked at its
contents.

The cause was a polymorphic relationship queried with one concrete fragment.
`InterfacePhysical.device` peers the device GENERIC, and every cable in this lab
runs `DcimDevice` <-> `ComputePhysicalServer` -- a leaf to a server. The query
spread only `... on DcimDevice`, so the server end resolved to an empty object,
the transform's `if src_dev_name and dst_dev_name` guard dropped the row, and
all seven disappeared silently.

That is the same failure mode this repository has recorded three times before,
in cycles 022, 023 and 024. It is pinned here at the level it actually breaks:
the fragments in the query text, not the output of a particular fixture.
"""

from __future__ import annotations

import inspect
import re

from transforms.cabling_plan import CablingPlan

QUERY = re.search(
    r'query = """(.*?)"""',
    inspect.getsource(CablingPlan._fetch_links_with_details),
    re.DOTALL,
).group(1)


def test_the_device_name_is_read_from_the_generic() -> None:
    """`name` must come from the generic, or non-DcimDevice ends vanish.

    A server is not a `DcimDevice`. Neither is the perimeter firewall, which is
    a `SecurityFirewall` -- so a future cable to it would be dropped by the same
    bug.
    """
    assert "... on DcimGenericDevice {" in QUERY, (
        "device `name` must be spread on DcimGenericDevice; a concrete-kind-only "
        "fragment silently drops every endpoint of another kind"
    )


def test_the_rack_stays_on_the_concrete_kind() -> None:
    """`rack` is a DcimDevice field. A server has none, and that is fine --
    the transform emits an empty rack column rather than dropping the row."""
    assert "... on DcimDevice {" in QUERY
    assert "rack { node { name { value } } }" in QUERY


def test_both_interface_fragments_carry_the_generic() -> None:
    """The query spreads two interface kinds, and both reach `device`.

    Fixing one and not the other would leave half the cables invisible, which
    is harder to notice than none of them.
    """
    assert QUERY.count("... on DcimGenericDevice {") == 2, (
        "both the InterfacePhysical and DcimInterface fragments must read the device name from the generic"
    )


def test_a_row_needs_both_device_names() -> None:
    """The guard that turned a query bug into silence.

    Kept deliberately -- a cable with one unresolvable end is not a cabling
    row -- but it is why the failure was invisible, so the test above exists to
    make the query correct rather than to loosen this.
    """
    source = inspect.getsource(CablingPlan._fetch_links_with_details)
    assert "if src_dev_name and dst_dev_name:" in source
