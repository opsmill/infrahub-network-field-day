# Acceptance Evidence

**Feature**: `specs/023-junos-config-render` | **Date**: 2026-09-12
**Branch**: `fw-render` (Infrahub) / `023-junos-config-render` (git)

## SC-001, SC-002 — the firewall renders

554 lines, against the 573 in-scope lines of `../lab/configs/fw/vsrx/junos.conf`. Every stanza
matches the device:

```text
interfaces    stanza: byte-for-byte
address-book  stanza: byte-for-byte, including its order
zones         stanza: byte-for-byte
policies      stanza: all 11 zone pairs byte-for-byte within each pair
```

Counts, from the live render:

```text
security-zone   6      address       13      address-set   4
from-zone      11      policy        19      deny-spoofed-infra  6
```

The live `infrahubctl transform` output is identical to the fixture render, modulo the single
trailing newline the CLI adds on stdout.

## SC-001's one carve-out — and why the address book did not get one

The sequence **between** zone pairs is asserted as a set rather than a sequence. Junos selects a
pair by from-zone/to-zone and evaluates only within it, so order between pairs changes nothing;
order **inside** a pair is first-match and therefore behaviour, and is pinned from
`SecurityPolicyRule.index` by `test_rule_order_within_every_pair_matches_the_device`.

The distinction that decided it: a zone pair is **derived** from each rule's zones, not stored,
so an index would have to sit on every rule and be identical across the pair — denormalised, and
a new way for the data to contradict itself. The address book *does* have a natural home for one,
which is why it was modelled rather than excused.

## SC-003 — six identical anti-spoofing rules

`deny-spoofed-infra` renders six times with byte-identical bodies, from six distinct objects.
Six, not one, because `source_zone` and `destination_zone` are cardinality-one on the adopted
schema — a rule belongs to exactly one pair by construction (research.md R2). The render must not
let them drift, and `test_the_anti_spoofing_rule_renders_six_times_identically` is what stops it.

## SC-005 — no credential, in the artifact or the model

```text
artifact: 0 matches for encrypted-password | ssh-rsa | ssh-ed25519 | PRIVATE KEY
model:    0 matches across objects/ schemas/ transforms/
```

The only repository hit is a docstring in `transforms/junos_config.py` explaining why the
`system` stanza is excluded. The requirement is about the graph as much as the output: an
artifact can be diffed, and a credential that reaches the model has reached every branch and
every export of it.

## SC-006, SC-010 — braces, and the arithmetic of what is missing

```text
brace depth at EOF: 0, never negative | ends with newline: True
in scope 573 | excluded 104 = system 13 + routing-options 12 + flow 7 + 72 outside any stanza
```

`test_the_exclusions_add_up` asserts both totals, so the gap cannot widen unnoticed.

## SC-008, SC-011 to SC-014 — registration and the seed

```text
group junos_firewalls: 1 member — fw1
query registered: True | transform: JunosConfig
class query attr: junos_config == registered query
artifact transformation: junos_config == transform name
targets: junos_firewalls | content_type: text/plain
```

The seed is a transcription: every rule's addresses, groups and applications match the oracle in
both directions, all six interfaces carry the device's own description and MTU 9192, and a second
`object load` leaves every count unchanged.

## Two local schema additions

Both in `schemas/security_extensions.yml`, both because the device distinguishes something
upstream does not model:

- **`book_index`** on `SecurityGenericAddress`. Junos writes the address book in authoring order,
  and nothing derives it — not alphabetical, not by network address, not by prefix length, all
  checked. Added on the generic so one attribute covers all six concrete address kinds. An absent
  index turned out to do double duty: `any` is the one address with no position in the file,
  because Junos declares it in neither the address book nor the applications stanza.
- **`log_session_close`** on `SecurityPolicyRule`. Upstream models `log` as a Boolean; the device
  logs `session-init` on every rule and `session-close` on the eight long-lived permits. It could
  have been inferred — "permit, unless the application is `junos-ping`" — which would match today
  while burying an unstated policy in the renderer.

