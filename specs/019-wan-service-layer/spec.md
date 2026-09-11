# Objects Specification: The WAN Service Layer

> **Workflow type**: Infrahub Objects (instance data)
> **Skill**: Use the `infrahub-managing-objects` skill to implement this specification.

**Feature Branch**: `019-wan-service-layer`
**Created**: 2026-09-11
**Status**: Complete
**Input**: "Please tackle the outstanding items" — the WAN half of the service layer, which had nothing.

## Why this cycle exists

Cycle 010 modelled the WAN's technical layer — circuits, sites, internet peering, VRFs,
firewall zones — and built schema for three WAN service kinds on top: `ServiceL3vpn`,
`ServiceInternetAccess`, `ServiceTenantCloud`. **None of them had a single object.** Four of
the six service kinds were empty schema.

The original request was to "contain all of the information that is in the lab: the ISP, the
branches, and the firewall". The technical layer did that; the service layer only did it for
Kubernetes.

## The source, and the asymmetry

`../lab/wan/tenants.yml` is the authority. Two tenants:

| Tenant | PE VRF | Internet | DC VRF | Zone | Subnet |
| --- | --- | --- | --- | --- | --- |
| acme | `CUST_ACME` | **true** | `TENANT_ACME` | `acme-cloud` | `10.220.10.0/24` |
| globex | `CUST_GLOBEX` | **false** | `TENANT_GLOBEX` | `globex-cloud` | `10.220.20.0/24` |

**There is exactly one internet-access service, and that is the point.** A tenant having a WAN
does not mean it has a way out to the internet. Seeding one per tenant would be symmetrical
and would lose the only interesting difference between the pair — so a test asserts the count
against the lab file rather than against a constant.

## Requirements

- **FR-001**: One `ServiceL3vpn` per lab tenant, carrying its PE-side VRF, its circuits and its DC service prefix
- **FR-002**: One `ServiceInternetAccess` **only** for tenants whose lab entry sets `internet: true`
- **FR-003**: One `ServiceTenantCloud` per tenant, carrying its DC VRF, firewall zone, subnet and VLAN
- **FR-004**: The PE-side VRFs (`CUST_*`) MUST be created — cycle 010 seeded only the DC-side `TENANT_*` VRFs
- **FR-005**: PE-side and DC-side VRFs MUST stay distinct; collapsing them would silently join two tenants' routing
- **FR-006**: Every service MUST name an owner and a status
- **FR-007**: Service names MUST be unique across kinds, which `ServiceGeneric` constrains (010's FR-070)
- **FR-008**: The object file MUST load idempotently

## Success Criteria

- **SC-001**: Five services load — two L3VPNs, one internet access, two tenant clouds
- **SC-002**: Every relationship resolves: tenants, VRFs, circuits, prefixes, zones, VLANs, the peering
- **SC-003**: Exactly one internet-access service exists, matching the lab's `internet` flags
- **SC-004**: A second load produces no error and no duplicate
- **SC-005**: The transcription matches `../lab/wan/tenants.yml` field for field
- **SC-006**: All unit tests and the repository's linters pass

## Out of Scope

- Rendering FRR configuration for the ISP, CE and branch routers from these services. That is a large, independent cycle — these services are its input.
- `ServiceAppAccess`, the one remaining service kind with no objects. It models an approval workflow and has no oracle.
- Generators beneath the WAN services. Nothing yet derives technical objects from them.
- Any schema change beyond the two PE VRFs, which are object data.
