# Transform Specification: Junos Configuration for the Perimeter Firewall

> **Workflow**: Infrahub Transform
> **Skill**: Use the `infrahub-managing-transforms` skill to implement this spec.

**Feature Branch**: `023-junos-config-render`
**Created**: 2026-09-12
**Status**: Draft — re-scoped. Implementation found the seeded data does not transcribe the
oracle (research.md R9); the seed repair is now **inside** this cycle rather than deferred.
**Input**: The last unrendered domain in cycle 010's table — the perimeter firewall.

## Why this cycle exists

Cycle 010 listed four lab domains held in hand-maintained files outside Infrahub. Three now
render: the fabric through AVD, Kubernetes and applications through cycles 011 and 017, and the
ISP, WAN and branch through cycle 022. **The firewall is the fourth and last.**

010's assumption 8 committed to it, and records that it was confirmed with the requester:

> *All six zones, every address-book entry and group, and all eleven zone-pair policies —
> including the anti-spoofing baseline repeated at the head of the first six pairs — are
> modeled, so `junos.conf` becomes a rendered artifact rather than a hand-maintained file. This
> extends the fabric's "nothing is configured by hand" property to the perimeter, and it is why
> US4 models policies and rules rather than only the grants issued against them. The alternative
> — modeling zones while leaving the baseline policies hand-written — was rejected because it
> leaves two sources of truth for one device.*

The model has been ready since cycle 010 and nothing has read it. Everything that assumption
promised is seeded and idle:

| Modelled | Count |
| --- | --- |
| `SecurityZone` | 6 |
| `SecurityFirewallInterface` (with addresses and zone bindings) | 6 |
| `SecurityIPAMIPPrefix` / `SecurityIPAMIPAddress` / `SecurityPrefix` | 12 / 1 / 1 |
| `SecurityAddressGroup` | 4 |
| `SecurityService` / `SecurityIPProtocol` | 3 / 2 |
| `SecurityPolicy` / `SecurityPolicyRule` | 1 / 19 |

That matches 010's SC-004 exactly — 6 zones, 13 addresses, 4 groups, 11 zone pairs, 19 rules.

### The anti-spoofing baseline, and what this cycle does *not* fix

`deny-spoofed-infra` is written by hand six times in `junos.conf`, at the head of six different
zone pairs, identical each time. An early draft of this specification claimed the render would
collapse that to one stored rule emitted six times. **It will not, and it cannot.**

The model already holds six distinct rule objects — verified against the live graph. That is not
a seeding choice: `SecurityPolicyRule.source_zone` and `.destination_zone` are cardinality-one
and mandatory, and the uniqueness constraint is
`[index, source_zone, destination_zone, policy]`, so a rule belongs to exactly one zone pair by
construction. The kind comes from `infrahub/security`, which `schemas/MARKETPLACE.md` keeps
byte-identical, so the cardinality is not this repository's to change.

What the cycle does deliver is smaller but real: the six copies stop being text in a 677-line
file and become objects in a graph — queryable, diffable, and changeable together by a script, a
generator or a check. **Making the six provably identical is a follow-up**, and the natural
shape for it is a check, not a renderer.

The cycle's argument stands without the copy-paste claim: 010's assumption 8 asked for
`junos.conf` to become a rendered artifact rather than a hand-maintained file, and that is what
this does.

### How this cycle differs from 022, and why it is harder

Cycle 022 was a **port**. The lab had five Jinja2 templates that were known correct, and the
work was to feed them from Infrahub and diff.

`junos.conf` has no templates. It is hand-written and pushed as-is, so the templates here must
be **written against the golden file** rather than ported into it. There is no prior art to
inherit and no "the lab already proved this renders" safety net. The oracle is just as good —
677 lines the firewall actually runs — but the risk profile is different, and the plan should
expect more iteration against the diff than 022 needed.

## Scope: two artifact types, deliberately

This cycle covers **Infrahub Objects and then an Infrahub Transform**. The extension's routing
normally takes one artifact type per cycle, and that rule is being set aside here on the
requester's decision, recorded so the deviation is visible rather than accidental.

The reason it is defensible: the object work is not a design exercise. It is 33 transcriptions
from a file that already exists, it has no schema component, and it is verified by the same
golden-file diff that verifies the transform. Splitting it would mean two cycles sharing one
oracle and one acceptance test.

