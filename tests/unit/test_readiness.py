"""`invoke ready`: the decisions, and the wiring that makes a bootstrap end ready.

Two kinds of test. The decisions are held against a passing and a failing input each,
because an empty problem list is only evidence beside a proven non-empty one. The wiring
tests read `tasks.py` and `scripts/verify_bootstrap.sh` as text, because the ordering is
the defect that cost a bootstrap: alice's token cannot be minted before Dex and her
account exist, and `demo-main` must be recreated after the stack is destroyed and before
the repository is registered. None of them needs a running Infrahub.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from solution_arista_avd import readiness as r
from solution_arista_avd.doctor import Result, Status

REPO = Path(__file__).resolve().parents[2]
TASKS = (REPO / "tasks.py").read_text(encoding="utf-8")


def _body(name: str) -> str:
    """The source of the invoke task or helper `name`, up to the next top-level definition."""
    rest = TASKS.split(f"def {name}(", 1)[1]
    end = min(i for i in (rest.find("\n@task"), rest.find("\ndef "), rest.find("\n_cluster_task")) if i != -1)
    return rest[:end]


def _module(path: str):  # noqa: ANN202
    spec = importlib.util.spec_from_file_location(Path(path).stem, REPO / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- what the repository declares


def test_the_catalogue_declares_ten_entries_and_six_requestable() -> None:
    entries = r.expected_catalogue(REPO)
    assert len(entries) == 10
    assert {n for n, requestable in entries.items() if requestable} == {
        "whoami",
        "podinfo",
        "grafana",
        "argo-cd",
        "otternet-shop",
        "otternet-wiki",
    }
    assert not any(n.startswith("lab-") and requestable for n, requestable in entries.items())


def test_triggers_yml_declares_the_group_rules() -> None:
    declared = r.expected_trigger_objects(REPO)
    assert "add-app-access-to-its-generator-group" in declared["CoreGroupAction"]
    assert declared["CoreGroupTriggerRule"]
    assert declared["CoreNodeTriggerRule"]


def test_the_seeded_applications_are_the_four_the_lab_models() -> None:
    assert r.expected_seeded_apps(REPO) == {"otternet-demo", "otternet-metrics", "otternet-telemetry", "otternet-dns"}


# --------------------------------------------------------------------------- decisions


def test_catalogue_passes_and_names_what_is_missing_or_wrongly_requestable() -> None:
    expected = {"whoami": True, "lab-whoami": False}
    assert (
        r.decide_catalogue(expected, {"whoami": (True, "active"), "lab-whoami": (False, "active")}).status
        is Status.PASS
    )
    missing = r.decide_catalogue(expected, {"whoami": (True, "active")})
    assert missing.status is Status.FAIL
    assert "lab-whoami" in missing.detail
    wrong = r.decide_catalogue(expected, {"whoami": (True, "active"), "lab-whoami": (True, "active")})
    assert wrong.status is Status.FAIL
    assert "lab-whoami" in wrong.detail


def test_declared_objects_pass_and_a_missing_group_rule_fails() -> None:
    names = {"CoreGroupAction:add-app-access-to-its-generator-group", "CoreNodeTriggerRule:a"}
    assert r.decide_declared("rules", names, names, "fix").status is Status.PASS
    result = r.decide_declared("rules", names, {"CoreNodeTriggerRule:a"}, "fix")
    assert result.status is Status.FAIL
    assert "add-app-access-to-its-generator-group" in result.detail


def test_a_seeded_application_without_a_pin_fails() -> None:
    assert r.decide_seeded_apps({"a"}, {"a": (True, True)}).status is Status.PASS
    assert r.decide_seeded_apps({"a"}, {"a": (True, False)}).status is Status.FAIL
    assert r.decide_seeded_apps({"a", "b"}, {"a": (True, True)}).status is Status.FAIL


def test_the_mcp_server_must_run_in_token_passthrough_mode() -> None:
    assert r.decide_mcp_server(True, {"status": "healthy", "auth_mode": "token-passthrough"}).status is Status.PASS
    assert r.decide_mcp_server(False, None).status is Status.FAIL
    assert r.decide_mcp_server(True, None).status is Status.FAIL
    assert r.decide_mcp_server(True, {"status": "healthy", "auth_mode": "service-account"}).status is Status.FAIL


def test_a_token_must_authenticate_as_the_expected_account() -> None:
    assert r.decide_identity("x", "alice", "alice", "V", "fix").status is Status.PASS
    assert r.decide_identity("x", "alice", "", "V", "fix").status is Status.FAIL
    wrong = r.decide_identity("x", "alice", "mcp-agent", "V", "fix")
    assert wrong.status is Status.FAIL
    assert "mcp-agent" in wrong.detail


def test_a_script_check_reports_its_problem_lines() -> None:
    assert r.decide_script_check("x", 0, "fine\n", "fix").status is Status.PASS
    failed = r.decide_script_check("x", 1, "PROBLEM: the role does not exist\n", "fix")
    assert failed.status is Status.FAIL
    assert "the role does not exist" in failed.detail


def test_mcp_config_matches_the_variables_in_env() -> None:
    config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    names = {"INFRAHUB_MCP_TOKEN_ALICE"}
    assert r.decide_mcp_config(config, names, ("alice",)).status is Status.PASS
    assert r.decide_mcp_config(config, {"INFRAHUB_MCP_TOKEN"}, ("alice",)).status is Status.FAIL
    # A second server, such as one that sends the mcp-agent token, is refused.
    extra = {
        "mcpServers": {**config["mcpServers"], "other": {"headers": {"Authorization": "Bearer ${INFRAHUB_MCP_TOKEN}"}}}
    }
    refused = r.decide_mcp_config(extra, names, ("alice",))
    assert refused.status is Status.FAIL
    assert "unexpected server 'other'" in refused.detail
    assert r.decide_mcp_config({"mcpServers": {}}, names, ("alice",)).status is Status.FAIL


def test_the_variable_names_the_scripts_write_are_the_ones_mcp_json_reads() -> None:
    user = _module("scripts/provision_mcp_user_token.py")
    config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    headers = {name: entry["headers"]["Authorization"] for name, entry in config["mcpServers"].items()}
    assert list(headers) == [r.MCP_SERVER_NAME]
    assert r.MCP_TOKEN_USERS == ("alice",)
    assert user.token_var("alice") == r.token_var("alice")
    assert headers[r.MCP_SERVER_NAME] == f"Bearer ${{{r.token_var('alice')}}}"


def test_claude_mcp_list_needs_every_server_connected() -> None:
    good = "otternet-infrahub: http://127.0.0.1:8001/mcp (HTTP) - ✓ Connected\n"
    assert r.decide_claude_mcp_list(good, ["otternet-infrahub"]).status is Status.PASS
    bad = "otternet-infrahub: x (HTTP) - ✗ Failed to connect\n"
    assert r.decide_claude_mcp_list(bad, ["otternet-infrahub"]).status is Status.FAIL
    assert "otternet-infrahub is not listed" in r.decide_claude_mcp_list("", ["otternet-infrahub"]).detail


READWRITE = {"kind": "CoreRepository", "default_branch": "demo-main", "sync_status": "in-sync"}


def _repository(**changes: object) -> Result:
    arguments: dict = {
        "expect_readwrite": True,
        "workers": 2,
        "remote_main": "a" * 40,
        "remote_demo_main": "a" * 40,
        "trees_equal": None,
    }
    arguments.update(changes)
    repo = arguments.pop("repo", READWRITE)
    return r.decide_repository(repo, **arguments)


def test_repository_passes_when_read_write_in_sync_and_demo_main_equals_main() -> None:
    assert _repository().status is Status.PASS
    assert _repository(remote_demo_main="b" * 40, trees_equal=True).status is Status.PASS


def test_a_stale_demo_main_is_a_failure() -> None:
    stale = _repository(remote_demo_main="b" * 40, trees_equal=False)
    assert stale.status is Status.FAIL
    assert "differs from main" in stale.detail


def test_repository_fails_on_sync_worker_count_or_a_missing_demo_main() -> None:
    assert _repository(repo={**READWRITE, "sync_status": "error-import"}).status is Status.FAIL
    assert _repository(workers=1).status is Status.FAIL
    assert _repository(remote_demo_main="").status is Status.FAIL


def test_each_repository_problem_names_its_own_fix() -> None:
    one_worker = _repository(workers=1)
    assert "invoke start" in one_worker.fix
    assert "demo-advance" not in one_worker.fix
    stale = _repository(remote_demo_main="b" * 40, trees_equal=False)
    assert "demo-advance" in stale.fix
    assert "invoke start" not in stale.fix


def test_a_read_only_repository_fails_only_where_read_write_was_asked_for() -> None:
    read_only = {"kind": "CoreReadOnlyRepository", "ref": "main", "sync_status": "in-sync"}
    assert _repository(repo=read_only).status is Status.FAIL
    assert _repository(repo=read_only, expect_readwrite=False).status is Status.SKIP


def test_a_leftover_mcp_session_branch_is_reported() -> None:
    assert r.decide_leftover_branches([{"name": "main", "is_default": True}]).status is Status.PASS
    left = r.decide_leftover_branches(
        [{"name": "main", "is_default": True}, {"name": "mcp/session-20261004-4a6021b3", "is_default": False}]
    )
    assert left.status is Status.WARN
    assert "MCP session" in left.detail


def test_a_proposed_change_stuck_in_merging_is_reported_after_the_limit() -> None:
    now = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    def row(minutes_ago: float) -> dict[str, str]:
        return {
            "name": "Release internet access",
            "source_branch": "demo/internet-access-1",
            "updated_at": (now - timedelta(minutes=minutes_ago)).isoformat(),
        }

    assert r.decide_stuck_merges([], now).status is Status.PASS
    # A merge that is running now is not stuck: it takes under two minutes.
    assert r.decide_stuck_merges([row(2)], now).status is Status.PASS
    left = r.decide_stuck_merges([row(r.STUCK_MERGE_MINUTES + 1)], now)
    assert left.status is Status.WARN
    assert "demo/internet-access-1" in left.detail
    assert "invoke start" in left.fix
    assert r.decide_stuck_merges([{"name": "x", "source_branch": "b", "updated_at": "not a time"}], now).status is (
        Status.WARN
    )
    naive = row(60) | {"updated_at": (now - timedelta(minutes=60)).replace(tzinfo=None).isoformat()}
    assert r.decide_stuck_merges([naive], now).status is Status.WARN


def test_the_integration_stack_runs_the_project_image_that_has_pyavd() -> None:
    body = _body("test")
    assert "INFRAHUB_TESTING_DOCKER_IMAGE" in body
    assert "PROJECT_IMAGE" in body
    override = (REPO / "docker-compose.override.yml").read_text(encoding="utf-8")
    assert f"image: {_module('tasks.py').PROJECT_IMAGE}:" in override


def test_the_stuck_merge_check_runs_in_the_readiness_list() -> None:
    assert "stuck merges" in [name for name, _ in r.CHECKS]


def test_a_stage_branch_cut_from_an_old_main_is_stale() -> None:
    assert r.decide_stage_branch("stage/x", True, "a", "a").status is Status.PASS
    assert r.decide_stage_branch("stage/x", True, "a", "b").status is Status.WARN
    assert r.decide_stage_branch("stage/x", False, "", "b").status is Status.SKIP


def test_the_picker_must_list_exactly_the_requestable_entries() -> None:
    wanted = {"whoami", "grafana"}
    assert r.decide_picker({"whoami", "grafana"}, wanted).status is Status.PASS
    assert r.decide_picker({"whoami", "grafana", "lab-metrics"}, wanted).status is Status.FAIL
    assert r.decide_picker(set(), wanted).status is Status.FAIL


def test_a_refused_proposed_change_fails_with_the_refusal() -> None:
    assert r.decide_proposed_change(True, "opened").status is Status.PASS
    assert r.decide_proposed_change(False, "PERMISSION_DENIED").status is Status.FAIL


def test_a_write_to_main_by_alice_fails_the_check() -> None:
    assert r.decide_alice_main_write(False, "refused").status is Status.PASS
    assert r.decide_alice_main_write(True, "created a tag").status is Status.FAIL


def test_a_probe_that_cannot_run_is_a_skip_not_a_crash() -> None:
    def broken(_env: object) -> Result:
        raise RuntimeError("boom")

    results = r.run_checks(REPO, (("x", broken),))
    assert results[0].status is Status.SKIP
    assert "boom" in results[0].detail


def test_the_summary_says_what_a_person_must_do_and_prints_no_token_value() -> None:
    text = r.render_summary([Result("a", Status.PASS, "ok")], REPO)
    assert "set -a; source .env; set +a" in text
    assert "INFRAHUB_MCP_TOKEN_ALICE" in text
    assert "INFRAHUB_MCP_TOKEN," not in text
    assert "otternet-infrahub-alice" not in text
    assert "1 PASS" in text


def test_the_summary_names_the_network_admin_account_and_its_password_variable_but_no_value() -> None:
    text = r.render_summary([Result("a", Status.PASS, "ok")], REPO)
    assert "alex" in text
    assert "INFRAHUB_NETWORK_ADMIN_PASSWORD" in text
    assert "INFRAHUB_NETWORK_ADMIN_PASSWORD=" not in text
    assert "not a Dex sign-in" in text


def test_the_network_admin_check_runs_the_script_check_and_is_registered() -> None:
    assert "network-admin account" in [name for name, _ in r.CHECKS]
    source = (REPO / "src/solution_arista_avd/readiness.py").read_text(encoding="utf-8")
    assert '"provision_network_admin.py"' in source


def test_a_failing_network_admin_check_names_the_fix() -> None:
    failed = r.decide_script_check(
        "x", 1, "PROBLEM: network-admin is in ['Super Administrators']\n", "uv run invoke network-admin"
    )
    assert failed.status is Status.FAIL
    assert failed.fix == "uv run invoke network-admin"


def test_network_admin_is_created_in_bootstrap_after_the_stack_is_loaded() -> None:
    body = _body("bootstrap")
    assert _first(body, "load(ctx)") < _first(body, "network_admin(ctx)") < _first(body, "Bootstrap complete")
    assert _first(body, "mcp_tokens(ctx)") < _first(body, "network_admin(ctx)")
    assert "provision_network_admin.py" in _body("network_admin")


def test_a_read_write_environment_is_checked_before_anything_is_destroyed() -> None:
    assert r.repository_environment_problems({"INFRAHUB_API_TOKEN": "t"}) == []
    problems = r.repository_environment_problems({"INFRAHUB_REPOSITORY_MODE": "readwrite"})
    assert len(problems) == 4
    assert any("INFRAHUB_API_TOKEN" in p for p in r.repository_environment_problems({}))
    complete = {
        "INFRAHUB_API_TOKEN": "t",
        "INFRAHUB_REPOSITORY_MODE": "readwrite",
        "INFRAHUB_REPOSITORY_URL": "https://example.invalid/x.git",
        "NFD_GITHUB_TOKEN": "t",
        "INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES": '["demo/.*"]',
    }
    assert r.repository_environment_problems(complete) == []


# --------------------------------------------------------------------------- the order bootstrap runs things in


def _first(body: str, needle: str) -> int:
    assert needle in body, f"bootstrap does not call {needle}"
    return body.index(needle)


def test_bootstrap_checks_the_read_write_settings_before_it_destroys_anything() -> None:
    body = _body("bootstrap")
    assert _first(body, "_preflight_repository_mode(") < _first(body, "destroy(ctx)")


def test_bootstrap_recreates_demo_main_after_the_teardown_and_before_the_repository_is_loaded() -> None:
    body = _body("bootstrap")
    assert _first(body, "destroy(ctx)") < _first(body, "_recreate_remote_demo_main(") < _first(body, "start(ctx)")
    assert _first(body, "_recreate_remote_demo_main(") < _first(body, "load(ctx)")
    helper = _body("_recreate_remote_demo_main")
    assert "--delete" in helper
    assert helper.index("--delete") < helper.index("FETCH_HEAD:refs/heads")


def test_alice_s_token_is_minted_after_dex_and_the_portal_accounts_exist() -> None:
    body = _body("bootstrap")
    assert _first(body, "tooling(ctx)") < _first(body, "mcp(ctx)") < _first(body, "mcp_tokens(ctx)")
    tokens = _body("mcp_tokens")
    assert _first(tokens, "provision_portal_accounts.py") < _first(tokens, "provision_mcp_user_token.py")
    # `invoke tooling` is what creates the accounts, and it runs Dex's deploy before them.
    tooling = _body("tooling")
    assert _first(tooling, "deploy_tooling.sh") < _first(tooling, "provision_portal_accounts.py")


def test_requester_access_runs_in_bootstrap_through_invoke_mcp_after_the_agent() -> None:
    body = _body("mcp")
    assert _first(body, "provision_mcp_agent.py") < _first(body, "provision_requester_access.py")
    assert _first(_body("bootstrap"), "mcp(ctx)") > 0


def test_bootstrap_ends_with_the_readiness_summary_and_fails_on_a_failed_check() -> None:
    body = _body("bootstrap")
    assert _first(body, "Bootstrap complete") < _first(body, "readiness.run_checks(")
    assert "readiness.render_summary(" in body
    assert "readiness.exit_code(" in body


def test_doctor_runs_the_readiness_checks_too() -> None:
    assert "readiness.run_checks(" in _body("doctor")


def test_mcp_json_has_one_server_for_the_one_token_user() -> None:
    config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    assert list(config["mcpServers"]) == [r.MCP_SERVER_NAME]


def test_verify_bootstrap_runs_the_readiness_checks_and_the_act_smoke() -> None:
    script = (REPO / "scripts/verify_bootstrap.sh").read_text(encoding="utf-8")
    assert "invoke ready" in script
    assert "demo-run --acts one,two" in script
    assert script.index("demo-run --acts one,two") < script.index("invoke demo-restore")
    assert "make -C" in script
    assert "121" in script


# --------------------------------------------------------------------------- a shell that outlived the stack


def test_a_shell_holding_the_old_token_is_found_and_dropped(tmp_path: Path) -> None:
    from solution_arista_avd import envfile

    dotenv = tmp_path / ".env"
    dotenv.write_text("INFRAHUB_PORTAL_TOKEN=new\nINFRAHUB_MCP_TOKEN_ALICE=same\n", encoding="utf-8")
    environ = {
        "INFRAHUB_PORTAL_TOKEN": "old",
        "INFRAHUB_MCP_TOKEN_ALICE": "same",
        "INFRAHUB_EXPORTER_TOKEN": "gone",
        "INFRAHUB_API_TOKEN": "left-alone",
        "PATH": "/usr/bin",
    }
    assert envfile.stale_credentials(environ, dotenv) == ["INFRAHUB_EXPORTER_TOKEN", "INFRAHUB_PORTAL_TOKEN"]
    assert envfile.use_dotenv_credentials(environ, dotenv) == ["INFRAHUB_EXPORTER_TOKEN", "INFRAHUB_PORTAL_TOKEN"]
    assert environ == {"INFRAHUB_MCP_TOKEN_ALICE": "same", "INFRAHUB_API_TOKEN": "left-alone", "PATH": "/usr/bin"}


def test_a_stale_shell_is_a_warning_and_a_clean_one_passes() -> None:
    assert r.decide_shell_environment([]).status is Status.PASS
    stale = r.decide_shell_environment(["INFRAHUB_PORTAL_TOKEN"])
    assert stale.status is Status.WARN
    assert "INFRAHUB_PORTAL_TOKEN" in stale.detail


def test_every_task_that_renders_a_credential_ignores_a_stale_shell_first() -> None:
    for name in ("bootstrap", "tooling", "mcp", "mcp_tokens", "metrics_exporter"):
        assert "_use_dotenv_credentials()" in _body(name), f"{name} would use a stale shell credential"
    assert _first(_body("tooling"), "_use_dotenv_credentials()") < _first(
        _body("tooling"), 'ctx.run("scripts/deploy_tooling.sh"'
    )


def test_bootstrap_builds_the_project_image_before_the_stack_starts() -> None:
    body = _body("bootstrap")
    assert _first(body, "build(ctx)") < _first(body, "start(ctx)")


def test_demo_release_refuses_without_the_api_token_before_it_touches_anything() -> None:
    body = _body("demo_release")
    assert _first(body, 'os.environ.get("INFRAHUB_API_TOKEN")') < _first(body, "dr.stage_branch(")


def test_a_read_write_bootstrap_releases_the_demo_branch_after_refreshing_the_stage_branch() -> None:
    body = _body("bootstrap")
    assert "release: bool = True" in body
    assert _first(body, "_refresh_stage_branch(ctx)") < _first(body, "_release_demo_branch(ctx)")
    assert _first(body, "_release_demo_branch(ctx)") < _first(body, "Bootstrap complete")
    assert "if release:" in body


def test_the_release_step_stages_a_missing_branch_and_reports_a_failure_instead_of_raising() -> None:
    body = _body("_release_demo_branch")
    assert _first(body, "demo_stage(ctx)") < _first(body, "demo_release(ctx)")
    assert "except Exit" in body
    assert "return False" in body


# --------------------------------------------------------------------------- observability namespaces and Secrets

_ALL_SECRETS = {
    "otternet-metrics": {"grafana-admin": {"admin-user", "admin-password"}, "grafana-oidc": {"client-secret"}},
    "otternet-telemetry": {"telemetry-credentials": {"GNMI_USERNAME", "GNMI_PASSWORD"}},
}


def test_the_namespace_check_passes_with_both_and_fails_naming_each_missing_one() -> None:
    assert r.decide_observability_namespaces({"otternet-metrics", "otternet-telemetry", "x"}).status is Status.PASS
    failed = r.decide_observability_namespaces({"otternet-telemetry"})
    assert failed.status is Status.FAIL
    assert "otternet-metrics" in failed.detail
    assert "otternet-telemetry" not in failed.detail
    assert "uv run invoke observability-secrets" in failed.fix


def test_the_secrets_check_passes_with_every_secret_and_key() -> None:
    assert r.decide_observability_secrets(_ALL_SECRETS).status is Status.PASS


def test_the_secrets_check_fails_for_a_missing_secret_a_missing_key_and_a_missing_namespace() -> None:
    no_admin = {**_ALL_SECRETS, "otternet-metrics": {"grafana-oidc": {"client-secret"}}}
    failed = r.decide_observability_secrets(no_admin)
    assert failed.status is Status.FAIL
    assert "otternet-metrics/grafana-admin does not exist" in failed.detail
    assert failed.fix == "uv run invoke observability-secrets"

    no_key = {**_ALL_SECRETS, "otternet-telemetry": {"telemetry-credentials": {"GNMI_USERNAME"}}}
    assert "lacks key(s) GNMI_PASSWORD" in r.decide_observability_secrets(no_key).detail

    nothing = r.decide_observability_secrets({})
    assert nothing.status is Status.FAIL
    assert nothing.detail.count("does not exist") == 3


def test_the_grafana_pod_check_fails_on_create_container_config_error_and_names_the_fix() -> None:
    stuck = r.decide_grafana_pod([("grafana-abc", "Pending", ["CreateContainerConfigError"])])
    assert stuck.status is Status.FAIL
    assert "grafana-abc" in stuck.detail
    assert "CreateContainerConfigError" in stuck.detail
    assert stuck.fix == "uv run invoke observability-secrets"
    assert r.decide_grafana_pod([("grafana-abc", "Running", [])]).status is Status.PASS
    assert r.decide_grafana_pod([("grafana-abc", "Pending", ["ContainerCreating"])]).status is Status.PASS
    assert r.decide_grafana_pod([]).status is Status.WARN


def test_the_new_checks_are_registered_and_a_missing_kubeconfig_skips_them(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    names = [name for name, _ in r.CHECKS]
    for name in ("observability namespaces", "observability Secrets", "Grafana pod"):
        assert name in names
    monkeypatch.setenv("KUBECONFIG", str(tmp_path / "absent.yaml"))
    results = r.run_checks(
        tmp_path, tuple((n, p) for n, p in r.CHECKS if n in ("observability namespaces", "Grafana pod"))
    )
    assert [x.status for x in results] == [Status.SKIP, Status.SKIP]
    assert "no kubeconfig" in results[0].detail


def test_no_probe_reads_a_secret_value() -> None:
    source = (REPO / "src/solution_arista_avd/readiness.py").read_text(encoding="utf-8")
    probe = source.split("def probe_observability_secrets", 1)[1].split("def probe_grafana_pod", 1)[0]
    assert "{{$v}}" not in probe
    assert "-o json" not in probe
    assert "base64" not in probe


def test_the_namespace_error_names_the_namespace_the_wait_the_checks_and_the_fix() -> None:
    message = r.namespace_wait_error(["otternet-metrics"], 600)
    assert "otternet-metrics" in message
    assert "600 s" in message
    for text in ("kubectl get vidraresource", "kubectl get fabricapp", "logs", "uv run invoke observability-secrets"):
        assert text in message
    assert "not known" in message


@dataclass
class _FakeResult:
    ok: bool


class _FakeCtx:
    """Stands in for invoke's Context: records commands and answers `get ns` from a set of namespaces."""

    def __init__(self, namespaces: set[str]) -> None:
        self.namespaces = namespaces
        self.commands: list[str] = []

    def run(self, command: str, **_: object) -> _FakeResult:
        self.commands.append(command)
        if " get ns " in command:
            return _FakeResult(command.split(" get ns ")[1].split(maxsplit=1)[0] in self.namespaces)
        return _FakeResult(True)


