# Arista AVD Reference Design

## Project context

This repository is the Arista AVD Reference Design for Infrahub. It models datacenter
fabric intent, topology, addressing pools, EVPN services, and per-device AVD data in
Infrahub, then renders EOS configurations and documentation through PyAVD.

Key docs to read before larger changes:

- `README.md` and `docs/docs/home.md` for the current product overview.
- `docs/docs/quick-start.md` for stack/load commands.
- `docs/docs/supported-capabilities.md` before assuming a feature is supported.
- `docs/docs/developer-guide/architecture.md` for the data model and generator chain.
- `docs/docs/developer-guide/schemas.md` for schema kinds and dropdown values.
- `docs/docs/developer-guide/generators.md` for generator structure and execution order.
- `docs/docs/developer-guide/transforms.md` for transform structure and artifacts.
- `docs/docs/developer-guide/avd/overview.md` for the two-phase AVD pipeline.
- `docs/docs/developer-guide/avd/extending.md` for extension workflows.
- `docs/docs/developer-guide/avd/debugging.md` for pipeline debugging.

## Repository layout

- `src/solution_arista_avd/` - core Python library: AVD helpers, cabling,
  addressing, sorting, generator utilities, and generated protocols.
- `generators/` - Infrahub generators and their GraphQL queries / generated
  query models.
- `transforms/` - Python transforms, GraphQL queries, generated query models,
  and templates.
- `checks/` - proposed-change checks (CloudVision validation and its workspace
  lifecycle helpers).
- `ansible/` - playbooks Semaphore runs, including ContainerLab deployment.
- `schemas/` - Infrahub schema definitions, split between base schemas and
  project/feature extensions.
- `objects/` - seed data loaded in filename order. This repository models one
  fabric, `NFD41_FABRIC`, which is the containerlab lab in the NFD41 lab repo;
  the upstream reference design's example fabrics were removed.
- `menus/` - Infrahub UI menu definitions.
- `docs/` - Docusaurus documentation.
- `lab/` - ContainerLab artifact/deployment helpers.
- `queries/` - GraphQL queries with no Python consumer in this repository. Currently
  one: `artifact_ids.gql`, polled by the Vidra operator.
- `vidra/` - deployment assets for the Vidra operator, which applies the Crossplane
  artifacts into the lab's Kubernetes cluster on merge. Helm values, the operator
  ConfigMap, the two `InfrahubSync` declarations, and the **shape** of the credential
  Secret - never the credential itself.
- `.infrahub.yml` - menus, queries, generators, transforms, and artifact
  definitions.
- `repository.yml` - CoreRepository definition.
- `tasks.py` - Invoke task definitions.

## Architecture summary

- Data model hierarchy: `NetworkFabric` -> `NetworkPod` -> `LocationRack` ->
  `DcimFabricSwitch` -> `DcimInterface` / `NetworkLink` / `IpamIPAddress`.
- **There are four device kinds, and they are siblings.** `DcimFabricSwitch` is
  the fabric's EOS switches, `DcimDevice` the WAN's FRR routers,
  `SecurityFirewall` the perimeter firewall, `ComputePhysicalServer` the hosts
  and Kubernetes nodes. All four inherit `DcimGenericDevice`; none inherits
  another, because Infrahub inheritance targets generics and these are nodes.
  **A query naming `DcimDevice` does not see a fabric switch and reports
  nothing** — peer or spread `DcimGenericDevice` to reach every kind.
- The fabric generator chain is `generate-fabric` -> `generate-pod` ->
  `generate-rack` -> `generate-avd-device-hostvar` ->
  `generate-avd-device-structured-config`.
- Hostvars are stored as `AvdHostvarFile` nodes under `AvdArtifact`; structured
  configs are stored as `AvdStructuredConfigFile` nodes under the same artifact.
- AVD transforms render artifacts from the stored files: EOS config, device docs,
  fabric docs, cabling plan, ANTA catalog, and computed interface descriptions.
- PyAVD is version-sensitive; the project targets `pyavd>=6.4.0,<6.5.0`.
- The service portal is a Streamlit app for day-2 workflows; every workflow should
  operate on an Infrahub branch and produce a proposed change for review.

## Generator and transform inventory

Current generator definitions are registered in `.infrahub.yml`:
`generate-fabric`, `generate-pod`, `generate-rack`, `generate-server-cabling`,
`generate-avd-device-hostvar`, `generate-avd-device-structured-config`,
`backfill-structured-config`, and `generate-fabric-peering`.

