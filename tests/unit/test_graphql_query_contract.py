"""Repo-wide contract on the `.gql` queries.

**One rule, and it was learned the expensive way.** A selection set that carries
an inline fragment must also select `__typename`.

`infrahubctl graphql generate-return-types` renders any such selection set as a
pydantic *discriminated union*, keyed on `__typename`. If the query does not ask
for the field, nothing complains at generation time -- the model is produced,
imports cleanly, and type-checks. It fails at run time, on the first real
response, with::

    Unable to extract tag using discriminator 'typename__' | '__typename'

and it fails for **every** node in that collection at once, so a generator dies
before its first write with an error naming no file and no query.

**A unit test cannot catch it, which is why this one is structural.** Fixtures
are written by hand from the generated model, and the model *has* the field --
so a fixture supplies `__typename` and is more correct than the query it stands
in for. Every test passes while the query is broken. That is exactly how
`generate_network_segment.gql` shipped: 30 passing tests, and it could not parse
a single pool.

This test reads the queries themselves with a real GraphQL parser rather than
line matching, because the field is often written inline on the same line as the
brace that opens its selection set.
"""

from __future__ import annotations

from pathlib import Path

import graphql
import pytest

REPO_ROOT = Path(__file__).parents[2]

# Directories that are ours to hold to this rule. Vendored and worktree copies
# are excluded: they are not edited here, and a failure in one would report a
# defect nobody in this repository can fix.
SEARCHED = ("checks", "generators", "transforms", "queries")

# The one query whose model is NOT generated, and so cannot grow a discriminated
# union to be wrong about. `containerlab_topology_query.py` is hand-written and
# lean on purpose -- its docstring says so -- modelling only the attributes the
# transform traverses, and Pydantic v2 ignores the rest.
#
# The exemption is VERIFIED rather than asserted, by
# `test_the_exempt_query_really_does_have_a_hand_written_model` below. An
# allowlist nobody checks is how a rule quietly stops applying.
HAND_WRITTEN_MODELS = {
    "transforms/containerlab_topology.gql": REPO_ROOT / "transforms/containerlab_topology_query.py",
}

DISCRIMINATOR = 'discriminator="typename__"'


def _queries() -> list[Path]:
    found: list[Path] = []
    for directory in SEARCHED:
        found.extend(sorted((REPO_ROOT / directory).glob("**/*.gql")))
    return found


def _offences(document: graphql.DocumentNode) -> list[str]:
    """Every selection set holding an inline fragment but not `__typename`."""
    offences: list[str] = []

    def walk(selection_set: graphql.SelectionSetNode | None, path: str) -> None:
        if selection_set is None:
            return
        fields = {
            selection.name.value for selection in selection_set.selections if isinstance(selection, graphql.FieldNode)
        }
        fragments = [
            selection for selection in selection_set.selections if isinstance(selection, graphql.InlineFragmentNode)
        ]
        if fragments and "__typename" not in fields:
            kinds = ", ".join(
                fragment.type_condition.name.value for fragment in fragments if fragment.type_condition is not None
            )
            offences.append(f"{path} (fragments on: {kinds})")

        for selection in selection_set.selections:
            if isinstance(selection, graphql.FieldNode):
                walk(selection.selection_set, f"{path}.{selection.name.value}")
            elif isinstance(selection, graphql.InlineFragmentNode):
                condition = selection.type_condition.name.value if selection.type_condition else "?"
                walk(selection.selection_set, f"{path}[{condition}]")

    for definition in document.definitions:
        if isinstance(definition, graphql.OperationDefinitionNode):
            walk(definition.selection_set, definition.name.value if definition.name else "query")
    return offences


def test_there_are_queries_to_check() -> None:
    """Without this, the parametrised test below passes over an empty set and
    reports success for a rule it never applied."""
    assert len(_queries()) > 20


@pytest.mark.parametrize("path", _queries(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_every_inline_fragment_has_a_discriminator(path: Path) -> None:
    """The whole failure class, asserted once per query."""
    if str(path.relative_to(REPO_ROOT)) in HAND_WRITTEN_MODELS:
        pytest.skip("model is hand-written; see HAND_WRITTEN_MODELS")
    offences = _offences(graphql.parse(path.read_text(encoding="utf-8")))
    assert not offences, (
        f"{path.relative_to(REPO_ROOT)} selects an inline fragment without __typename at:\n"
        + "\n".join(f"  {offence}" for offence in offences)
        + "\n\nThe generated model makes that a discriminated union keyed on __typename, so every "
        "node in the collection fails to parse at run time. Add `__typename` to the selection set."
    )


def _inline_fragments(document: graphql.DocumentNode) -> int:
    count = 0
    stack: list[graphql.SelectionSetNode] = [
        definition.selection_set
        for definition in document.definitions
        if isinstance(definition, graphql.OperationDefinitionNode)
    ]
    while stack:
        selection_set = stack.pop()
        for selection in selection_set.selections:
            if isinstance(selection, graphql.InlineFragmentNode):
                count += 1
            child = getattr(selection, "selection_set", None)
            if child is not None:
                stack.append(child)
    return count


def test_at_least_one_query_actually_uses_inline_fragments() -> None:
    """Proves the rule has something to bite on.

    A structural test over a corpus with no inline fragments anywhere would pass
    forever while asserting nothing.
    """
    total = sum(_inline_fragments(graphql.parse(path.read_text(encoding="utf-8"))) for path in _queries())
    assert total > 0, "no query uses an inline fragment, so the rule above is vacuous"


@pytest.mark.parametrize(("query", "model"), sorted(HAND_WRITTEN_MODELS.items()))
def test_the_exempt_query_really_does_have_a_hand_written_model(query: str, model: Path) -> None:
    """Keeps the exemption honest.

    If this model is ever replaced by a generated one it WILL carry discriminated
    unions, and the query it was exempted from would then be wrong in exactly the
    way the rule exists to catch -- silently, because the skip above would go on
    skipping. So the exemption asserts the property it depends on.
    """
    assert model.is_file(), f"{query} is exempted against a model that does not exist"
    assert DISCRIMINATOR not in model.read_text(encoding="utf-8"), (
        f"{model.name} now contains a discriminated union, so {query} is no longer exempt: "
        "remove it from HAND_WRITTEN_MODELS and add __typename wherever it uses an inline fragment"
    )
