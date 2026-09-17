"""Infrahub Service Catalog - Request a Network Segment.

Creates ONE object: a `ServiceNetworkSegment`. The subnet, the VLAN and the SVI
are built by `generate-network-segment` when the branch merges.

**This page used to create those three itself**, and the schema header of
`schemas/service/network_services.yml` names it as the inversion the service
layer exists to fix. Three things were wrong with that, beyond the missing
record of who asked:

* It demanded a VLAN id, a gateway CIDR and a VRF VNI from the requester -- the
  person least able to know which of those are free.
* Leaving the VRF blank produced a VLAN and no SVI, warned "SVI will need a VRF
  assigned manually", and reported success.
* Nothing set `avd_tags`, so every SVI it did create matched no node-group
  filter and rendered on **no switch at all**, silently.

Workflow: create branch -> create the service -> open a proposed change. No AVD
run here: the generator writes the technical objects on merge, and the fabric
picks them up on the next `invoke avd`.
"""

import streamlit as st  # type: ignore[import-untyped]
from utils import (
    INFRAHUB_ADDRESS,
    INFRAHUB_API_TOKEN,
    INFRAHUB_UI_URL,
    InfrahubClient,
    display_error,
    display_success,
)
from utils.api import InfrahubAPIError, InfrahubConnectionError, InfrahubGraphQLError

if "infrahub_url" not in st.session_state:
    st.session_state.infrahub_url = INFRAHUB_ADDRESS


def _tag_label(tag: dict) -> str:
    """A tag, and the leaves it actually selects.

    The names alone (`k8s`, `app`, `border`) say nothing about where a segment
    will land, and landing nowhere is this form's most likely mistake.
    """
    racks = [r["node"]["name"]["value"] for r in tag.get("racks", {}).get("edges", []) if r.get("node")]
    name = tag["name"]["value"]
    return f"{name} — {', '.join(racks)}" if racks else f"{name} (selects no racks)"