- **Objects**: repair `objects/32_nfd41_security.yml` against `../lab/configs/fw/vsrx/junos.conf`
- **Approach**: **Hybrid** — Python assembles the zone, address-book and policy context from a
  GraphQL query; Jinja2 emits Junos' braced syntax
- **Output Format**: `text/plain` — Junos configuration
- **Target Nodes**: `SecurityFirewall` — `fw1`, the only firewall

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The seed transcribes the firewall (Priority: P1) 🎯 MVP

An engineer comparing `objects/32_nfd41_security.yml` to `../lab/configs/fw/vsrx/junos.conf`
finds the same firewall described twice, not two similar ones. Every rule names the addresses,
groups and applications the file names; every interface carries the file's description and MTU.

**Why this priority**: nothing downstream can be right until this is. A renderer cannot emit
`destination-address acme-sites;` from an empty relationship, and cycle 010 seeded the structure
faithfully but the values approximately. This is the step the firewall never had — the same one
cycles 020 and 021 gave the WAN.

**Independent Test**: a test comparing every rule's addresses, groups and applications, and
every interface's description and MTU, against the oracle in both directions. It needs no
renderer and no server.

**Acceptance Scenarios**:

1. **Given** the oracle, **When** each of the 19 rules is compared, **Then** its source
   addresses, destination addresses and applications match the file exactly.
2. **Given** the four address groups, **When** rule references are inspected, **Then** each group
   is referenced by the rules that name it — six references in total, where today there are none.
3. **Given** the six interfaces, **When** their descriptions and MTUs are compared, **Then** both
   match the file, with MTU `9192` rather than the schema default.
4. **Given** the applications, **When** `any` is looked up, **Then** it exists as a service
   object, because eleven rules reference it.
5. **Given** a second load of the object file, **Then** it produces no error and no duplicate.

---

### User Story 2 - The zones and the address book render (Priority: P2)

An engineer opens `fw1` in Infrahub and reads its interface-to-zone bindings and its complete
address book as configuration: six zones, each with its interfaces, and thirteen named addresses
grouped into four groups. The output matches what the firewall runs.

**Why this priority**: it is the foundation every policy references — a rule naming
`source-address fabric-infra` is meaningless until the group exists — and it establishes the
query, the template and the golden-diff harness that stories 3 and 4 reuse. Roughly 130 of the
573 in-scope lines. Depends on US1: a rendered address book is only right if the seed is.

**Independent Test**: render `fw1`, extract the `interfaces` and `security { address-book }` and
`security { zones }` stanzas, and diff each against `../lab/configs/fw/vsrx/junos.conf`.

**Acceptance Scenarios**:

1. **Given** the security model is loaded, **When** the artifact is generated, **Then** all six
   zones appear with their bound interfaces, matching the lab.
2. **Given** the address book, **When** it is rendered, **Then** all thirteen entries and four
   groups appear, and every address is the one the IPAM object holds — not a restated CIDR.
3. **Given** an address used by more than one group, **When** the book is rendered, **Then** it
   is defined once and referenced by name.

---

### User Story 3 - The zone-pair policies render, baseline included (Priority: P3)

All eleven zone pairs render with their rules in evaluation order, and `deny-spoofed-infra`
appears at the head of the six pairs that carry it — emitted from one stored rule rather than
written out six times.

**Why this priority**: the payoff and the risk. Junos evaluates policies within a zone pair in
order, so a renderer that emits them in the wrong sequence produces a configuration that loads
cleanly and enforces something different. It is the largest stanza and the one where a subtle
error is invisible.

**Independent Test**: diff the `security { policies }` stanza against the lab, then assert
`deny-spoofed-infra` appears exactly six times with identical bodies.

**Acceptance Scenarios**:

1. **Given** the 19 policy rules, **When** the policies stanza is rendered, **Then** it matches
   the lab byte for byte, with every rule under its correct zone pair.
2. **Given** a zone pair with several rules, **When** it is rendered, **Then** the rules appear
   in the order the model stores them, because Junos evaluates first-match.
3. **Given** the anti-spoofing rule, **When** the configuration is rendered, **Then** it appears
   at the head of all six pairs that carry it, from a single stored rule.
4. **Given** a rule that logs, **When** it is rendered, **Then** its `then { deny; log { ... } }`
   block matches the lab exactly.

---