Current Python transforms are: `computed_interface_description`, `cabling_plan`,
`avd_eos_config`, `avd_fabric_doc`, `avd_device_doc`, `avd_anta_catalog`,
`containerlab_topology`, `cv_workspace_submission_webhook_payload`, `crossplane_fabric_peering`,
`crossplane_fabric_app`, `frr_config`, and `junos_config`.

`frr_config` renders the WAN's FRR configuration — the two ISP provider-edge routers, the
internet router, the two customer edges and the branch router — as one `text/plain` artifact per
device, targeting the `frr_routers` group. It is the half of the lab PyAVD does not cover, and
it is held byte-for-byte against `../lab/wan/rendered/*/frr.conf` by
`tests/unit/test_frr_config.py`. Two things to know before changing it:

- It reads the **service** layer as well as the technical one. A provider edge's per-tenant
  import route-map is assembled from `ServiceL3vpn.dc_service_prefixes`,
  `ServiceTenantCloud.prefix` and whether a `ServiceInternetAccess` exists. That is the
  documented exception to "renderers read technical objects" — the provider edge's policy *is*
  the service intent.
- Its templates are ported from `../lab/wan/templates/` with exactly one line changed, the
  provenance header. Every comment is deliberate; they are most of the teaching value of those
  configs.

`junos_config` renders the perimeter firewall's Junos configuration as one `text/plain` artifact
targeting the `junos_firewalls` group. Three things to know:

- **It covers 592 of `junos.conf`'s 677 lines, and the 85 it does not are two different things.**
  The `system` stanza (13 lines) is *configuration deliberately never modelled*: two credential
  hashes that must never enter the model, and the query must never ask. The file header (72 lines)
  is *not configuration at all* — 68 comments and 4 blanks of lab documentation about the file,
  including how vrnetlab appends it to `init.conf`; the artifact replaces it with its own
  provenance line, because reproducing it would make a false claim about where the file came from.
  Grouping the two as "excluded lines" hides that difference, which is why they are named
  separately here and asserted separately in `test_the_exclusions_add_up`.

  Everything else matches the device byte for byte, **with one exception the model cannot close**:
  the *sequence* of the eleven zone-pair blocks. A zone pair is derived from each rule's source and
  destination zone, so no pair object exists to carry an order, and `SecurityPolicyRule.index`
  orders rules *within* a pair — it holds only 10, 20 and 30 across all nineteen. Junos matches a
  packet to its pair by zone, not by position, so the sequence is presentation. Every pair is
  present and each is byte-for-byte identical.

  The eight static routes are held against three sources by
  `tests/unit/test_fw_static_route_objects.py`, and the third is the interesting one: every next
  hop must lie on a subnet `fw1` has an interface on. A comparison against `junos.conf` cannot
  catch a typo *in* `junos.conf`, so the interface addresses are an independent witness.
  `test_the_exclusions_add_up` makes the total an assertion rather than a caveat, so it is the
  thing to update when those twelve lines move in scope.
- **Order is checked where it is behaviour and relaxed where it is not.** Junos evaluates
  first-match within a zone pair, so rule order is semantic and pinned; the sequence *between*
  pairs is presentational and asserted as a set. The address book's order *is* pinned, through
  `book_index` — added locally because Junos writes it in authoring order and nothing derives it.
- **Two attributes are local additions** in `schemas/security_extensions.yml`: `book_index` on
  `SecurityGenericAddress` and `log_session_close` on `SecurityPolicyRule`. Upstream models `log`
  as a Boolean; the device distinguishes `session-init` from `session-init` plus `session-close`.

Check definitions are `cv-config-validation` (`checks/cv_config_check.py`), with its
workspace lifecycle and helpers in `checks/cv_workspace_lifecycle.py` and
`checks/cv_helpers.py`; `fabric-pool-validation` (`checks/fabric_pool_check.py`); and
`peering-consistency` (`checks/peering_consistency_check.py`). The first two are targeted on
`fabrics`; `peering-consistency` is **global** — it has no `targets`, because its rules are
statements about the whole graph rather than about one fabric.

## Development workflow

1. Prefer schema-first changes: add or update YAML under `schemas/` before code uses
   new nodes, attributes, relationships, or dropdown values.
2. Regenerate generated files rather than hand-editing them:
   - `src/solution_arista_avd/protocols.py` is generated.
   - `*_query.py` Pydantic models next to `.gql` files are generated.
3. Implement generators, transforms, object data, menus, checks, or docs using the
   matching local Infrahub skills when a task touches those artifact types.
4. Keep generators idempotent: use upserts/natural keys, deterministic ordering,
   checksum comparisons, and repeated-run validation.
5. Keep GraphQL responses typed: update `.gql`, regenerate return types, and use the
   generated Pydantic models in production code.