def main() -> None:
    """Render the Request Network Segment page."""
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL,
    )

    st.title("Request a Network Segment")
    st.markdown(
        "Ask for a tenant network. The subnet and VLAN id are **allocated for you**; "
        "a proposed change is opened for review, and the segment is built when it merges."
    )

    try:
        tenants = client.get_organization_tenants()
        vrfs = client.get_vrfs()
        fabrics = client.get_fabrics()
        avd_tags = client.get_avd_tags()
        organizations = client.get_organizations()
    except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError) as e:
        display_error("Unable to fetch data from Infrahub", str(e))
        st.stop()
        return

    missing = [
        label
        for label, values in (
            ("tenants", tenants),
            ("VRFs", vrfs),
            ("fabrics", fabrics),
            ("AVD tags", avd_tags),
            ("organizations", organizations),
        )
        if not values
    ]
    if missing:
        # Named rather than generic: "no data" sends the reader to the wrong file.
        st.warning(f"Cannot request a segment yet — Infrahub has no {', '.join(missing)}.")
        st.stop()
        return

    with st.form("request_segment_form"):
        st.subheader("What the segment is for")

        col1, col2 = st.columns(2)

        with col1:
            segment_name = st.text_input("Segment Name", placeholder="e.g. PLATFORM_HOSTS")
            description = st.text_input("Description", placeholder="e.g. platform team application hosts")

            tenant_options = {t["id"]: t["name"]["value"] for t in tenants}
            tenant_id = st.selectbox(
                "Tenant", options=list(tenant_options.keys()), format_func=lambda x: tenant_options[x]
            )

            owner_options = {o["id"]: o["display_label"] for o in organizations}
            owner_id = st.selectbox(
                "Requested by", options=list(owner_options.keys()), format_func=lambda x: owner_options[x]
            )

        with col2:
            # SELECTED, never created. A segment joins a routing domain that
            # already exists and is shared; one VRF per segment would give every
            # segment its own routing table, which is the opposite of what a
            # tenant network is for.
            vrf_options = {v["id"]: v["name"]["value"] for v in vrfs}
            vrf_id = st.selectbox(
                "VRF (must already exist)",
                options=list(vrf_options.keys()),
                format_func=lambda x: vrf_options[x],
            )

            fabric_options = {f["id"]: f["name"]["value"] for f in fabrics}
            fabric_id = st.selectbox(
                "Fabric", options=list(fabric_options.keys()), format_func=lambda x: fabric_options[x]
            )

            prefix_length = st.number_input(
                "Subnet size (prefix length)", min_value=16, max_value=30, value=24
            )

        st.subheader("Where it lands")
        st.caption(
            "AVD puts the gateway only on leaves whose node group matches one of these tags. "
            "**A segment with no tag renders on no switch** — the configuration is produced, "
            "reports Ready, and simply lacks the interface."
        )
        tag_options = {t["id"]: _tag_label(t) for t in avd_tags}
        avd_tag_ids = st.multiselect(
            "AVD Tags", options=list(tag_options.keys()), format_func=lambda x: tag_options[x]
        )

        with st.expander("Advanced — normally leave these alone"):
            st.caption(
                "Leaving the VLAN id empty is the normal case: the generator takes the next free "
                "id from the segment pool. Name one only when adopting an id that is already in use."
            )
            name_vlan = st.checkbox("Name a specific VLAN ID")
            vlan_id = st.number_input("VLAN ID", min_value=2, max_value=4093, value=500, disabled=not name_vlan)

        submitted = st.form_submit_button("Request Segment", type="primary")

    if submitted:
        if not segment_name:
            st.error("Segment Name is required.")
            return
        if not avd_tag_ids:
            # Refused rather than defaulted. There is no tag meaning "everywhere",
            # so an empty list is a segment that renders nowhere.
            st.error(
                "At least one AVD tag is required — without one the segment would render on no switch."
            )
            return

        branch_name = f"add-segment-{segment_name.lower().replace(' ', '-').replace('_', '-')}"

        try:
            with st.spinner(f"Creating branch '{branch_name}'..."):
                client.create_branch(branch_name)
            st.info(f"Branch `{branch_name}` created")

            with st.spinner("Requesting the segment..."):
                client.create_network_segment(
                    branch=branch_name,
                    name=segment_name,
                    description=description or f"{segment_name} segment",
                    owner_id=owner_id,
                    tenant_id=tenant_id,
                    vrf_id=vrf_id,
                    fabric_id=fabric_id,
                    avd_tag_ids=avd_tag_ids,
                    prefix_length=int(prefix_length),
                    vlan_id=int(vlan_id) if name_vlan else None,
                )
            st.info("Segment requested")

            with st.spinner("Creating proposed change..."):
                pc = client.create_proposed_change(
                    branch=branch_name,
                    name=f"Request network segment: {segment_name}",
                    description=(
                        f"Request segment '{segment_name}' for tenant {tenant_options[tenant_id]} "
                        f"in VRF {vrf_options[vrf_id]} on fabric {fabric_options[fabric_id]}, "
                        f"/{int(prefix_length)}, tags {', '.join(tag_options[t].split(' — ')[0] for t in avd_tag_ids)}. "
                        "The subnet, VLAN and SVI are built by generate-network-segment on merge."
                    ),
                )

            pc_url = client.get_proposed_change_url(pc["id"])
            display_success(f"Segment '{segment_name}' requested.")
            st.markdown(
                "The subnet and VLAN id are allocated when this merges, and the gateway reaches "
                "the switches on the next `invoke avd`."
            )
            st.link_button("View Proposed Change", pc_url)

        except InfrahubConnectionError as e:
            display_error("Connection error", str(e))
        except InfrahubGraphQLError as e:
            display_error("GraphQL error", str(e))
        except InfrahubAPIError as e:
            display_error("API error", str(e))


main()