### User Story 4 - The rendered configuration is loadable as a whole (Priority: P4)

The artifact is a coherent Junos configuration file, not a set of fragments: correct brace
nesting, correct stanza order, and the trailing newline a parser expects.

**Why this priority**: stories 2 and 3 can each be diffed stanza by stanza while still producing
a file that would not load. This story is what makes the artifact usable rather than merely
correct in pieces.

**Independent Test**: brace-balance the whole output and diff it against the in-scope stanzas of
the lab file end to end.

**Acceptance Scenarios**:

1. **Given** the rendered configuration, **When** braces are counted, **Then** every block is
   balanced and nesting depth returns to zero at the end.
2. **Given** the whole artifact, **When** it is diffed against the lab's `interfaces` and
   `security` stanzas, **Then** there is no difference.
3. **Given** the artifact, **When** its scope is compared to the lab file, **Then** it omits
   exactly the `system` stanza, the `routing-options` stanza and the `flow` block — and nothing
   else.

---

### Edge Cases

- **The configuration contains credential hashes.** `system { root-authentication }` and
  `system { login }` hold two `encrypted-password` values. These must never enter the model and
  must never be rendered. This is the one stanza whose absence from the artifact is a feature.
- **An address in two groups** must be defined once and referenced twice, not duplicated.
- **`any` is referenced but never defined.** It exists in the model as an address object so a
  rule's `destination_address` has something to point at, but Junos treats `any` as a keyword
  and the address book must not declare it.
- **A zone with no policies** — the model may hold one — must still render its interface
  bindings.
- **A zone pair with exactly one rule** must not render the plural scaffolding differently from
  a pair with five.
- **Rule order is semantic, not cosmetic.** Junos evaluates first-match within a zone pair, so a
  reordered render is a different firewall that loads without complaint.
- **An application list with one entry** renders as `application junos-http;`, but with several
  as `application [ junos-http junos-https ];`. Getting the bracket form wrong is a syntax error
  on one path and silent on the other.
- **An address group with one member** has the same bracket problem.
- **Junos comments** (`/* ... */`) appear in the lab file and carry intent. Whether the render
  reproduces them is a scope decision the plan must settle, not a detail to discover during the
  diff.

## Requirements *(mandatory)*

### Functional Requirements

#### Object Data — the seed repair

- **FR-050**: `objects/32_nfd41_security.yml` MUST transcribe `../lab/configs/fw/vsrx/junos.conf`,
  which is the oracle. No value may be invented or paraphrased.
- **FR-051**: The six address-**group** references MUST be linked — 3 on `source_address`, 3 on
  `destination_address`. All four groups are seeded today and referenced by nothing.
- **FR-052**: The 14 missing application links MUST be added, 11 of them `any`.
- **FR-053**: `any` MUST be added as a service object. `junos-http`, `junos-https` and
  `junos-ping` already exist; `any` is the only named application the model lacks.
- **FR-054**: The six interface descriptions MUST match the file's strings exactly, replacing the
  current paraphrases.
- **FR-055**: The six interface MTUs MUST be set to `9192`, replacing the schema default `1514`.
- **FR-056**: The object file MUST load idempotently — a second run produces no error and no
  duplicate.
- **FR-057**: No schema change. `SecurityAddressGroup` is already a concrete kind of
  `SecurityGenericAddress`, so groups are linkable today, and `mtu` and `description` already
  exist on `SecurityFirewallInterface`.

#### GraphQL Query

- **FR-001**: A GraphQL query MUST be added under `transforms/` retrieving the firewall's zones,
  interfaces with their addresses and zone bindings, the full address book, address groups,
  services and IP protocols, and the policy with all of its rules.
- **FR-002**: The query MUST accept the device as a variable, matching the artifact definition.
- **FR-003**: The query MUST retrieve each rule's index, source and destination addresses,
  applications, action, logging, and its zone pair.
- **FR-004**: Addresses MUST be read from their IPAM objects, never from a restated text field.
- **FR-005**: The query MUST be registered in `.infrahub.yml` under `queries`.

#### Transform Logic

- **FR-010**: The transform MUST be a Python class preparing the context and rendering Jinja2.
- **FR-011**: The transform MUST return a string, so the artifact is `text/plain`.
- **FR-012**: Policy rules MUST be emitted in the order the model stores them, because Junos
  evaluates first-match within a zone pair.