def _load_tasks():  # noqa: ANN202
    import sys

    sys.path.insert(0, str(REPO))
    try:
        return _module("tasks.py")
    finally:
        sys.path.remove(str(REPO))


def test_the_secrets_step_exits_1_naming_the_namespace_when_one_never_appears(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    import pytest
    from invoke import Exit

    tasks = _load_tasks()
    monkeypatch.setattr(tasks, "_ensure_env_value", lambda *_: "not-a-real-password")
    monkeypatch.setattr(tasks, "sleep", lambda _: None)
    ctx = _FakeCtx({"otternet-telemetry"})
    with pytest.raises(Exit) as raised:
        tasks._observability_secrets(ctx, tmp_path / "kubeconfig", 1)
    assert raised.value.code == 1
    assert "otternet-metrics" in str(raised.value.message)
    assert "uv run invoke observability-secrets" in str(raised.value.message)
    applied = [c for c in ctx.commands if " apply -f " in c]
    assert len(applied) == 1  # telemetry-credentials was still applied; the metrics Secrets were not
    assert "not-a-real-password" not in " ".join(ctx.commands)


def test_the_secrets_step_applies_all_three_and_returns_when_both_namespaces_exist(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    tasks = _load_tasks()
    monkeypatch.setattr(tasks, "_ensure_env_value", lambda *_: "not-a-real-password")
    ctx = _FakeCtx({"otternet-metrics", "otternet-telemetry"})
    tasks._observability_secrets(ctx, tmp_path / "kubeconfig", 1)
    assert len([c for c in ctx.commands if " apply -f " in c]) == 3
    assert "not-a-real-password" not in " ".join(ctx.commands)


def test_the_cluster_task_runs_the_secrets_step_before_waiting_and_the_standalone_task_runs_it_alone() -> None:
    cluster = _body("cluster")
    assert _first(cluster, "_observability_secrets(") < _first(cluster, "_wait_for_observability(")
    alone = _body("observability_secrets")
    assert "_observability_secrets(" in alone
    for other in ("install-cilium", "install_vidra", "install-crossplane"):
        assert other not in alone
