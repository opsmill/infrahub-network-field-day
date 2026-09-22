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

HTTPS with a self-signed certificate, and that is not about privacy: the frontend
calls `crypto.randomUUID`, which a browser populates only in a secure context, so
over plain HTTP sign-in succeeds and the app then dies. The branch desktop
already trusts the certificate; other machines get a warning to click through.

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

The ordering is the design. `generate-app-access` reads the application's VIP
block and `generate-fabric-app` is what allocates it; both fire on creation
through independent rules, so a grant created beside its application races the
allocation — and loses permanently, because the generator raises, stamps the
grant `error`, and nothing re-runs it. The template waits for the allocation
between the two creates, then proves the block exists before creating the grant.

It also regenerates the fabric before opening the change, so the reviewer sees
the border leaf's rendered configuration gain its advertisement line rather than
a JSON attribute changing.

Two fields carry traps worth knowing:

- **Ports to advertise** names `SecurityService` objects. The grant derives its
  permitted ports from them and *refuses* rather than guessing when an
  application advertises nothing — so the rule permits the port the application
  actually declared, as one object rather than two numbers that must agree.
- **Chart values** are prefilled with a working exposure block. A chart's Service
  is ClusterIP by default, and an application can be exposed, hold a VIP block
  and be permitted by the firewall while answering nothing. Reaching it needs a
  LoadBalancer Service *and* the label named in the service selector.

### Revoke access

Sets a grant's status to `decommissioning` and lets its generator do the work:
the rule, the address-book entry and the source prefix that grant opened are
removed, and the fabric is regenerated. Removal is keyed on provenance —
`managed_by_service` on rules, `granted_source_prefixes` on sources — so a
hand-written rule in the same zone pair, and a source another live grant still
needs, are both left alone.

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