- **FR-013**: Rules MUST be grouped into zone pairs from their `source_zone` and
  `destination_zone`, and each pair rendered once with its rules in `index` order. A rule name
  appearing in several pairs is several objects, not one — see "what this cycle does not fix".
- **FR-014**: The transform MUST raise rather than render when a required value is absent.
- **FR-015**: The transform MUST NOT emit any credential, and MUST NOT read one. The `system`
  stanza has no representation in the model and must gain none.
- **FR-016**: List-valued fields MUST use Junos' bracket form only when there is more than one
  member, and the bare form otherwise.
- **FR-017**: The address named `any` MUST be excluded from the rendered address book and still
  emitted wherever a rule references it.

#### Jinja2 Templates

- **FR-020**: Templates MUST be added under `transforms/templates/junos/`.
- **FR-021**: The environment MUST use strict undefined handling, so a missing value fails the
  render instead of emitting an empty statement.
- **FR-022**: The output MUST open with a provenance line naming Infrahub and the device. As in
  cycle 022, the artifact must not claim to be something it is not.
- **FR-023**: Brace nesting MUST be balanced and the file MUST end with a newline.

#### Artifact & Registration

- **FR-030**: A `CoreStandardGroup` MUST be added for the firewall, with `fw1` as its member.
- **FR-031**: The transform MUST be registered under `python_transforms` in `.infrahub.yml`.
- **FR-032**: An artifact definition MUST be registered with content type `text/plain`,
  targeting the new group, and mapping the device name to the query variable.

#### Tests

- **FR-040**: A unit test MUST render `fw1` from a fixture and diff the result against the
  in-scope stanzas of `../lab/configs/fw/vsrx/junos.conf`.
- **FR-041**: The fixture MUST be captured from the live graph, not hand-written.
- **FR-042**: A test MUST assert `deny-spoofed-infra` renders exactly six times with identical
  bodies. It does not assert deduplication, which the adopted schema forbids; it asserts that
  six separately stored rules still render the same, which is the property a later check would
  enforce at the model level.
- **FR-043**: A test MUST assert no `encrypted-password`, key material or other credential
  appears anywhere in the rendered output.
- **FR-044**: A test MUST assert brace balance.

### Key Files

| File | Purpose |
|------|---------|
| `transforms/junos_config.gql` | GraphQL query for the firewall |
| `transforms/junos_config_query.py` | Generated return types — regenerated, never hand-written |
| `transforms/junos_config.py` | The transform class and its context assembly |
| `transforms/templates/junos/*.j2` | The Junos templates |
| `objects/00_groups.yml` | The new target group |
| `.infrahub.yml` | Query, transform and artifact registration |
| `tests/unit/test_junos_config.py` | Golden-file parity against the lab |

### Key Entities

- **`SecurityZone`**: the six trust domains. Each names its interfaces.
- **`SecurityFirewallInterface`**: the six physical interfaces, their addresses and their zones.
- **`SecurityIPAMIPPrefix` / `SecurityIPAMIPAddress` / `SecurityPrefix`**: the address book.
  IPAM-backed, so an address matched here is the same object the route policies match on.
- **`SecurityAddressGroup`**: the four named groups rules refer to.
- **`SecurityService` / `SecurityIPProtocol`**: the applications a rule permits.
- **`SecurityPolicy` / `SecurityPolicyRule`**: the eleven zone pairs and their nineteen rules,
  with evaluation order preserved.
- **Rendered Junos configuration**: one `text/plain` artifact for `fw1`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The rendered artifact matches the `interfaces` and `security` stanzas of
  `../lab/configs/fw/vsrx/junos.conf` exactly — **573 of its 677 lines**, being `interfaces` (76)
  plus `security` (504) less the unmodelled `flow` block (7) — excluding only the provenance
  header **and the sequence of zone pairs within the `policies` stanza**, which is asserted as a
  set with byte-for-byte equality inside each pair.

  The carve-out is deliberate and narrow. Junos selects a zone pair by from-zone/to-zone and
  evaluates only within it, first-match, so order *inside* a pair is behaviour — and the model
  carries it in `index`, which the render reproduces and a test pins. Order *between* pairs is
  presentational and has no object to attach an index to, because pairs are derived from each
  rule's zones rather than stored. The address book's order, by contrast, did have a natural home
  and so was modelled (`book_index`) rather than excused. See research.md R11 and R12.
