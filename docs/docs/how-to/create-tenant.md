---
title: Create a tenant
description: Onboard a tenant onto a fabric, with an EVPN tenant and a MAC VRF VNI base derived for it.
audience: user
sidebar_position: 3
---

# Create a tenant

Puts a tenant onto a fabric. You request one `ServiceTenantOnboarding`; its generator, `generate-tenant-onboarding`, creates the `EvpnTenant` that is the fabric's view of the organization, and gives it a **MAC VRF VNI base**. The tenant's L2 VLAN VNIs are allocated upward from that base, so every segment gets a unique VNI without manual allocation.

Prerequisites:

- A running stack with seed data loaded ([Quick Start](../quick-start.md)).
- At least one provisioned fabric ([Provision Your First Fabric](../provision-first-fabric.md)).
- The `OrganizationTenant` you're adding must already exist.

## Open the service portal

From the branch desktop, open **`https://10.90.0.11:32001`** and sign in through Dex, for example as `alice@otternet.lab`. See [The service portal](../service-portal.md) for the self-signed certificate and the one-time Infrahub sign-in every portal user needs.

Open the catalogue and choose the **Tenant Onboarding (generated)** template. It's generated from the `ServiceTenantOnboarding` schema, so its fields are the kind's own attributes and relationships.

## Fill the form

Leave **What do you want to do?** on **Request a new service**. The fields come from `schemas/service/onboarding_services.yml` and the service generic:

| Field | Required | Notes |
|-------|:--------:|-------|
| **Name** | ✅ | The service's name, unique across every service kind. |
| **Owner** | ✅ | The organization ordering the onboarding. |
| **Organization** | ✅ | Who the tenant is. The EVPN tenant is the fabric's view of them. |
| **Fabric** | ✅ | The fabric the tenant is joining. |
| **Description** | | Optional. |

The EVPN tenant and the VNI base aren't on the form, because the generator creates and derives them.

## Submit

The template then:

1. **Creates a branch** named `implement_<name>`.
2. **Creates the `ServiceTenantOnboarding`** on that branch, in the `service_tenant_onboardings` group that `generate-tenant-onboarding` targets.
3. **Waits for the generators.** The `created` event rule in `triggers.yml` runs `generate-tenant-onboarding`, which creates the `EvpnTenant` with its derived VNI base.
4. **Opens a proposed change** from the branch into `main`.

When it finishes, the output links to the proposed change in Infrahub, the onboarding in the catalogue, and the onboarding in Infrahub.

## Review and merge

The tenant itself doesn't add device-level configuration (no VRFs or VLANs exist under it yet), so the re-rendered AVD artifacts may be identical to before. The tenant becomes useful once you add network segments for it (see [Add a Network Segment](./add-network-segment.md)).

Merge the proposed change to promote the tenant to `main`.

## How the VNI base is chosen

The base is derived, not taken from a pool. A number pool hands out consecutive integers, so two tenants would get bases one apart and their VNI ranges would overlap almost entirely — with no error anywhere, the fabric would bridge the two tenants together.

Instead, the generator takes the lowest free multiple of 1000 at or above `11000`. The lab's tenants sit at `11000`, `12000`, `13000`, and `15000`, so the next onboarding gets `14000`: the derivation fills gaps rather than only appending.

## Without the portal

An operator can make the same request in the Infrahub UI or with `infrahubctl`: create a branch, create a `ServiceTenantOnboarding` on it with the fields above as a member of the `service_tenant_onboardings` group, and open a proposed change. The `created` event rule runs the generator on the branch, exactly as it does for a portal request.

To withdraw a tenant, set the onboarding's **Status** to `decommissioning` and re-run the generator. It deletes the EVPN tenant, and refuses while VRFs still reference it.

## Source

- Service kind: [`schemas/service/onboarding_services.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/service/onboarding_services.yml).
- Generator: [`generators/generate_tenant_onboarding.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_tenant_onboarding.py).
- Request template generation: [`backstage/plugins/infrahub-backend/src/provider.ts`](https://github.com/opsmill/infrahub-arista-avd/blob/main/backstage/plugins/infrahub-backend/src/provider.ts).