6. Add or update unit tests for changed generator, transform, hostvars, role mapping,
   or utility behavior.
7. Run local unit/lint validation, integration tests and generator idempotence test as applicable.

## Running the AVD chain

`invoke load` seeds objects and runs **no generators**. A freshly loaded instance
therefore has no spine-to-leaf cabling, and PyAVD renders switches with no
uplinks and no underlay or overlay BGP — about 155 lines for a spine instead of
239 — while every artifact still reports `Ready`. Nothing errors. Use
`invoke avd --topology` once after a fresh load to build the fabric.

Thereafter use `invoke avd`, which runs only the two idempotent stages:

| Stage | Idempotent | When |
| --- | --- | --- |
| `generate-fabric`, `generate-pod`, `generate-rack` | **No — destructive on re-run** | `--topology`, build time only |
| `generate-avd-device-hostvar`, `generate-avd-device-structured-config` | Yes | every run |

The topology generators must not be re-run against a fabric that already has
cabling. `generate-pod` takes each spine from nine interfaces to four, deleting
the leaf-role ports racks 1 and 2 are cabled to, and `generate-rack` then fails
on rack 3 with an `IndexError` because its slice of spine ports is empty. That
is why they are behind a flag rather than in the default path.

**Use `--branch` for anything you intend to review.** The chain writes a great
deal of derived data, and doing that straight onto `main` leaves nowhere to see
what changed first. Artifact regeneration passes the branch through to
`POST /api/artifact/generate/{id}`; omit it and the endpoint regenerates against
`main`, which produces the confusing result that
`infrahubctl transform --branch X` renders your change while the stored artifact
never moves.

## Naming conventions

- Generators: `generate_<entity>.py`.
- Generator GraphQL queries: matching `.gql` files.
- Generated query models: `*_query.py`; regenerate them from `.gql` files rather
  than hand-editing.
- Node namespaces commonly used here: `Network.*`, `Location.*`,
  `Organization.*`, `Ipam.*`, `Dcim.*`, `Avd.*`, `Routing.*`, `Evpn.*`,
  `Interface.*`, `Compute.*`.

## Extension checklist

When adding an **AVD-rendered fabric** device role:

1. Add the role value to the **`DcimFabricSwitch`** dropdown in
   `schemas/dcim_extensions.yml`. That list must stay equal to `ROLE_TO_AVD_TYPE`;
   `tests/unit/test_dcim_schema_contract.py` asserts it.
2. Load/check schema and regenerate generated files.
3. Update `ROLE_TO_AVD_TYPE` in `src/solution_arista_avd/avd.py`.
4. Update `generators/generate_avd_device_hostvar.py` for role-specific fields.
5. Update whichever upstream generator creates devices of that role and group membership.
6. Add tests, especially `tests/unit/test_avd.py` and hostvars tests when needed.
7. Update `docs/docs/developer-guide/avd/role-mapping.md` and hostvars docs.

When adding a **non-EOS** device role, steps 3 to 5 and 7 do not apply, and the role
goes on **`DcimDevice`'s** dropdown rather than `DcimFabricSwitch`'s — cycle 027 split
the one dropdown into two, so "add the role value in `schemas/dcim_extensions.yml`"
now requires choosing which kind. The role values `isp_edge`, `isp_core`,
`internet_edge`, `customer_edge`, `branch_router` and `k8s_node` describe equipment
pyAVD never renders, and they are deliberately absent from `ROLE_TO_AVD_TYPE` (there is
no `firewall` value at all: a firewall is a `SecurityFirewall`):

- `get_avd_type` raises `ValueError` for an unmapped role. That loud failure is the
  wanted behaviour here; mapping one would instead let a firewall or an FRR router be
  rendered as an EOS switch, which fails silently.
- Devices with these roles must never join the `avd_devices` group, which is the only
  path into the AVD hostvar generator. Membership is set in one place,
  `src/solution_arista_avd/generator.py`, on the device-creation path the fabric and
  rack generators run from device designs — so a manually loaded device stays out.
- Add the role to `NON_AVD_DEVICE_ROLES` in `tests/unit/test_avd.py`, which keeps
  `test_schema_roles_all_mapped` guarding the fabric roles while excluding these, and
  update `docs/docs/developer-guide/schemas.md` instead of the AVD role-mapping doc.

When adding a transform output:

1. Add the `.gql` query under `transforms/`.
2. Regenerate the matching `*_query.py`; do not hand-write it.
3. Implement the transform class in `transforms/`.
4. Register the query, transform, and artifact definition in `.infrahub.yml`.
5. Add unit tests and integration coverage when appropriate.

When adding a hostvars field:

1. Add schema if the source data is not already represented.
2. Reload/check schema and regenerate protocols / GraphQL schema / return types.
   Use `graphql export-schema --destination schema.graphql` with the current CLI.
3. Update `generators/avd_device_hostvar.gql`.
4. Map the field in `generators/generate_avd_device_hostvar.py`.
5. Confirm the field is accepted by the pinned PyAVD version.
6. Add tests and update `docs/docs/developer-guide/avd/hostvars.md`.

## Commands agents may use

Install and discovery:

```bash
uv sync --all-packages
uv run invoke --list
```

Invoke tasks:

```bash
uv run invoke build
uv run invoke start
uv run invoke stop
uv run invoke destroy
uv run invoke restart
uv run invoke restart --component=infrahub-server
uv run invoke restart --component=service-catalog
uv run invoke load
uv run invoke load-schema
uv run invoke load-menu
uv run invoke avd                       # regenerate AVD hostvars, structured configs and artifacts
uv run invoke avd --branch my-change    # ... on a branch, so the result can be reviewed
uv run invoke avd --topology            # BUILD-TIME ONLY: also build the fabric and its cabling
uv run invoke init-semaphore
uv run invoke test
uv run invoke lint
uv run invoke lint-ruff
uv run invoke lint-yaml
uv run invoke lint-mypy
uv run invoke lint-markdown
uv run invoke lint-prose
uv run invoke format
uv run invoke docs
```

Local tests and linters:

```bash
uv run pytest tests/unit
uv run pytest tests/unit/test_avd.py
uv run pytest tests/unit/test_hostvar_ordering.py
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
uv run mypy --show-error-codes src/solution_arista_avd
uv run yamllint .
uv run rumdl check README.md AGENTS.md docs/ lab/README.md schemas/
uv run rumdl fmt README.md AGENTS.md docs/ lab/README.md schemas/
```

Markdown linting covers authored files only; vendored agent content, `specs/`, and
PyAVD-rendered output under `lab/avd/` are excluded in `[tool.rumdl]`.

Prose linting uses Vale, which is a Go binary rather than a `uv` dependency. Install the
pinned version before running `invoke lint-prose`:

```bash
curl -sL "https://github.com/errata-ai/vale/releases/download/v3.17.1/vale_3.17.1_Linux_64-bit.tar.gz" \
  -o /tmp/vale.tar.gz && tar -xzf /tmp/vale.tar.gz -C ~/.local/bin vale
vale sync
```

Use local `uv run pytest tests/integration` only for ad-hoc local/lab debugging when explicitly
appropriate.

`infrahubctl` examples:

```bash
uv run infrahubctl branch list
uv run infrahubctl branch create <branch-name>
uv run infrahubctl schema check schemas/ --branch <branch-name>
uv run infrahubctl schema load schemas --branch <branch-name>
uv run infrahubctl menu load menus/ --branch <branch-name>
uv run infrahubctl object load objects/ --branch <branch-name>
uv run infrahubctl object load repository.yml --branch <branch-name>
uv run infrahubctl object load triggers.yml --branch <branch-name>
uv run infrahubctl graphql export-schema --destination schema.graphql
uv run infrahubctl graphql generate-return-types generators/avd_device_hostvar.gql
uv run infrahubctl graphql generate-return-types transforms/<query>.gql
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

For repeated `infrahubctl` calls, define a temporary shell alias in the current session only:

```bash
alias ihctl='uv run infrahubctl'
```

The documentation site uses pnpm, not npm. Prefer `uv run invoke docs`, which runs the same
commands CI runs. To work inside `docs/` directly:

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

pnpm settings for the site live in `docs/pnpm-workspace.yaml`, not in `docs/package.json` -
pnpm no longer reads the `pnpm` field there, so overrides placed in it are ignored.

## Documentation publishing

`docs/docs/` is synced to `opsmill/infrahub-docs` by `.github/workflows/sync-docs.yml` on
every push to `main`, and published at `docs.infrahub.app/arista-avd`. That site mounts this
content under a `/arista-avd` route rather than at the site root, so two rules apply to
anything added under `docs/docs/`:

- Link between pages with relative Markdown paths (`](./quick-start.md)`,
  `](../troubleshooting.md)`), never root-absolute ones (`](/quick-start)`). Absolute paths
  resolve locally because `routeBasePath` is `/` here, but on the aggregation site they point
  at core Infrahub pages and fail its build, which sets `onBrokenLinks: 'throw'`.
- Keep the sidebar key in `docs/sidebars.ts` named `aristaAvdSidebar`. The aggregation site's
  navbar references it by name, and sidebar keys must be unique across that site.

Edits made directly in `infrahub-docs` are overwritten by the next sync.
