"""Infrahub Service Catalog - Request Application Access.

Creates ONE object: a `ServiceAppAccess`. The firewall address-book entry, the
service objects and the permit rule are built by `generate-app-access` on the
request's own branch, as soon as it is created.

**THE BRANCH IS THE GATE, and it is the only one.** The kind used to carry an
`approved` Boolean and the generator composed nothing while it was false; that
was a second gate in front of one the workflow already has, and two gates can
only disagree. The field is gone. A request reaches no device until its proposed
change is merged, and the reviewer sees the rule, the address-book entry and the
re-rendered firewall configuration in that change. Merging is the approval.

The form makes two mistakes hard, both of which `zone-advertisement` would
otherwise report only after the fact:

* An **unexposed application** cannot be reached however correct everything else
  is — it gets no pool, no VIP and no advertisement — so only exposed ones are
  offered.
* A **VIP outside the application's block** is permitted by the firewall and
  never routed, so the address list is filtered to the block.
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


def main() -> None:
    """Render the Request Access page."""
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL,
    )

    st.title("Request Application Access")
    st.markdown(
        "Ask to reach an application from a network outside the cluster. "
        "**The grant is built on its own branch as soon as it is requested** — the rule, "
        "the service objects and the address-book entry are in the proposed change, and "
        "merging it is the approval."
    )

    try:
        apps = [a for a in client.get_fabric_apps() if a["exposed"]["value"]]
        zones = client.get_security_zones()
        addresses = client.get_security_addresses()
        organizations = client.get_organizations()
    except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError) as e:
        display_error("Unable to fetch data from Infrahub", str(e))
        st.stop()
        return

    if not apps:
        st.warning(
            "No exposed applications. An unexposed application gets no VIP and no advertisement, "
            "so access to it cannot be granted."
        )
        st.stop()
        return

    missing = [
        label for label, values in (("zones", zones), ("address entries", addresses), ("organizations", organizations)) if not values
    ]
    if missing:
        st.warning(f"Cannot request access yet — Infrahub has no {', '.join(missing)}.")
        st.stop()
        return

    app_options = {a["id"]: a["name"]["value"] for a in apps}
    app_by_id = {a["id"]: a for a in apps}

    with st.form("request_access_form"):
        st.subheader("What you want to reach")

        col1, col2 = st.columns(2)
        with col1:
            application_id = st.selectbox(
                "Application", options=list(app_options.keys()), format_func=lambda x: app_options[x]
            )
            justification = st.text_area(
                "Justification",
                placeholder="Why this access is needed — the reviewer reads this",
                height=100,
            )
        with col2:
            zone_options = {z["id"]: z["name"]["value"] for z in zones}
            source_zone_id = st.selectbox(
                "Source zone", options=list(zone_options.keys()), format_func=lambda x: zone_options[x]
            )
            address_options = {a["id"]: a["display_label"] for a in addresses}
            source_address_id = st.selectbox(
                "Source network",
                options=list(address_options.keys()),
                format_func=lambda x: address_options[x],
                help="An existing address-book entry, so the rule reads like the hand-written ones beside it",
            )

        st.subheader("Where, and on which ports")
        block = (app_by_id[application_id].get("vip_block") or {}).get("node") or {}
        block_value = (block.get("prefix") or {}).get("value")
        st.caption(
            f"Only addresses inside {block_value} are offered: the cluster advertises nothing else, "
            "so a VIP outside the block is permitted by the firewall and never routed."
            if block_value
            else "This application has no VIP block yet; generate-fabric-app allocates one."
        )

        try:
            vips = client.get_ip_addresses(prefix=block_value) if block_value else []
        except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError):
            vips = []

        col3, col4 = st.columns(2)
        with col3:
            vip_options = {v["id"]: v["address"]["value"] for v in vips}
            destination_vip_id = (
                st.selectbox(
                    "Destination VIP",
                    options=list(vip_options.keys()),
                    format_func=lambda x: vip_options[x],
                )
                if vip_options
                else None
            )
            if not vip_options:
                st.error("No addresses exist inside this application's VIP block.")
        with col4:
            ports_text = st.text_input(
                "TCP ports",
                placeholder="e.g. 8080, 8443",
                help="Ports the application actually serves; a port it does not serve is permitted here and refused by the cluster",
            )

        requester = st.text_input("Requester", placeholder="your name or team")
        owner_options = {o["id"]: o["display_label"] for o in organizations}
        owner_id = st.selectbox(
            "Owning organization", options=list(owner_options.keys()), format_func=lambda x: owner_options[x]
        )

        submitted = st.form_submit_button("Submit Request", type="primary")

    if submitted:
        if not destination_vip_id:
            st.error("A destination VIP inside the application's block is required.")
            return
        try:
            ports = [int(p.strip()) for p in ports_text.split(",") if p.strip()]
        except ValueError:
            st.error("Ports must be numbers separated by commas.")
            return
        if not ports:
            # Empty is rejected rather than read as "all ports", which is the
            # same choice the lab's FirewallAccess CRD makes with minItems: 1.
            st.error("At least one port is required — an empty list is not read as 'all ports'.")
            return
        if not justification.strip():
            st.error("A justification is required; the reviewer has nothing to go on without one.")
            return

        app_name = app_options[application_id]
        grant_name = f"{zone_options[source_zone_id]}-to-{app_name}"
        branch_name = f"access-{grant_name.lower().replace(' ', '-')}"

        try:
            with st.spinner(f"Creating branch '{branch_name}'..."):
                client.create_branch(branch_name)
            st.info(f"Branch `{branch_name}` created")

            with st.spinner("Submitting the request..."):
                client.create_service(
                    kind="ServiceAppAccess",
                    branch=branch_name,
                    group="service_app_accesses",
                    fields={
                        "name": grant_name,
                        "description": f"{app_name} from {zone_options[source_zone_id]}",
                        "requester": requester or "unknown",
                        "justification": justification.strip(),
                        "ports": ports,
                    },
                    relationships={
                        "owner": owner_id,
                        "application": application_id,
                        "source_zone": source_zone_id,
                        "source_address": source_address_id,
                        "destination_vip": destination_vip_id,
                    },
                )
            st.info("Request submitted")

            with st.spinner("Creating proposed change..."):
                pc = client.create_proposed_change(
                    branch=branch_name,
                    name=f"Access request: {grant_name}",
                    description=(
                        f"Permit {address_options[source_address_id]} in zone "
                        f"{zone_options[source_zone_id]} to reach {app_name} at "
                        f"{vip_options[destination_vip_id]} on tcp/{', '.join(str(p) for p in ports)}.\n\n"
                        f"Justification: {justification.strip()}\n\n"
                        "The grant is built on this branch already: the rule, the service objects "
                        "and the address-book entry are in this change. Merging it is the approval."
                    ),
                )

            display_success(f"Access request '{grant_name}' submitted.")
            st.info(
                "The firewall rule, the service objects and the address-book entry are on this "
                "branch now. They reach the device when the proposed change is merged."
            )
            st.link_button("View Proposed Change", client.get_proposed_change_url(pc["id"]))

        except InfrahubConnectionError as e:
            display_error("Connection error", str(e))
        except InfrahubGraphQLError as e:
            display_error("GraphQL error", str(e))
        except InfrahubAPIError as e:
            display_error("API error", str(e))


main()
