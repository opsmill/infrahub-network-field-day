"""Infrahub Service Catalog - Onboard a Tenant.

Creates ONE object: a `ServiceTenantOnboarding`. The EVPN tenant and its VNI
base are built by `generate-tenant-onboarding` when the branch merges.

**This page used to create the `EvpnTenant` itself**, and asked the requester for
a MAC-VRF VNI base. That is the single worst question to put on this form: every
tenant's L2VLAN VNIs are allocated upward from its base, so two tenants with
close bases share VNIs and the fabric bridges them together — with nothing
erroring anywhere. The generator derives the next free base instead.
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
    """Render the Onboard Tenant page."""
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL,
    )

    st.title("Onboard a Tenant")
    st.markdown(
        "Give an organization a presence on a fabric. The EVPN tenant and its **VNI range are "
        "derived for you**; a proposed change is opened for review."
    )

    try:
        organizations = client.get_organizations()
        tenants = client.get_organization_tenants()
        fabrics = client.get_fabrics()
    except (InfrahubConnectionError, InfrahubGraphQLError, InfrahubAPIError) as e:
        display_error("Unable to fetch data from Infrahub", str(e))
        st.stop()
        return

    missing = [
        label
        for label, values in (("organizations", organizations), ("tenants", tenants), ("fabrics", fabrics))
        if not values
    ]
    if missing:
        st.warning(f"Cannot onboard a tenant yet — Infrahub has no {', '.join(missing)}.")
        st.stop()
        return

    with st.form("onboard_tenant_form"):
        st.subheader("Who, and where")

        col1, col2 = st.columns(2)
        with col1:
            tenant_options = {t["id"]: t["name"]["value"] for t in tenants}
            tenant_id = st.selectbox(
                "Organization to onboard",
                options=list(tenant_options.keys()),
                format_func=lambda x: tenant_options[x],
            )
            description = st.text_input("Description", placeholder="e.g. platform team workloads")

        with col2:
            fabric_options = {f["id"]: f["name"]["value"] for f in fabrics}
            fabric_id = st.selectbox(
                "Fabric", options=list(fabric_options.keys()), format_func=lambda x: fabric_options[x]
            )
            owner_options = {o["id"]: o["display_label"] for o in organizations}
            owner_id = st.selectbox(
                "Requested by", options=list(owner_options.keys()), format_func=lambda x: owner_options[x]
            )

        st.caption(
            "The EVPN tenant is named `TENANT_<ORGANIZATION>` and its VNI base is the next free "
            "multiple of 1000. Both are derived on merge — there is deliberately no field for them here."
        )

        submitted = st.form_submit_button("Onboard Tenant", type="primary")

    if submitted:
        organization = tenant_options[tenant_id]
        branch_name = f"onboard-{organization.lower().replace(' ', '-')}"

        try:
            with st.spinner(f"Creating branch '{branch_name}'..."):
                client.create_branch(branch_name)
            st.info(f"Branch `{branch_name}` created")

            with st.spinner("Requesting the onboarding..."):
                client.create_service(
                    kind="ServiceTenantOnboarding",
                    branch=branch_name,
                    group="service_tenant_onboardings",
                    fields={
                        "name": f"onboard-{organization}",
                        "description": description or f"{organization} on {fabric_options[fabric_id]}",
                    },
                    relationships={"owner": owner_id, "organization": tenant_id, "fabric": fabric_id},
                )
            st.info("Onboarding requested")

            with st.spinner("Creating proposed change..."):
                pc = client.create_proposed_change(
                    branch=branch_name,
                    name=f"Onboard tenant: {organization}",
                    description=(
                        f"Give {organization} a presence on {fabric_options[fabric_id]}. The EVPN tenant "
                        "and its VNI base are derived by generate-tenant-onboarding on merge."
                    ),
                )

            display_success(f"Tenant '{organization}' onboarding requested.")
            st.link_button("View Proposed Change", client.get_proposed_change_url(pc["id"]))

        except InfrahubConnectionError as e:
            display_error("Connection error", str(e))
        except InfrahubGraphQLError as e:
            display_error("GraphQL error", str(e))
        except InfrahubAPIError as e:
            display_error("API error", str(e))


main()
