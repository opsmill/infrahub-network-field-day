"""Infrahub Service Catalog - Deploy an Application.

Creates ONE object: a `ServiceFabricApp`. Its namespace, network policy and
LoadBalancer VIP block are delivered into the cluster by Crossplane, through the
`Crossplane FabricApp` artifact, once the branch merges.

**There is no VIP block field**, and that is the point. `generate-fabric-app`
allocates one from the cluster's pool when the application is exposed. Before
that generator existed, every exposed application needed a block chosen by hand
out of `10.112.240.0/24` with nothing preventing two of them from choosing the
same addresses — and `crossplane_fabric_app.py` *raises* on an exposed
application with no block, so getting it wrong failed the render rather than
degrading.

The policy switches default the way the XRD does, because a manifest that denies
what the live one permits is a difference nobody sees until the workload breaks.
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
    """Render the Deploy Application page."""
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL,
    )

    st.title("Deploy an Application")
    st.markdown(
        "Ask for a namespace on the cluster, with its network policy and — if it is exposed — "
        "a **LoadBalancer VIP block allocated for you**."
    )

    try:
        clusters = client.get_clusters()
        vrfs = client.get_vrfs()
        organizations = client.get_organizations()
    except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError) as e:
        display_error("Unable to fetch data from Infrahub", str(e))
        st.stop()
        return

    missing = [
        label for label, values in (("clusters", clusters), ("VRFs", vrfs), ("organizations", organizations)) if not values
    ]
    if missing:
        st.warning(f"Cannot deploy an application yet — Infrahub has no {', '.join(missing)}.")
        st.stop()
        return

    with st.form("deploy_app_form"):
        st.subheader("The application")

        col1, col2 = st.columns(2)
        with col1:
            app_name = st.text_input("Application name", placeholder="e.g. nfd41-metrics")
            namespace_name = st.text_input("Namespace", placeholder="defaults to the application name")
            description = st.text_input("Description", placeholder="e.g. Prometheus and Grafana")

        with col2:
            cluster_options = {c["id"]: c["name"]["value"] for c in clusters}
            cluster_id = st.selectbox(
                "Cluster", options=list(cluster_options.keys()), format_func=lambda x: cluster_options[x]
            )
            vrf_options = {v["id"]: v["name"]["value"] for v in vrfs}
            vrf_id = st.selectbox(
                "Fabric tenant VRF", options=list(vrf_options.keys()), format_func=lambda x: vrf_options[x]
            )
            owner_options = {o["id"]: o["display_label"] for o in organizations}
            owner_id = st.selectbox(
                "Requested by", options=list(owner_options.keys()), format_func=lambda x: owner_options[x]
            )

        st.subheader("Exposure")
        exposed = st.checkbox("Expose this application outside the cluster", value=False)
        vip_block_size = st.number_input(
            "VIP block size (prefix length)",
            min_value=24,
            max_value=30,
            value=28,
            disabled=not exposed,
            help="The block itself is allocated on merge; you are choosing how many addresses it holds",
        )
        st.caption(
            "An unexposed application gets no pool, no VIP and no advertisement — and access to it "
            "cannot be granted, because there is nothing to reach."
        )

        st.subheader("Network policy")
        st.caption("These default the way the cluster's XRD does. Changing them changes what the workload can do.")
        col3, col4 = st.columns(2)
        with col3:
            default_deny = st.checkbox("Default deny", value=True)
            allow_dns = st.checkbox("Allow DNS", value=True)
            allow_intra = st.checkbox(
                "Allow intra-namespace",
                value=True,
                help="Default-deny denies egress too, so without this a chart's own components cannot reach each other",
            )
        with col4:
            allow_api = st.checkbox(
                "Allow egress to the API server",
                value=False,
                help="Needed by any chart carrying an operator, controller or webhook",
            )
            allow_internet = st.checkbox("Allow egress to the internet", value=False)

        submitted = st.form_submit_button("Deploy Application", type="primary")

    if submitted:
        if not app_name:
            st.error("Application name is required.")
            return

        branch_name = f"deploy-{app_name.lower().replace(' ', '-')}"
        fields: dict[str, object] = {
            "name": app_name,
            "description": description or f"{app_name} on {cluster_options[cluster_id]}",
            "namespace_name": namespace_name or app_name,
            "exposed": exposed,
            "policy_default_deny": default_deny,
            "policy_allow_dns": allow_dns,
            "policy_allow_intra_namespace": allow_intra,
            "policy_allow_egress_api_server": allow_api,
            "policy_allow_egress_internet": allow_internet,
        }
        if exposed:
            fields["vip_block_size"] = int(vip_block_size)

        try:
            with st.spinner(f"Creating branch '{branch_name}'..."):
                client.create_branch(branch_name)
            st.info(f"Branch `{branch_name}` created")

            with st.spinner("Requesting the application..."):
                client.create_service(
                    kind="ServiceFabricApp",
                    branch=branch_name,
                    group="service_fabric_apps",
                    fields=fields,
                    relationships={"owner": owner_id, "cluster": cluster_id, "vrf": vrf_id},
                )
            st.info("Application requested")

            with st.spinner("Creating proposed change..."):
                pc = client.create_proposed_change(
                    branch=branch_name,
                    name=f"Deploy application: {app_name}",
                    description=(
                        f"Namespace {namespace_name or app_name} on {cluster_options[cluster_id]}, "
                        f"VRF {vrf_options[vrf_id]}, "
                        + (
                            f"exposed with a /{int(vip_block_size)} VIP block allocated on merge."
                            if exposed
                            else "not exposed."
                        )
                    ),
                )

            display_success(f"Application '{app_name}' requested.")
            if exposed:
                st.markdown(
                    "The VIP block is allocated from the cluster's pool when this merges — "
                    "there was deliberately no field for it."
                )
            st.link_button("View Proposed Change", client.get_proposed_change_url(pc["id"]))

        except InfrahubConnectionError as e:
            display_error("Connection error", str(e))
        except InfrahubGraphQLError as e:
            display_error("GraphQL error", str(e))
        except InfrahubAPIError as e:
            display_error("API error", str(e))


main()
