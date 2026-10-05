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


def test_the_catalogue_declares_seven_entries_and_four_requestable() -> None:
    entries = r.expected_catalogue(REPO)
    assert len(entries) == 7
    assert {n for n, requestable in entries.items() if requestable} == {"whoami", "podinfo", "grafana", "argo-cd"}
    assert not any(n.startswith("lab-") and requestable for n, requestable in entries.items())


def test_triggers_yml_declares_the_group_rules() -> None:
    declared = r.expected_trigger_objects(REPO)
    assert "add-app-access-to-its-generator-group" in declared["CoreGroupAction"]
    assert declared["CoreGroupTriggerRule"]
    assert declared["CoreNodeTriggerRule"]


def test_the_seeded_applications_are_the_three_the_lab_models() -> None:
    assert r.expected_seeded_apps(REPO) == {"otternet-demo", "otternet-metrics", "otternet-telemetry"}


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
    good = "infrahub-lab: http://127.0.0.1:8001/mcp (HTTP) - ✓ Connected\n"
    assert r.decide_claude_mcp_list(good, ["infrahub-lab"]).status is Status.PASS
    bad = "infrahub-lab: x (HTTP) - ✗ Failed to connect\n"
    assert r.decide_claude_mcp_list(bad, ["infrahub-lab"]).status is Status.FAIL
    assert "infrahub-lab is not listed" in r.decide_claude_mcp_list("", ["infrahub-lab"]).detail


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
    assert "infrahub-lab-alice" not in text
    assert "1 PASS" in text


def test_a_read_write_environment_is_checked_before_anything_is_destroyed() -> None:
    assert r.repository_environment_problems({}) == []
    problems = r.repository_environment_problems({"INFRAHUB_REPOSITORY_MODE": "readwrite"})
    assert len(problems) == 3
    complete = {
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