`tests/unit/test_security_schema_contract.py` asserted that exactly two kinds were extended
locally. It failed, correctly, and was updated to three rather than loosened.

## Gates

```text
uv run pytest tests/unit              998 passed
  test_junos_config.py                 23
  test_junos_seed_data.py              17
uv run ruff check .                   All checks passed
uv run ruff format --check .          107 files already formatted
uv run yamllint schemas/ objects/     clean
uv run mypy src/solution_arista_avd   Success
uv run rumdl check AGENTS.md docs/    no issues
```

## Corrections this cycle made to its own record

Three counted claims were wrong before they were right, each recorded rather than quietly fixed:

- **The line accounting** (research R4): 580/97, corrected to 573/104 after the `flow` block was
  found double-counted inside the in-scope `security` stanza.
- **The rule-field gap** (R9 → R10): reported as 33 corrections including six missing
  address-group references. All six were present in cycle 010's seed on the correct
  `source_groups`/`destination_groups` relationships — a schema query had filtered out every
  field ending in `groups`, and the comparison then read only the address fields. **14 lines of
  correct data were deleted on that wrong conclusion and restored from git.** The real repair was
  27 corrections.
- **The SC-003 line count** in cycle 022's equivalent, for the same reason: a number asserted
  from reading rather than from running.

The pattern each time was a measurement derived from an incomplete read and stated with more
confidence than it had earned. The tests now pin all three, including
`test_the_oracle_parser_handles_the_bracket_form`, which guards the specific parser bug that
overstated the gap.

## T070 — the Infrahub branch merge was refused, and correctly

The git merge to `main` is clean and pushed. The **Infrahub** branch merge is not, and the
reason is worth keeping.

`infrahubctl branch merge fw-render` reported conflicts. Twenty-one of them, every one the same
shape: `book_index` NULL on base against the transcribed value on the branch,
`log_session_close` False against True. Those are schema defaults on one side and intended
values on the other, so all twenty-one resolved to the branch. The merge still refused.

The CLI's own advice — create a proposed change — produced the real error, in the task worker
rather than at the client:

```text
MergeConstraintsViolatedError: Node-level 'uniqueness_constraints' constraint violation on
schema 'SchemaAttribute' ... field name.value='book_index'
... field name.value='log_session_close'
```

**Both branches already carry both attributes.** `infrahubctl graphql export-schema` has no
`--branch`, so regenerating `schema.graphql` mid-cycle required loading the schema into
Infrahub `main`; that load created the two attributes on `main` independently of the copies the
branch had. Merging would have added a *second* `SchemaAttribute` of each name to the same node,
which the uniqueness constraint exists to refuse. Confirmed against the schema API afterwards:
each attribute is present exactly once on each branch.

So the merge was not merely blocked, it was the wrong operation. `main` needed **no** schema
change from the branch — only the twenty-one object values, which are committed to git. Those
were loaded onto `main` directly with `infrahubctl object load`, which is the path
`invoke load` and any fresh clone already take.

Verified on `main` after the load: 13 of 14 addresses carry a `book_index` (`any` deliberately
does not), 8 of 19 rules carry `log_session_close`, and `infrahubctl transform junos_config
--branch main` renders output identical to the fixture render — the single trailing newline the
CLI adds to stdout is the only difference. The `fw-render` branch is deleted and its proposed
change is closed with this explanation on it.

Two things this did **not** do: the failed merge rolled back on its own, so `main` was never
left half-merged; and nothing was forced past the constraint.

The follow-up this leaves: `export-schema` having no `--branch` is what put the schema on `main`
early, and it will do the same to the next cycle that adds an attribute on a branch. Worth
either a branch-aware export or a convention that the schema load to `main` happens only at
merge time.

## Integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020 to 022.
The constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative that ran: the schema loaded to a real branch, the objects loaded twice
with counts compared, the artifact rendered live through `infrahubctl transform` and diffed
against the device's own file, the target group verified at one member, and the registration
names checked programmatically.
