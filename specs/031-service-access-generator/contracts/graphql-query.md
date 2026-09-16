# Contract: `generators/generate_app_access.gql`

One query, one parameter, one grant. Aliased `target:` because the generator is parameterised on the service's name — the same shape `generate_fabric_peering.gql` uses.

```graphql
query GenerateAppAccessQuery($name: String!) {
  target: ServiceAppAccess(name__value: $name) { ... }
  SecurityPolicy { ... }
  SecurityZone { ... }
  SecurityService { ... }
  SecurityGenericAddress { ... }
}
```

## Parameter

| Variable | Mapped from | Registered as |
| --- | --- | --- |
| `$name` | the grant's `name__value` | `parameters: {name: name__value}` in `.infrahub.yml` |

## What `target:` must return

| Path | Why the generator needs it |
| --- | --- |
| `id`, `name { value }` | Identity; the name is the natural key every generated object derives from |
| `status { value }` | So the generator can tell whether it is changing state |
| `approved { value }` | **The gate.** V1 |
| `requester { value }`, `justification { value }` | Carried into the generated rule's description |
| `ports { value }` | One service object per entry. V2, V3 |
| `application { node { id name { value } vrf { node { id name { value } } } } }` | The destination-zone derivation. V4 |
| `source_zone { node { id name { value } } }` | Used directly as the rule's source zone |
| `source_address { node { id name { value } } }` | Used directly as the rule's source address |
| `destination_vip { node { id address { value } } }` | Wrapped in the generated address-book entry |
| `granted_rules { edges { node { id name { value } } } }` | What a previous run already granted |

## What the firewall context must return

Fetched unfiltered, because the generator resolves against the whole set rather than by name.

| Root field | Fields | Used for |
| --- | --- | --- |
| `SecurityPolicy` | `id`, `name { value }`, `device_target { node { id name { value } } }` | Deriving the policy the rule joins. V6 |
| `SecurityZone` | `id`, `name { value }`, `vrf { node { id } }` | Matching the application's VRF to a zone. V5, V8 |
| `SecurityService` | `id`, `name { value }`, `port { value }`, `ip_protocol { node { id name { value } } }` | Adoption by `(protocol, port)` — so a grant for 443 finds `junos-https` |
| `SecurityGenericAddress` | `id`, `name { value }`, `book_index { value }`, and `... on SecurityIPAMIPAddress { ip_address { node { id } } }` | Adoption by wrapped address, and finding the highest `book_index` in use |

`SecurityGenericAddress` is a generic, so reaching `ip_address` requires an inline fragment on `SecurityIPAMIPAddress`. `transforms/junos_config.gql` documents the same constraint at its own `SecurityGenericAddress` block: "a fragment per kind is mandatory."

## What the query must NOT fetch

- **`SecurityFirewallInterface`.** The first design derived the destination zone from interface containment; the handoff interfaces are `/30` point-to-points that contain no VIP. Fetching them would invite that derivation back. See [research.md](../research.md) R2.
- **`SecurityPolicyRule` beyond `granted_rules`.** The generator allocates indices from a fixed floor of 100 rather than from the highest index in the pair, deliberately (research R1), so it does not need to read the baseline. Reading it would make the allocation non-deterministic.
- **Anything under `DeploymentState` or `DeploymentDiffFile`.** `AGENTS.md` forbids generating from them, and `tests/unit/test_deployment_schema_contract.py` fails when someone does.

## Generated return types

```bash
uv run infrahubctl graphql generate-return-types generators/generate_app_access.gql
```

Produces `generators/generate_app_access_query.py`. **Never hand-edited** (FR-014, constitution III). The generator imports the generated classes and aliases the verbose ones at module level, following `generate_fabric_peering.py`:

```python
from .generate_app_access_query import (
    GenerateAppAccessQuery,
    GenerateAppAccessQueryTargetEdgesNode,
)
```
