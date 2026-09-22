"""The curated two-for-one template is hand-written, so the schema can leave it behind.

`backstage/catalog/exposed-app-with-access.yaml` creates a `ServiceFabricApp`
and a `ServiceAppAccess` with mutation text written by hand. The generated
templates re-derive their fields from the Infrahub schema on every sync and
cannot drift; this one can, and the failure is quiet in the worst way -- a
renamed attribute fails at request time, in the portal, for a branch user.

So this asserts the template against the schema it was written from:

- every field the mutations name still exists on that kind, and
- every field mandatory on create is either sent or has a schema default, and
- the groups it joins exist, because a service outside its generator's group is
  created and then silently never expanded, and
- the file is registered in BOTH app-configs and COPYed into the image.

That last one is not pedantry. `app-config.docker.yaml` REPLACES the dev
`catalog.locations` list rather than extending it, and the Dockerfile COPYs only
`examples` and `app-config*.yaml` -- so a template that works locally can be
absent in the lab with nothing logged anywhere.

**Inherited fields are the subtle half.** Neither kind's own file declares
`name`, `owner` or `status`: they come from `ServiceGeneric` in service.yml. A
check that reads only the two kind files passes while missing exactly the fields
most likely to be forgotten, so the generic is resolved here too.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "backstage/catalog/exposed-app-with-access.yaml"
DEV_CONFIG = REPO / "backstage/app-config.yaml"
DOCKER_CONFIG = REPO / "backstage/app-config.docker.yaml"
DOCKERFILE = REPO / "backstage/packages/backend/Dockerfile"
GROUPS = REPO / "objects/00_groups.yml"

SCHEMA_FILES = [
    REPO / "schemas/service/service.yml",
    REPO / "schemas/service/kubernetes_services.yml",
    REPO / "schemas/service/access_services.yml",
]

# The two creates, by the mutation name they use.
CREATES = {
    "ServiceFabricAppCreate": ("Service", "FabricApp"),
    "ServiceAppAccessCreate": ("Service", "AppAccess"),
}

# Fields the mutation sets that are not schema fields of the kind.
NOT_A_FIELD = {"member_of_groups"}


def _load_schema() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return ({name: node}, {name: generic}) keyed by the schema's own `name`."""
    nodes: dict[str, dict[str, Any]] = {}
    generics: dict[str, dict[str, Any]] = {}
    for path in SCHEMA_FILES:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for node in document.get("nodes") or []:
            nodes[f"{node.get('namespace', '')}{node['name']}"] = node
        for generic in document.get("generics") or []:
            generics[f"{generic.get('namespace', '')}{generic['name']}"] = generic
    return nodes, generics


def _fields_of(kind: dict[str, Any], generics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every attribute and relationship of a kind, its own and inherited."""
    fields: dict[str, dict[str, Any]] = {}
    for parent in kind.get("inherit_from") or []:
        if parent in generics:
            fields.update(_fields_of(generics[parent], generics))
    for group in ("attributes", "relationships"):
        for field in kind.get(group) or []:
            fields[field["name"]] = field
    return fields


def _mutation_fields(text: str, mutation: str) -> set[str]:
    """The field names inside one mutation's `data: { ... }` block."""
    start = text.index(mutation)
    data = text.index("data: {", start)
    depth, index = 0, data + len("data: {") - 1
    for index in range(data + len("data: {") - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                break
    block = text[data : index + 1]
    # `  name: { value: $name }` / `  cluster: { hfid: [$cluster] }` — a field is
    # a key at the start of a line inside the block.
    return set(re.findall(r"^\s{14,}(\w+):", block, re.MULTILINE))


@pytest.fixture(scope="module")
def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    return _load_schema()


@pytest.mark.parametrize("mutation,kind_key", list(CREATES.items()))
def test_every_field_the_mutation_sends_still_exists(
    template_text: str,
    schema: tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]],
    mutation: str,
    kind_key: tuple[str, str],
) -> None:
    nodes, generics = schema
    kind = nodes["".join(kind_key)]
    known = _fields_of(kind, generics)

    sent = _mutation_fields(template_text, mutation) - NOT_A_FIELD
    unknown = sorted(name for name in sent if name not in known)

    assert not unknown, (
        f"{mutation} sets {unknown}, which {''.join(kind_key)} no longer has. "
        "A hand-written template does not re-derive its fields, so this fails at "
        "request time in the portal rather than here."
    )


@pytest.mark.parametrize("mutation,kind_key", list(CREATES.items()))
def test_every_mandatory_field_is_sent_or_defaulted(
    template_text: str,
    schema: tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]],
    mutation: str,
    kind_key: tuple[str, str],
) -> None:
    nodes, generics = schema
    kind = nodes["".join(kind_key)]
    known = _fields_of(kind, generics)
    sent = _mutation_fields(template_text, mutation)

    missing = sorted(
        name
        for name, field in known.items()
        if field.get("optional") is False and "default_value" not in field and name not in sent
    )

    assert not missing, (
        f"{mutation} omits mandatory field(s) {missing}. Infrahub refuses the whole "
        "create, so the requester gets a branch and nothing in it."
    )


def test_the_grant_supplies_its_generator_inputs_in_the_create(template_text: str) -> None:
    """The ordering rule that a follow-up update step would break.

    `generate-app-access` fires on `created`, so anything it reads has to be in
    the create mutation. A source set by a later step arrives after the run that
    needed it, and the grant is stamped `error` and never retried.
    """
    sent = _mutation_fields(template_text, "ServiceAppAccessCreate")
    for field in ("application", "source_site"):
        assert field in sent, (
            f"the grant's create must carry {field!r}: its generator fires on creation, "
            "so a value set afterwards is too late and cannot be retried"
        )