- **SC-011**: Every rule's source addresses, destination addresses and applications match the
  oracle, compared in both directions — 20 field corrections across 15 rules, and nothing
  invented.
- **SC-012**: Each of the four address groups is referenced by the rules that name it: six
  references, where today there are none.
- **SC-013**: All six interfaces carry the file's description and MTU `9192`.
- **SC-014**: A second load of every object file produces no error and no duplicate.
- **SC-002**: All six zones, thirteen address-book entries, four groups, eleven zone pairs and
  nineteen rules appear, matching 010's SC-004. The model's fourteenth address, `any`, is
  referenced by rules and absent from the book.
- **SC-003**: The six `deny-spoofed-infra` rules render at the head of their six zone pairs with
  byte-identical bodies. They are six objects in the model, and the render must not silently
  diverge them.
- **SC-004**: Rule evaluation order within every zone pair matches the lab.
- **SC-005**: **No credential of any kind appears in the artifact, the model or the query.**
- **SC-006**: Brace nesting is balanced and the output ends with a newline.
- **SC-007**: Every value traces to an object in the graph; none is hardcoded in a template
  except Junos' own syntax.
- **SC-008**: The artifact definition generates exactly one artifact.
- **SC-009**: All unit tests and the repository's linters pass.
- **SC-010**: **What the artifact does not cover is enumerated with a reason for each**, and
  totals exactly the **104** lines named in Out of Scope. A renderer that silently omits part of
  a firewall's configuration is worse than one that does not exist.

## Assumptions

1. **The model is ready and untouched.** Cycle 010 seeded everything this needs and nothing has
   read it since. No schema change and no new object data beyond the target group — the same
   shape as cycle 022.
2. **Templates are written, not ported.** Unlike 022 there is no prior Jinja2 to inherit, so the
   templates are authored against the golden file. The plan should expect iteration.
3. **The provenance line is the only intentional difference**, as in cycle 022.
4. **`fw1` is a `SecurityFirewall`**, not a `DcimDevice` — verified against the live graph. The
   kind inherits `CoreArtifactTarget`, so it can carry artifacts with no schema change, which
   matters because `security/security.yml` is marketplace-adopted and could not be changed to
   add it.
5. **Junos comments are reproduced.** The lab file's `/* ... */` comments explain why named
   objects are used rather than bare CIDRs, and why the anti-spoofing baseline is repeated.
   Cycle 022 kept the FRR comments for the same reason and it cost nothing.

## Out of Scope

Enumerated rather than summarised, because SC-010 turns on it. Counted from the file rather than
estimated. Of `junos.conf`'s 677 lines, **104** are not rendered:

- **`system { ... }` — 13 lines. Credentials.** Two `encrypted-password` hashes, for root and
  for the admin user. These must never enter the model. This is the one exclusion that is
  permanent rather than deferred.
- **`routing-options { static { ... } }` — 12 lines.** Eight static routes pointing at the
  fabric handoffs. The next hops exist as IPAM objects, but nothing gives a *device* a static
  route: `RoutingStaticRoute` exists as a kind and `static_routes` is a VRF relationship, not a
  device one. Rendering them would mean hardcoding eight routes in a template, which SC-007
  forbids. **This needs a small schema cycle first** — the same 019→020 pattern — and then these
  twelve lines can join the artifact.
- **`security { flow { tcp-mss 9138 } }` — 7 lines,** nested inside the otherwise in-scope
  `security` stanza. No kind models it. The value is the lab's
  MTU of 9214 less 76, so it is derivable in principle, but nothing models the firewall's MTU
  and inferring it from the WAN's would be a guess.
- **Blank lines and file-level comments outside any top-level stanza — 72 lines.** The three
  exclusions above account for 32; these are the rest.

Also out of scope:

- **Deploying the configuration.** Nothing here talks to the firewall.
- **Any schema change.** If something turns out to be unrepresentable it belongs in a schema
  cycle first, per the layering rule 010 established.
- **The `protocols.py` extensions gap.** Still on the backlog; this transform will use the
  generated GraphQL return types, as cycle 022 did.

## Dependencies

None outstanding. Cycle 010's security model is merged and seeded, `fw1` exists, and cycles 020
through 022 are merged and pushed. This cycle stands alone.
