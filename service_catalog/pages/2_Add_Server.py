"""Infrahub Service Catalog - Request a Server.

Creates ONE object: a `ServiceServerPlacement`. The machine, its interfaces and
its cabling are built by `generate-server-placement` and `generate-server-cabling`
when the branch merges.

**This page used to create the `ComputePhysicalServer` itself.** Two of the
fields below are mandatory for reasons that are invisible if you get them wrong:

* The **rack** is what the machine gets cabled to — `generate-server-cabling`
  finds the leaf switches in the server's own rack. A machine with no rack is
  cabled to nothing and every step reports success.
* The **object template** is what gives the machine its interfaces, and cabling
  cables interfaces. Without one the cabling generator logs "has no interfaces"
  and returns, which reads exactly like a broken generator.
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

ROLES = {
    "compute": "Compute — general workload host",
    "storage": "Storage — storage node",
    "k8s_node": "Kubernetes node — joins the cluster's BGP peering",
}


def _rack_label(rack: dict) -> str:
    """A rack, and the switches a machine in it would be cabled to."""
    devices = [d["node"]["name"]["value"] for d in rack.get("devices", {}).get("edges", []) if d.get("node")]
    leaves = [d for d in devices if "leaf" in d or "spine" in d]
    name = rack["name"]["value"]
    return f"{name} — cabled to {', '.join(leaves)}" if leaves else f"{name} (no switches; nothing to cable to)"


def main() -> None:
    """Render the Request Server page."""
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL,
    )

    st.title("Request a Server")
    st.markdown(
        "Ask for a machine in a rack. It is **created and cabled to that rack's leaves** for you; "
        "a proposed change is opened for review."
    )

    try:
        racks = client.get_racks()
        templates = client.get_object_templates()
        tenants = client.get_organization_tenants()
        organizations = client.get_organizations()
    except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError) as e:
        display_error("Unable to fetch data from Infrahub", str(e))
        st.stop()
        return

    missing = [
        label
        for label, values in (
            ("racks", racks),
            ("object templates", templates),
            ("organizations", organizations),
        )
        if not values
    ]
    if missing:
        st.warning(f"Cannot request a server yet — Infrahub has no {', '.join(missing)}.")
        st.stop()
        return

    with st.form("request_server_form"):
        st.subheader("The machine")

        col1, col2 = st.columns(2)
        with col1:
            hostname = st.text_input("Hostname", placeholder="e.g. host-c")
            role = st.selectbox("Role", options=list(ROLES.keys()), format_func=lambda x: ROLES[x])
            description = st.text_input("Description", placeholder="e.g. additional workload capacity")

        with col2:
            tenant_options = {t["id"]: t["name"]["value"] for t in tenants}
            tenant_id = (
                st.selectbox(
                    "Tenant (optional)",
                    options=[None, *tenant_options.keys()],
                    format_func=lambda x: "— shared infrastructure —" if x is None else tenant_options[x],
                )
                if tenants
                else None
            )
            owner_options = {o["id"]: o["display_label"] for o in organizations}
            owner_id = st.selectbox(
                "Requested by", options=list(owner_options.keys()), format_func=lambda x: owner_options[x]
            )

        st.subheader("Where it goes, and what it is")
        st.caption(
            "The rack decides what the machine is cabled to. The template decides what interfaces it "
            "has — and cabling cables interfaces, so a machine without one is connected to nothing."
        )
        col3, col4 = st.columns(2)
        with col3:
            rack_options = {r["id"]: _rack_label(r) for r in racks}
            rack_id = st.selectbox("Rack", options=list(rack_options.keys()), format_func=lambda x: rack_options[x])
        with col4:
            template_options = {t["id"]: t["template_name"]["value"] for t in templates}
            template_id = st.selectbox(
                "Object Template",
                options=list(template_options.keys()),
                format_func=lambda x: template_options[x],
            )

        submitted = st.form_submit_button("Request Server", type="primary")

    if submitted:
        if not hostname:
            st.error("Hostname is required — it is also the machine's ContainerLab node name.")
            return

        branch_name = f"add-server-{hostname.lower().replace(' ', '-')}"
        relationships: dict[str, str | list[str]] = {
            "owner": owner_id,
            "rack": rack_id,
            "template": template_id,
        }
        if tenant_id:
            relationships["tenant"] = tenant_id

        try:
            with st.spinner(f"Creating branch '{branch_name}'..."):
                client.create_branch(branch_name)
            st.info(f"Branch `{branch_name}` created")

            with st.spinner("Requesting the machine..."):
                client.create_service(
                    kind="ServiceServerPlacement",
                    branch=branch_name,
                    group="service_server_placements",
                    fields={
                        "name": f"place-{hostname}",
                        "description": description or f"{hostname} in {rack_options[rack_id].split(' — ')[0]}",
                        "hostname": hostname,
                        "server_role": role,
                    },
                    relationships=relationships,
                )
            st.info("Machine requested")

            with st.spinner("Creating proposed change..."):
                pc = client.create_proposed_change(
                    branch=branch_name,
                    name=f"Request server: {hostname}",
                    description=(
                        f"Place {hostname} ({role}) in {rack_options[rack_id].split(' — ')[0]} using template "
                        f"{template_options[template_id]}. The machine and its cabling are built on merge."
                    ),
                )

            display_success(f"Server '{hostname}' requested.")
            st.link_button("View Proposed Change", client.get_proposed_change_url(pc["id"]))

        except InfrahubConnectionError as e:
            display_error("Connection error", str(e))
        except InfrahubGraphQLError as e:
            display_error("GraphQL error", str(e))
        except InfrahubAPIError as e:
            display_error("API error", str(e))


main()