def test_the_application_is_created_exposed(template_text: str) -> None:
    """An unexposed application never gets a VIP block, and the grant then refuses."""
    assert "exposed: { value: $exposed }" in template_text
    assert re.search(r"^\s+exposed:\s*true\s*$", template_text, re.MULTILINE), (
        "`exposed` must be pinned true: generate-fabric-app allocates a block only "
        "for an exposed application, and generate-app-access refuses a grant to an "
        "application with no block"
    )


def test_the_barrier_sits_between_the_two_creates(template: dict[str, Any]) -> None:
    """The whole design: the grant is created after the app's generators are quiet."""
    ids = [step["id"] for step in template["spec"]["steps"]]
    for step in ("create_app", "await_app", "assert_vip", "create_grant"):
        assert step in ids, f"step {step!r} is missing"
    assert ids.index("create_app") < ids.index("await_app") < ids.index("create_grant"), (
        "the grant must be created after the application's generators have run, or it "
        "races the VIP allocation it depends on"
    )
    assert ids.index("assert_vip") < ids.index("create_grant"), (
        "the VIP assertion must run before the grant: the await can report success having waited for nothing"
    )


def test_the_fabric_is_regenerated_before_the_proposed_change(template: dict[str, Any]) -> None:
    """The grant writes fabric intent that nothing else regenerates.

    `generate-app-access` appends a `permit <vip>/32` to the border leaf's
    `avd_custom_hostvars`. `generate-avd-device-hostvar` runs on no trigger and
    is `execute_in_proposed_change: false`, so without these steps the proposed
    change shows a changed JSON blob and no configuration -- the reviewer
    approves a consequence they cannot see.

    Order is load bearing in both directions: after the grant, because the
    hostvars must pick up what its generator wrote; before the proposed change,
    because that is the point.
    """
    ids = [step["id"] for step in template["spec"]["steps"]]
    for step in ("lookup_avd", "run_avd_hostvars", "run_avd_structured_config"):
        assert step in ids, f"step {step!r} is missing; the branch would carry unrendered fabric intent"

    assert ids.index("await_grant") < ids.index("run_avd_hostvars"), (
        "the host vars must be regenerated after the grant's generator has written "
        "avd_custom_hostvars, or they regenerate from data that predates the request"
    )
    assert ids.index("run_avd_hostvars") < ids.index("run_avd_structured_config"), (
        "structured config reads the STORED hostvar files, so it must run after them"
    )
    assert ids.index("run_avd_structured_config") < ids.index("proposed_change"), (
        "the fabric must be regenerated before the proposed change opens"
    )


def test_the_avd_runs_cover_every_device_and_block(template: dict[str, Any]) -> None:
    """`nodes` omitted means the whole target group; the wait is what makes it done."""
    by_id = {step["id"]: step for step in template["spec"]["steps"]}
    for step_id in ("run_avd_hostvars", "run_avd_structured_config"):
        query = by_id[step_id]["input"]["query"]
        assert "wait_until_completion: true" in query, (
            f"{step_id} must block: without it the proposed change opens while the generators are still running"
        )
        assert "nodes" not in query, (
            f"{step_id} must omit `nodes` so the definition runs across its whole "
            "target group rather than a single device"
        )


def test_every_infrahub_step_names_the_branch(template: dict[str, Any]) -> None:
    """A step with no branch runs on main, where none of this exists.

    The two exceptions are deliberate: the branch is created on main, and a
    proposed change is an object on main that names the branch.
    """
    on_main = {"branch", "proposed_change", "catalog"}
    for step in template["spec"]["steps"]:
        if step["id"] in on_main:
            continue
        if not step["action"].startswith("infrahub:"):
            continue
        assert "branch" in (step.get("input") or {}), (
            f"step {step['id']!r} does not name the branch, so it would run against main"
        )


def test_both_groups_exist(template_text: str) -> None:
    """A service outside its generator's group is created and never expanded."""
    # objects/00_groups.yml is a multi-document file, one document per group kind.
    declared = {
        entry["name"]
        for document in yaml.safe_load_all(GROUPS.read_text(encoding="utf-8"))
        if isinstance(document, dict)
        for entry in ((document.get("spec") or {}).get("data") or [])
        if isinstance(entry, dict) and "name" in entry
    }
    named = set(re.findall(r'member_of_groups: \[\{ hfid: \["([^"]+)"\] \}\]', template_text))
    assert named, "the template joins no group; nothing would ever expand either object"
    missing = sorted(name for name in named if declared and name not in declared)
    assert not missing, f"the template joins group(s) {missing} that objects/00_groups.yml does not declare"


def test_the_template_is_registered_where_the_lab_reads_it() -> None:
    """Registered in dev only, it works on a laptop and is absent in the lab.

    `app-config.docker.yaml` replaces the dev `catalog.locations` rather than
    extending it, and the deployed portal runs with both files.
    """
    assert "catalog/exposed-app-with-access.yaml" in DEV_CONFIG.read_text(encoding="utf-8"), (
        "not registered in app-config.yaml"
    )
    assert "catalog/exposed-app-with-access.yaml" in DOCKER_CONFIG.read_text(encoding="utf-8"), (
        "not registered in app-config.docker.yaml, which REPLACES the dev locations "
        "and is the list the deployed portal reads"
    )


def test_the_catalog_directory_reaches_the_image() -> None:
    """The Dockerfile COPYs named paths; a new directory is silently absent."""
    assert re.search(r"^COPY .*catalog \./catalog$", DOCKERFILE.read_text(encoding="utf-8"), re.MULTILINE), (
        "backstage/packages/backend/Dockerfile does not COPY the catalog directory, so "
        "app-config.docker.yaml would point at a path that does not exist in the image"
    )
