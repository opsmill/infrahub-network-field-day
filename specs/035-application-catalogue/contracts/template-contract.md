# Contract: portal template `exposed-app-with-access-request`

Asserted by `tests/unit/test_combined_app_template_contract.py` (extended) and `tests/unit/test_application_catalogue_portal.py`.

Form (page one) keeps: `app_name`, `description`, `namespace_name`, `cluster`, `vrf`, `owner`, and gains `application` (entity picker).
Form removes: `chart_repository`, `chart_name`, `chart_version`, `advertised_services`, `service_selector`, `vip_block_size`, `values_file_content`.
Form (page two) is unchanged.

Picker: `ui:field: EntityPicker`, `catalogFilter: { kind: Resource, spec.type: application-definition, metadata.tags: requestable }` (one tag, because Backstage ORs the values of one key; the provider emits `requestable` only for an entry that is requestable AND active), `allowArbitraryValues: false`.

Steps in order: `fetch_definition` (`catalog:fetch`) -> `branch` -> `read_definition` (GraphQL read on the request branch, so no step runs on `main` and the existing every-step-names-its-branch contract is untouched with `requestable__value: true` and `status__value: "active"`; its required-variable use makes the run stop when the entry is not offered) -> `create_app` (sends the entry's chart fields, block size and selector, and the `definition` relationship; the advertised services are NOT sent, because the scaffolder cannot template a list out of a relationship read, so the generator fills them from the entry when the request left them empty) -> `await_app` -> `read_app` -> `assert_vip` -> `create_grant` -> `await_grant` -> the AVD regeneration steps -> `proposed_change`. No `values` upload step.

Unchanged: `exposed: true`, the hfid fields, `member_of_groups`, grant inputs in the create, every existing step order assertion.
