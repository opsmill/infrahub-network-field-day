---
title: The service portal
---

# The service portal

Branch users request services through a Backstage portal in the tooling cluster.
It is the front door to everything the service layer models, and until now it was
documented nowhere — the narrative ran through a component the docs never named.

It reaches Infrahub over the API and writes **as the person signed in**, so a
request carries their name rather than a service account's.

## Getting to it

| | |
| --- | --- |
| Portal | `https://10.90.0.11:32001` |
| Identity | `http://10.90.0.11:32556/dex` |
| Lab users | `alice@otternet.lab`, `bob@otternet.lab` — password `password` |

HTTPS with a lab certificate, and that is not about privacy: the frontend
calls `crypto.randomUUID`, which a browser populates only in a secure context, so
over plain HTTP sign-in succeeds and the app then dies. `invoke tooling` signs
the certificate with a throwaway CA and installs that CA on the branch desktop,
so its Firefox shows no warning; other machines get a warning to click through.
It is two certificates rather than one self-signed one because Firefox refuses a
self-signed certificate marked as a CA when a server presents it
(`MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY`), and installs nothing else as
an authority. A Firefox already open when `invoke tooling` runs keeps warning
until it is restarted.

:::warning A user must sign in to Infrahub once before requesting anything
The portal attributes writes through the mutation's `context`, and Infrahub
provisions an account on first SSO login. Before that, a request fails with
`Unable to set context for account that doesn't exist` — **after** creating its
branch. `invoke tooling` provisions every Dex user; check with
`scripts/provision_portal_accounts.py --check`.
:::

## What is on offer

Most items are **generated**: the catalog provider reads the Infrahub schema and
emits one request template per service kind, so they cannot drift from the model.
Two are hand-written, because they do something the generated shape cannot.

### Exposed application, with access

One request, two service objects, one branch, one proposed change. It creates an
exposed `ServiceFabricApp` and the `ServiceAppAccess` that opens the way to it.

**The application is picked from the catalogue, not described.** The form asks
for **one entry from the application catalogue**, such as Who am I, plus what is
yours: a name, an owner, a source site, a
justification and a reference. It does not ask for a chart repository, chart name,
chart version, ports, block size, selector or values. Those are the platform
team's decision and live on the entry in Infrahub (`ServiceApplicationDefinition`).
The portal cannot override the chart or its values. Once the proposed change merges, the application can also be
reached by name, `<name>.int.otternet.lab`, from the branch machine; see [the DNS service](./developer-guide/dns-service.md). The template also fixes the
cluster (`otternet`) and the VRF (`K8S_PROD`); the requester is not asked for either. The namespace is optional; when left blank
it is the application name.

The picker offers only entries that are **requestable and active**; the lab's own
infrastructure applications are not requestable and never appear. The template
reads the chosen entry again from Infrahub with the same two conditions before it
creates anything, so a stale form cannot request an entry that is no longer
offered. A new entry needs no portal change: the portal ingests the catalogue like
any other kind. See [the application catalogue](./developer-guide/schemas.md#the-application-catalogue).

**The chart is pinned when you ask.** The application is created with the entry's
chart and version, and `generate-fabric-app` then attaches the entry's values and
fills the advertised services, once, on your branch. A later change to the
catalogue never upgrades an application already requested; moving one to a new
version is its own reviewed change.

The ordering is the design. `generate-app-access` reads the application's VIP
block and `generate-fabric-app` is what allocates it; both fire on creation
through independent rules, so a grant created beside its application races the
allocation — and loses for good, because the generator raises and stamps the
grant `error`, and nothing re-runs it until someone edits one of the grant's own
inputs. The template waits for the allocation
between the two creates, then proves the block exists before creating the grant.

It also regenerates the fabric before opening the change, so the reviewer sees
the border leaf's rendered configuration gain its advertisement line rather than
a JSON attribute changing.

Two things the catalogue entry carries are traps worth knowing, because nobody
types them any more:

- **Advertised services** name `SecurityService` objects. The grant derives its
  permitted ports from them and *refuses* rather than guessing when an
  application advertises nothing — so the rule permits the port the application
  actually declared, as one object rather than two numbers that must agree. The
  entry names them, and `generate-fabric-app` applies them when the request left
  them empty.
- **Default values** carry a working exposure block. A chart's Service is
  ClusterIP by default, and an application can be exposed, hold a VIP block and be
  permitted by the firewall while answering nothing. Reaching it needs a
  LoadBalancer Service *and* the label named in the service selector, which is why
  the `whoami` entry's values say both.

### Revoke access

Sets a grant's status to `decommissioning` and lets its generator do the work:
the rule, the address-book entry and the source prefix that grant opened are
removed, and the fabric is regenerated. Removal is keyed on provenance —
`managed_by_service` on rules, `granted_source_prefixes` on sources — so a
hand-written rule in the same zone pair, and a source another live grant still
needs, are both left alone.

### Tenant L3VPN (generated)

Any `OrganizationTenant` can be picked, and any tenant renders onto the WAN. It
needs more than the form asks for, though: the L3VPN puts the tenant's sites in a
provider-edge VRF, and a tenant new to the lab has no site, no circuit, no
customer edge and no provider-edge port. Such a request opens its proposed change
and the `wan-service-consistency` check fails, naming each missing prerequisite —
a live tenant cloud, a `WanSite`, a port for the site's attachment address. Until
then it merges as nothing at all. Model those first, then request the L3VPN.

The form cannot offer `dc_service_prefixes`; a request without them takes the DC
service range every other tenant already imports.

## Adding a hand-written item

Three edits, not one:

1. The template under `backstage/catalog/`.
2. `catalog.locations` in **both** `app-config.yaml` and
   `app-config.docker.yaml`. The docker one *replaces* the dev list and is what
   the deployed portal reads.
3. A `COPY` in `packages/backend/Dockerfile`, which copies only named paths.

Miss either of the last two and it works locally and is absent in the lab, with
nothing logged. `tests/unit/test_combined_app_template_contract.py` asserts all
three, and holds the template's fields against the schema it was written from.

Rebuild with `invoke backstage-build`, never a bare `docker compose build`: the
Dockerfile unpacks a bundle compiled on the host, so a plain build ships new
layers and old JavaScript.
