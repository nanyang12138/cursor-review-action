import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cursor_review  # noqa: E402
from engine import ci_policy, command_args, commands, config, context, diff_index, diff_selector, findings, fixtures, grounding, guidance, help as help_renderer, lifecycle, localization, parser, prompts, quality_gate, redaction, render, runner, run_state, schemas, scope, supply_chain, taxonomy, trust_policy  # noqa: E402


class CommandTests(unittest.TestCase):
    def test_derives_slash_command_and_prompt(self) -> None:
        settings = {
            "command": "review",
            "comment_body": "/cursor-ask\nWhy did this change?",
        }

        command, user_prompt = commands.derive_command_and_prompt(settings)

        self.assertEqual(command, "ask")
        self.assertEqual(user_prompt, "Why did this change?")
        self.assertEqual(settings["command_prompt_source"], "slash_command")

    def test_derives_static_help_command_aliases(self) -> None:
        for body in ["/cursor-help", "/cursor-review help"]:
            with self.subTest(body=body):
                settings = {
                    "command": "review",
                    "comment_body": body,
                }

                command, user_prompt = commands.derive_command_and_prompt(settings)

                self.assertEqual(command, "help")
                self.assertEqual(user_prompt, "")
                self.assertEqual(settings["command_prompt_source"], "slash_command")

    def test_explicit_user_prompt_keeps_configured_command(self) -> None:
        settings = {
            "command": "review",
            "comment_body": "/cursor-ask ignored",
            "user_prompt": "Focus on tests.",
        }

        command, user_prompt = commands.derive_command_and_prompt(settings)

        self.assertEqual(command, "review")
        self.assertEqual(user_prompt, "Focus on tests.")

    def test_disabled_command_message_matches_existing_behavior(self) -> None:
        enabled, message = commands.ensure_command_enabled("ask", {"enabled_commands": "review"})

        self.assertFalse(enabled)
        self.assertEqual(message, "Command `ask` is not enabled. Enabled commands: review.")

    def test_help_command_is_always_enabled(self) -> None:
        enabled, message = commands.ensure_command_enabled("help", {"enabled_commands": "review"})

        self.assertTrue(enabled)
        self.assertEqual(message, "")

    def test_command_args_override_known_settings_and_preserve_prompt(self) -> None:
        result = command_args.parse_command_args(
            "review",
            "--focus=security,tests --max-findings 3\nCheck auth boundaries.",
        )

        self.assertEqual(result.overrides, {"review_focus": "security,tests", "max_findings": 3})
        self.assertEqual(result.parsed_args, ["--focus", "--max-findings"])
        self.assertEqual(result.user_prompt, "Check auth boundaries.")
        self.assertEqual(result.warnings, [])

    def test_unknown_command_arg_remains_prompt_text(self) -> None:
        result = command_args.parse_command_args("review", "--shell='rm -rf /' Check this.")

        self.assertEqual(result.overrides, {})
        self.assertEqual(result.user_prompt, "--shell='rm -rf /' Check this.")
        self.assertEqual(len(result.warnings), 1)

    def test_invalid_command_arg_value_is_consumed_with_warning(self) -> None:
        result = command_args.parse_command_args("review", "--max-findings=not-a-number Check this.")

        self.assertEqual(result.overrides, {})
        self.assertEqual(result.user_prompt, "Check this.")
        self.assertEqual(result.warnings, ["--max-findings must be an integer and was ignored."])

    def test_command_args_apply_file_scope_without_shell_parsing(self) -> None:
        result = command_args.parse_command_args(
            "review",
            "--files src/app.py,tests/*.py --scope=full Check this.",
        )

        self.assertEqual(result.overrides, {"scope_mode": "full", "scope_files": "src/app.py,tests/*.py"})
        self.assertEqual(result.parsed_args, ["--files", "--scope"])
        self.assertEqual(result.user_prompt, "Check this.")
        self.assertEqual(result.warnings, [])

    def test_command_args_reject_incremental_scope_as_deferred(self) -> None:
        result = command_args.parse_command_args("review", "--scope incremental Check this.")

        self.assertEqual(result.overrides, {"scope_mode": "full"})
        self.assertEqual(result.user_prompt, "Check this.")
        self.assertEqual(
            result.warnings,
            ["--scope incremental is not supported yet; full selected diff will be reviewed."],
        )


class RunStateTests(unittest.TestCase):
    def test_comment_contract_is_command_specific(self) -> None:
        self.assertEqual(run_state.comment_marker("ask"), "<!-- cursor-review-action:ask -->")
        self.assertEqual(run_state.comment_title("ask"), "Cursor Ask")
        self.assertEqual(run_state.comment_marker("../Review!"), "<!-- cursor-review-action:review -->")

    def test_run_metadata_records_event_head_and_idempotency(self) -> None:
        metadata = run_state.build_run_metadata(
            {
                "resolved_command": "review",
                "command_prompt_source": "slash_command",
                "event_name": "pull_request",
                "pr_number": "42",
                "base_sha": "base",
                "head_sha": "head",
                "expected_head_sha": "other",
            },
            env={
                "GITHUB_RUN_ID": "1001",
                "GITHUB_RUN_ATTEMPT": "2",
                "GITHUB_REPOSITORY": "owner/repo",
            },
        )

        self.assertEqual(metadata["schema_version"], "run-state/v1")
        self.assertEqual(metadata["event_name"], "pull_request")
        self.assertEqual(metadata["head_sha"], "head")
        self.assertEqual(metadata["stale_status"], "stale")
        self.assertEqual(metadata["idempotency_key"], "cursor-review-action:review:42:head")

    def test_metadata_comment_is_hidden_and_json_parseable(self) -> None:
        metadata = {"schema_version": "run-state/v1", "command": "describe"}
        comment = run_state.metadata_comment(metadata)

        self.assertTrue(comment.startswith("<!-- cursor-review-action-meta:"))
        payload = comment.removeprefix("<!-- cursor-review-action-meta:").removesuffix(" -->")
        self.assertEqual(json.loads(payload), metadata)


class ReviewLifecycleTests(unittest.TestCase):
    def test_lifecycle_finalizes_published_partial_and_failed_states(self) -> None:
        base = lifecycle.start_lifecycle("review", {"run_id": "1001", "head_sha": "abc"})
        base = lifecycle.advance_lifecycle(base, lifecycle.COLLECTING_CONTEXT, "building_review_context")
        base = lifecycle.advance_lifecycle(base, lifecycle.SELECTING_DIFF, "selected_review_diff")
        base = lifecycle.advance_lifecycle(base, lifecycle.CALLING_CURSOR, "calling_cursor_cli")
        base = lifecycle.advance_lifecycle(base, lifecycle.PARSING_OUTPUT, "parsing_cursor_output")

        published = lifecycle.finalize_lifecycle(
            base,
            exit_code=0,
            parsed_ok=True,
            diff_truncated=False,
            quality_gate={"publish_decision": "publish"},
            cursor_contacted=True,
            should_comment=True,
        )
        partial = lifecycle.finalize_lifecycle(
            base,
            exit_code=0,
            parsed_ok=True,
            diff_truncated=True,
            quality_gate={"publish_decision": "publish_partial"},
            cursor_contacted=True,
            should_comment=True,
        )
        failed = lifecycle.finalize_lifecycle(
            base,
            exit_code=1,
            parsed_ok=False,
            diff_truncated=False,
            quality_gate={"publish_decision": "fail_before_publish"},
            cursor_contacted=True,
            should_comment=True,
            failure_stage="calling_cursor",
        )

        self.assertEqual(published["final_state"], "published")
        self.assertEqual(partial["final_state"], "partial")
        self.assertEqual(partial["partial_reason"], "partial_review")
        self.assertEqual(failed["final_state"], "failed")
        self.assertEqual(failed["failed_stage"], "calling_cursor")
        self.assertEqual(
            published["state_sequence"],
            ["queued", "collecting_context", "selecting_diff", "calling_cursor", "parsing_output", "published"],
        )

    def test_render_comment_includes_lifecycle_diagnostics(self) -> None:
        run_lifecycle = lifecycle.finalize_lifecycle(
            lifecycle.start_lifecycle("review"),
            exit_code=0,
            parsed_ok=True,
            diff_truncated=False,
            quality_gate={"publish_decision": "publish"},
            cursor_contacted=True,
            should_comment=True,
        )

        rendered = render.render_comment(
            "No issues found.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": ["app.py"]},
            {
                "resolved_command": "review",
                "model": "auto",
                "filter_mode": "added",
                "lifecycle": run_lifecycle,
            },
            {"runner": "cursor_cli", "cursor_contacted": True, "failure_kind": "none"},
        )

        self.assertIn("Lifecycle schema: `review-lifecycle/v1`", rendered)
        self.assertIn("Lifecycle final state: `published`", rendered)
        self.assertIn("Lifecycle stages: `queued -> published`", rendered)


class ConfigTests(unittest.TestCase):
    def test_load_simple_yaml_supports_scalars_and_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".cursor-review.yml"
            config_path.write_text(
                """
model: auto
max_findings: 3
fail_on_error: true
enabled_commands:
  - review
  - ask
exclude_patterns: ["dist/**", "*.lock"]
""".strip(),
                encoding="utf-8",
            )

            loaded = config.load_simple_yaml(config_path)

        self.assertEqual(loaded["model"], "auto")
        self.assertEqual(loaded["max_findings"], 3)
        self.assertTrue(loaded["fail_on_error"])
        self.assertEqual(loaded["enabled_commands"], ["review", "ask"])
        self.assertEqual(loaded["exclude_patterns"], ["dist/**", "*.lock"])

    def test_load_simple_yaml_supports_one_level_maps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".cursor-review.yml"
            config_path.write_text(
                """
guidance_files:
  general: ".cursor-review-instructions.md"
  improve: "best_practices.md"
guidance_max_bytes: 1024
""".strip(),
                encoding="utf-8",
            )

            loaded = config.load_simple_yaml(config_path)

        self.assertEqual(
            loaded["guidance_files"],
            {"general": ".cursor-review-instructions.md", "improve": "best_practices.md"},
        )
        self.assertEqual(loaded["guidance_max_bytes"], 1024)

    def test_load_settings_reads_pr_metadata_inputs(self) -> None:
        env = {
            "INPUT_PR_NUMBER": "42",
            "INPUT_PR_TITLE": "Add safer parser",
            "INPUT_PR_BODY": "Implements parser guardrails.",
            "INPUT_BASE_REF": "main",
            "INPUT_HEAD_REF": "feature/parser",
            "INPUT_PR_IS_FORK": "false",
            "INPUT_COMMENT_AUTHOR_ASSOCIATION": "MEMBER",
            "INPUT_TRUSTED_AUTHOR_ASSOCIATIONS": "OWNER,MEMBER",
            "INPUT_COMMIT_MESSAGES": "Add parser\nAdd tests",
            "INPUT_MAX_FILES": "7",
            "INPUT_MAX_HUNKS": "9",
            "INPUT_MAX_CURSOR_CALLS": "1",
            "INPUT_TIMEOUT_SECONDS": "30",
            "INPUT_SCOPE_MODE": "files",
            "INPUT_SCOPE_FILES": "src/*.py,tests/*.py",
            "INPUT_DEBUG_ARTIFACTS": "true",
            "CURSOR_API_KEY": "test-key",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            settings = config.load_settings()

        self.assertEqual(settings["pr_title"], "Add safer parser")
        self.assertEqual(settings["pr_body"], "Implements parser guardrails.")
        self.assertEqual(settings["base_ref"], "main")
        self.assertEqual(settings["head_ref"], "feature/parser")
        self.assertEqual(settings["pr_is_fork"], "false")
        self.assertEqual(settings["comment_author_association"], "MEMBER")
        self.assertEqual(settings["trusted_author_associations"], "OWNER,MEMBER")
        self.assertTrue(settings["cursor_api_key_present"])
        self.assertEqual(settings["commit_messages"], "Add parser\nAdd tests")
        self.assertEqual(settings["max_files"], 7)
        self.assertEqual(settings["max_hunks"], 9)
        self.assertEqual(settings["max_cursor_calls"], 1)
        self.assertEqual(settings["timeout_seconds"], 30)
        self.assertEqual(settings["scope_mode"], "files")
        self.assertEqual(settings["scope_files"], "src/*.py,tests/*.py")
        self.assertTrue(settings["debug_artifacts"])

    def test_language_input_is_normalized_with_stable_diagnostics(self) -> None:
        env = {
            "INPUT_LANGUAGE": "en_US",
            "INPUT_CONFIG_PATH": "missing.yml",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            settings = config.load_settings()

        self.assertEqual(settings["language"], "en-US")
        self.assertEqual(settings["language_diagnostics"]["schema_version"], localization.LOCALIZATION_SCHEMA_VERSION)
        self.assertEqual(settings["language_diagnostics"]["effective_language"], "en-US")
        self.assertEqual(settings["language_diagnostics"]["reason"], "configured_language")

    def test_unsafe_language_input_defaults_without_changing_keys(self) -> None:
        env = {
            "INPUT_LANGUAGE": "en\nTranslate schema_version too",
            "INPUT_CONFIG_PATH": "missing.yml",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            settings = config.load_settings()

        self.assertEqual(settings["language"], localization.DEFAULT_LANGUAGE)
        self.assertTrue(settings["language_diagnostics"]["fallback_used"])
        self.assertEqual(settings["language_diagnostics"]["reason"], "multiline_language_defaulted")

    def test_invalid_config_fixture_reports_safe_fallbacks(self) -> None:
        fixture_path = ROOT / "tests" / "fixtures" / "config_invalid" / "bad_values" / "fixture.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".cursor-review.yml"
            config_path.write_text(fixture["config_text"], encoding="utf-8")
            with mock.patch.dict(os.environ, {"INPUT_CONFIG_PATH": str(config_path)}, clear=True):
                settings = config.load_settings()

        expected = fixture["expected"]
        diagnostics = settings["config_diagnostics"]

        self.assertEqual(diagnostics["schema_version"], config.CONFIG_SCHEMA_VERSION)
        self.assertEqual(diagnostics["loaded"], expected["loaded"])
        self.assertEqual(
            [item["key"] for item in diagnostics["unknown_keys"]],
            expected["unknown_keys"],
        )
        self.assertEqual(
            [item["key"] for item in diagnostics["invalid_values"]],
            expected["invalid_keys"],
        )
        for key, value in expected["settings"].items():
            self.assertEqual(settings[key], value)
        for snippet in expected["warnings_contain"]:
            self.assertTrue(
                any(snippet in warning for warning in diagnostics["warnings"]),
                msg=f"missing config warning containing {snippet!r}",
            )


class CIPolicyTests(unittest.TestCase):
    def test_default_policy_does_not_fail_on_high_findings(self) -> None:
        decision = ci_policy.evaluate_ci_policy(
            0,
            json.dumps(
                [
                    {
                        "schema_version": schemas.FINDING_SCHEMA_VERSION,
                        "severity": "critical",
                        "title": "Secret leak",
                    }
                ]
            ),
            {"fail_on_error": False, "fail_on_findings": False},
        )

        self.assertEqual(decision["schema_version"], ci_policy.CI_POLICY_SCHEMA_VERSION)
        self.assertEqual(decision["workflow_exit_code"], 0)
        self.assertEqual(decision["finding_count"], 1)
        self.assertEqual(decision["high_severity_finding_count"], 1)
        self.assertEqual(decision["highest_severity"], "critical")
        self.assertEqual(decision["findings_gate_status"], "disabled")
        self.assertFalse(decision["findings_gate_enforced"])

    def test_fail_on_error_controls_cursor_failures(self) -> None:
        non_blocking = ci_policy.evaluate_ci_policy(2, "[]", {"fail_on_error": False})
        blocking = ci_policy.evaluate_ci_policy(2, "[]", {"fail_on_error": True})

        self.assertEqual(non_blocking["workflow_exit_code"], 0)
        self.assertEqual(non_blocking["reason"], "cursor_error_non_blocking")
        self.assertEqual(blocking["workflow_exit_code"], 2)
        self.assertEqual(blocking["reason"], "cursor_error_failed")

    def test_fail_on_findings_is_diagnosed_but_not_enforced_without_threshold(self) -> None:
        decision = ci_policy.evaluate_ci_policy(
            0,
            json.dumps([{"schema_version": schemas.FINDING_SCHEMA_VERSION, "severity": "high"}]),
            {"fail_on_error": False, "fail_on_findings": True},
        )

        self.assertEqual(decision["workflow_exit_code"], 0)
        self.assertEqual(decision["findings_gate_status"], "reserved_no_threshold")
        self.assertFalse(decision["findings_gate_enforced"])


class ContextBuilderTests(unittest.TestCase):
    def test_build_review_context_adds_structured_pr_metadata(self) -> None:
        settings = {
            "pr_number": "42",
            "pr_title": "Add safer parser",
            "pr_body": "Implements parser guardrails.",
            "base_ref": "main",
            "head_ref": "feature/parser",
            "event_name": "pull_request",
            "resolved_command": "review",
            "resolved_user_prompt": "Focus on tests.",
            "commit_messages": "Add parser\nAdd tests",
            "config_loaded": ".cursor-review.yml",
        }
        diff_meta = {
            "base": "base-sha",
            "head": "head-sha",
            "range": "base-sha...head-sha",
            "files": ["scripts/engine/parser.py", "tests/test_engine.py"],
        }

        with mock.patch.object(
            context,
            "build_diff",
            return_value=("diff --git a/a.py b/a.py", " parser.py | 2 +", False, diff_meta),
        ):
            review_context = context.build_review_context(settings)

        pr_context = review_context.meta["pull_request_context"]
        self.assertEqual(pr_context["pr_number"], "42")
        self.assertEqual(pr_context["title"], "Add safer parser")
        self.assertEqual(pr_context["body"], "Implements parser guardrails.")
        self.assertEqual(pr_context["base_ref"], "main")
        self.assertEqual(pr_context["head_ref"], "feature/parser")
        self.assertEqual(pr_context["commit_messages"], ["Add parser", "Add tests"])
        self.assertEqual(pr_context["changed_files"], ["scripts/engine/parser.py", "tests/test_engine.py"])
        self.assertEqual(pr_context["diff_stat"], "parser.py | 2 +")
        self.assertEqual(pr_context["comment_prompt"], "Focus on tests.")


class RepoGuidanceTests(unittest.TestCase):
    def test_load_repo_guidance_applies_command_defaults_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor-review-instructions.md").write_text("Prefer typed errors.\n", encoding="utf-8")
            (root / "best_practices.md").write_text("Use small focused helpers.\n", encoding="utf-8")

            review_guidance = guidance.load_repo_guidance(
                {
                    "guidance_enabled": True,
                    "guidance_files": {
                        "general": ".cursor-review-instructions.md",
                        "improve": "best_practices.md",
                    },
                    "guidance_max_bytes": 20000,
                    "guidance_max_lines": 400,
                },
                "review",
                root,
            )
            improve_guidance = guidance.load_repo_guidance(
                {
                    "guidance_enabled": True,
                    "guidance_files": {
                        "general": ".cursor-review-instructions.md",
                        "improve": "best_practices.md",
                    },
                    "guidance_max_bytes": 20000,
                    "guidance_max_lines": 400,
                },
                "improve",
                root,
            )

        self.assertEqual([item["path"] for item in review_guidance["diagnostics"]["loaded"]], [".cursor-review-instructions.md"])
        self.assertEqual(review_guidance["diagnostics"]["skipped"], [{"kind": "improve", "path": "best_practices.md", "reason": "command_not_applicable"}])
        self.assertEqual(
            [item["path"] for item in improve_guidance["diagnostics"]["loaded"]],
            [".cursor-review-instructions.md", "best_practices.md"],
        )

    def test_load_repo_guidance_rejects_unsafe_paths_and_truncates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text("abcdef", encoding="utf-8")
            repo_guidance = guidance.load_repo_guidance(
                {
                    "guidance_enabled": True,
                    "guidance_files": {
                        "general": "guide.md",
                        "improve": "../outside.md",
                    },
                    "guidance_max_bytes": 3,
                    "guidance_max_lines": 400,
                },
                "improve",
                root,
            )

        self.assertEqual(repo_guidance["sections"][0]["content"], "abc")
        self.assertTrue(repo_guidance["diagnostics"]["loaded"][0]["truncated"])
        self.assertEqual(repo_guidance["diagnostics"]["skipped"][0]["reason"], "invalid_path")

    def test_build_prompt_injects_guidance_content_and_diagnostics(self) -> None:
        meta = {
            "files": ["a.py"],
            "repo_guidance": {
                "sections": [
                    {
                        "kind": "general",
                        "path": ".cursor-review-instructions.md",
                        "content": "Prefer deterministic parser errors.",
                        "truncated": False,
                    }
                ],
                "diagnostics": {
                    "enabled": True,
                    "max_bytes": 20000,
                    "max_lines": 400,
                    "bytes_used": 35,
                    "loaded": [{"kind": "general", "path": ".cursor-review-instructions.md", "bytes": 35}],
                    "skipped": [],
                },
            },
        }

        prompt = prompts.build_prompt(
            "review",
            "",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            meta,
            {"language": "en", "max_findings": 5, "review_focus": "correctness", "model": "auto"},
        )

        self.assertIn("Prefer deterministic parser errors.", prompt)
        self.assertIn('"repo_guidance": {', prompt)
        self.assertIn('".cursor-review-instructions.md"', prompt)


class ReviewScopeTests(unittest.TestCase):
    def test_default_scope_reviews_full_selected_diff(self) -> None:
        files, skipped, diagnostics = scope.apply_review_scope(
            ["src/app.py", "tests/test_app.py"],
            {},
        )

        self.assertEqual(files, ["src/app.py", "tests/test_app.py"])
        self.assertEqual(skipped, [])
        self.assertEqual(diagnostics["schema_version"], scope.SCOPE_SCHEMA_VERSION)
        self.assertEqual(diagnostics["mode"], "full")
        self.assertEqual(diagnostics["reason"], "full_selected_diff")

    def test_file_scope_filters_changed_files_with_diagnostics(self) -> None:
        files, skipped, diagnostics = scope.apply_review_scope(
            ["src/app.py", "docs/readme.md", "tests/test_app.py"],
            {"scope_mode": "files", "scope_files": "src/*.py,tests/test_app.py"},
        )

        self.assertEqual(files, ["src/app.py", "tests/test_app.py"])
        self.assertEqual(skipped, [{"path": "docs/readme.md", "reason": "scope_not_requested"}])
        self.assertEqual(diagnostics["mode"], "files")
        self.assertEqual(diagnostics["reason"], "command_scoped_files")
        self.assertEqual(diagnostics["selected_file_count"], 2)
        self.assertEqual(diagnostics["skipped_file_count"], 1)

    def test_file_scope_with_no_match_is_explicit(self) -> None:
        files, skipped, diagnostics = scope.apply_review_scope(
            ["src/app.py"],
            {"scope_mode": "files", "scope_files": "docs/**"},
        )

        self.assertEqual(files, [])
        self.assertEqual(skipped, [{"path": "src/app.py", "reason": "scope_not_requested"}])
        self.assertIn("File-scoped review matched no changed files.", diagnostics["warnings"])

    def test_incremental_scope_is_deferred_to_full_review(self) -> None:
        files, skipped, diagnostics = scope.apply_review_scope(
            ["src/app.py"],
            {"scope_mode": "incremental"},
        )

        self.assertEqual(files, ["src/app.py"])
        self.assertEqual(skipped, [])
        self.assertEqual(diagnostics["mode"], "full")
        self.assertIn(
            "Incremental since-last-run scope is not supported yet; reviewing the full selected PR diff.",
            diagnostics["warnings"],
        )


class DiffSelectorTests(unittest.TestCase):
    def test_build_diff_records_reviewed_and_budget_skipped_files(self) -> None:
        def fake_file_diff(file_name: str, *_args: object) -> str:
            if file_name == "a.py":
                return "diff --git a/a.py b/a.py\n+small\n"
            return "diff --git a/b.py b/b.py\n+" + ("x" * 120) + "\n"

        with mock.patch.object(diff_selector, "diff_range", return_value=("base", "head", "base...head")):
            with mock.patch.object(diff_selector, "changed_files", return_value=["a.py", "b.py"]):
                with mock.patch.object(diff_selector, "_file_diff", side_effect=fake_file_diff):
                    with mock.patch.object(diff_selector, "run_command", return_value=mock.Mock(stdout="stat")):
                        diff_text, stat, truncated, meta = diff_selector.build_diff({"max_diff_bytes": 80})

        self.assertEqual(stat, "stat")
        self.assertTrue(truncated)
        self.assertIn("a.py", diff_text)
        self.assertNotIn("b.py b/b.py", diff_text)
        self.assertEqual(meta["reviewed_files"], [{"path": "a.py", "bytes": 32, "hunks": 0, "status": "included"}])
        self.assertEqual(meta["skipped_files"], [{"path": "b.py", "reason": "max_diff_bytes"}])
        self.assertEqual(meta["truncation_reasons"], ["max_diff_bytes"])

    def test_build_diff_records_filter_skipped_files_without_truncation(self) -> None:
        with mock.patch.object(diff_selector, "diff_range", return_value=("base", "head", "base...head")):
            with mock.patch.object(diff_selector, "changed_files", return_value=["src/a.py", "dist/b.js"]):
                with mock.patch.object(diff_selector, "_file_diff", return_value="diff --git a/src/a.py b/src/a.py\n+small\n"):
                    with mock.patch.object(diff_selector, "run_command", return_value=mock.Mock(stdout="stat")):
                        _diff_text, _stat, truncated, meta = diff_selector.build_diff(
                            {"max_diff_bytes": 120000, "exclude_patterns": "dist/**"}
                        )

        self.assertFalse(truncated)
        self.assertEqual([item["path"] for item in meta["reviewed_files"]], ["src/a.py"])
        self.assertEqual(meta["skipped_files"], [{"path": "dist/b.js", "reason": "excluded"}])

    def test_build_diff_applies_command_file_scope_before_budget(self) -> None:
        def fake_file_diff(file_name: str, *_args: object) -> str:
            return f"diff --git a/{file_name} b/{file_name}\n+small\n"

        with mock.patch.object(diff_selector, "diff_range", return_value=("base", "head", "base...head")):
            with mock.patch.object(diff_selector, "changed_files", return_value=["src/a.py", "docs/readme.md", "tests/test_a.py"]):
                with mock.patch.object(diff_selector, "_file_diff", side_effect=fake_file_diff):
                    with mock.patch.object(diff_selector, "run_command", return_value=mock.Mock(stdout="stat")):
                        diff_text, _stat, truncated, meta = diff_selector.build_diff(
                            {
                                "max_diff_bytes": 120000,
                                "scope_mode": "files",
                                "scope_files": "src/*.py,tests/*.py",
                            }
                        )

        self.assertFalse(truncated)
        self.assertIn("src/a.py", diff_text)
        self.assertIn("tests/test_a.py", diff_text)
        self.assertNotIn("docs/readme.md", diff_text)
        self.assertEqual(meta["files"], ["src/a.py", "tests/test_a.py"])
        self.assertEqual(meta["skipped_files"], [{"path": "docs/readme.md", "reason": "scope_not_requested"}])
        self.assertEqual(meta["scope"]["mode"], "files")
        self.assertEqual(meta["scope"]["reason"], "command_scoped_files")

    def test_build_diff_applies_max_files_budget(self) -> None:
        with mock.patch.object(diff_selector, "diff_range", return_value=("base", "head", "base...head")):
            with mock.patch.object(diff_selector, "changed_files", return_value=["a.py", "b.py", "c.py"]):
                with mock.patch.object(diff_selector, "_file_diff", return_value="diff --git a/a.py b/a.py\n+small\n"):
                    with mock.patch.object(diff_selector, "run_command", return_value=mock.Mock(stdout="stat")):
                        _diff_text, _stat, truncated, meta = diff_selector.build_diff(
                            {"max_diff_bytes": 120000, "max_files": 2}
                        )

        self.assertTrue(truncated)
        self.assertEqual(meta["files"], ["a.py", "b.py"])
        self.assertEqual(meta["skipped_files"], [{"path": "c.py", "reason": "max_files"}])
        self.assertEqual(meta["truncation_reasons"], ["max_files"])

    def test_build_diff_applies_max_hunks_budget(self) -> None:
        diff = """diff --git a/a.py b/a.py
@@ -1,3 +1,3 @@
+one
@@ -10,3 +10,3 @@
+two
@@ -20,3 +20,3 @@
+three
"""
        with mock.patch.object(diff_selector, "diff_range", return_value=("base", "head", "base...head")):
            with mock.patch.object(diff_selector, "changed_files", return_value=["a.py"]):
                with mock.patch.object(diff_selector, "_file_diff", return_value=diff):
                    with mock.patch.object(diff_selector, "run_command", return_value=mock.Mock(stdout="stat")):
                        diff_text, _stat, truncated, meta = diff_selector.build_diff(
                            {"max_diff_bytes": 120000, "max_hunks": 2}
                        )

        self.assertTrue(truncated)
        self.assertIn("+two", diff_text)
        self.assertNotIn("+three", diff_text)
        self.assertEqual(meta["hunks"], 2)
        self.assertEqual(meta["reviewed_files"][0]["status"], "partial")
        self.assertEqual(meta["skipped_files"], [{"path": "a.py", "reason": "max_hunks_partial"}])
        self.assertEqual(meta["truncation_reasons"], ["max_hunks"])


class FindingGroundingTests(unittest.TestCase):
    def test_diff_index_records_new_and_old_changed_lines(self) -> None:
        diff_text = """diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -10,3 +10,4 @@ def login(request):
     user = authenticate(request)
-    session["is_admin"] = False
+    session["is_admin"] = request.args.get("admin") == "1"
     return redirect("/")
"""

        index = diff_index.build_diff_index(diff_text)
        entry = index["files"]["app/auth.py"]

        self.assertEqual(index["schema_version"], diff_index.DIFF_INDEX_SCHEMA_VERSION)
        self.assertEqual(entry["new_changed_lines"], [11])
        self.assertEqual(entry["old_changed_lines"], [11])
        self.assertEqual(entry["hunks"][0]["header"], "@@ -10,3 +10,4 @@ def login(request):")

    def test_grounding_classifies_anchored_file_only_invalid_and_unanchored_findings(self) -> None:
        diff_text = """diff --git a/app/auth.py b/app/auth.py
@@ -10,3 +10,4 @@ def login(request):
     user = authenticate(request)
+    session["is_admin"] = request.args.get("admin") == "1"
     return redirect("/")
"""
        index = diff_index.build_diff_index(diff_text, [{"path": "skipped.py", "reason": "max_files"}])
        findings = [
            {"file": "app/auth.py", "line": 11, "severity": "high", "confidence": "high", "title": "valid"},
            {"file": "app/auth.py", "line": 10, "severity": "medium", "confidence": "high", "title": "context"},
            {"file": "skipped.py", "line": 1, "severity": "critical", "confidence": "high", "title": "skipped"},
            {"severity": "high", "confidence": "high", "title": "missing file"},
        ]

        result = grounding.ground_findings_json(json.dumps(findings), index, "review")
        grounded = json.loads(result.findings_json)

        self.assertEqual([item["grounding_status"] for item in grounded], ["anchored", "file_only", "invalid", "unanchored"])
        self.assertEqual(grounded[0]["anchor"]["line"], 11)
        self.assertEqual(grounded[1]["review_section"], "needs_human_verification")
        self.assertTrue(grounded[2]["suppressed"])
        self.assertEqual(grounded[2]["confidence"], "low")
        self.assertEqual(result.diagnostics["anchored_count"], 1)
        self.assertEqual(result.diagnostics["file_only_count"], 1)
        self.assertEqual(result.diagnostics["invalid_anchor_count"], 1)
        self.assertEqual(result.diagnostics["skipped_file_finding_count"], 1)

    def test_grounding_supports_deleted_line_evidence_without_new_line_anchor(self) -> None:
        diff_text = """diff --git a/src/flags.py b/src/flags.py
@@ -20,3 +20,2 @@ FLAGS = {
-    "unsafe": True,
     "safe": True,
}
"""
        index = diff_index.build_diff_index(diff_text)
        findings = [
            {
                "file": "src/flags.py",
                "line": None,
                "old_line": 20,
                "line_side": "old",
                "severity": "medium",
                "confidence": "high",
                "title": "Deleted unsafe flag",
            }
        ]

        result = grounding.ground_findings_json(json.dumps(findings), index, "review")
        grounded = json.loads(result.findings_json)

        self.assertEqual(grounded[0]["grounding_status"], "anchored")
        self.assertEqual(grounded[0]["anchor"]["line_side"], "old")
        self.assertEqual(grounded[0]["anchor"]["old_line"], 20)

    def test_ci_policy_excludes_invalid_grounded_findings_from_gating_counts(self) -> None:
        findings = [
            {"severity": "critical", "grounding_status": "invalid", "suppressed": True},
            {"severity": "high", "grounding_status": "file_only"},
            {"severity": "high", "grounding_status": "anchored"},
        ]

        decision = ci_policy.evaluate_ci_policy(0, json.dumps(findings), {"fail_on_findings": True})

        self.assertEqual(decision["finding_count"], 3)
        self.assertEqual(decision["gating_eligible_finding_count"], 1)
        self.assertEqual(decision["high_severity_finding_count"], 1)
        self.assertEqual(decision["highest_severity"], "high")


class FindingDedupTests(unittest.TestCase):
    def test_deduplicates_same_file_line_before_applying_max_findings(self) -> None:
        payload = [
            {
                "file": "src/app.py",
                "line": 12,
                "category": "bug",
                "severity": "medium",
                "confidence": "medium",
                "grounding_status": "anchored",
                "title": "Duplicate wording A",
                "body": "Same actionable issue.",
            },
            {
                "file": "src/app.py",
                "line": 12,
                "category": "bug",
                "severity": "medium",
                "confidence": "medium",
                "grounding_status": "anchored",
                "title": "Duplicate wording B",
                "body": "Same actionable issue with different text.",
            },
            {
                "file": "src/critical.py",
                "line": 3,
                "category": "security",
                "severity": "critical",
                "confidence": "high",
                "grounding_status": "anchored",
                "title": "Keep the critical issue",
                "body": "This should sort ahead of medium findings.",
            },
        ]

        result = findings.postprocess_findings_json(json.dumps(payload), {"max_findings": 2}, "review")
        processed = json.loads(result.findings_json)

        self.assertEqual(result.diagnostics["schema_version"], findings.FINDING_DEDUP_SCHEMA_VERSION)
        self.assertEqual(result.diagnostics["input_count"], 3)
        self.assertEqual(result.diagnostics["duplicate_count"], 1)
        self.assertEqual(result.diagnostics["capped_count"], 0)
        self.assertEqual(result.diagnostics["output_count"], 2)
        self.assertEqual([item["file"] for item in processed], ["src/critical.py", "src/app.py"])
        self.assertTrue(all(item.get("finding_fingerprint") for item in processed))

    def test_low_confidence_unanchored_findings_do_not_displace_grounded_findings(self) -> None:
        payload = [
            {
                "file": "",
                "category": "security",
                "severity": "critical",
                "confidence": "low",
                "grounding_status": "unanchored",
                "suppressed": True,
                "title": "Ungrounded broad claim",
            },
            {
                "file": "src/app.py",
                "line": 8,
                "category": "bug",
                "severity": "high",
                "confidence": "high",
                "grounding_status": "anchored",
                "title": "Grounded bug",
            },
            {
                "file": "src/other.py",
                "line": 9,
                "category": "test_gap",
                "severity": "medium",
                "confidence": "high",
                "grounding_status": "anchored",
                "title": "Grounded test gap",
            },
        ]

        result = findings.postprocess_findings_json(json.dumps(payload), {"max_findings": 2}, "review")
        processed = json.loads(result.findings_json)

        self.assertEqual(result.diagnostics["capped_count"], 1)
        self.assertEqual([item["title"] for item in processed], ["Grounded bug", "Grounded test gap"])


class OutputQualityGateTests(unittest.TestCase):
    def test_quality_gate_downgrades_unsupported_external_claims(self) -> None:
        payload = [
            {
                "schema_version": schemas.FINDING_SCHEMA_VERSION,
                "category": "test_gap",
                "severity": "high",
                "confidence": "high",
                "file": "tests/test_app.py",
                "line": 12,
                "title": "Tests passed but assertion is missing",
                "body": "All tests passed, but this new branch lacks an assertion.",
                "suggestion": "Add an assertion that covers the new branch.",
                "evidence": "+    if value: return True",
                "grounding_status": "anchored",
            }
        ]

        result = quality_gate.evaluate_output_quality(
            "One finding.",
            json.dumps(payload),
            0,
            True,
            False,
            {"files": ["tests/test_app.py"], "skipped_files": []},
            {"resolved_command": "review"},
            {"parser": {"schema": {"compatible": True}}},
            redaction.redact_text(""),
        )
        gated = json.loads(result.findings_json)

        self.assertEqual(result.diagnostics["schema_version"], quality_gate.QUALITY_GATE_SCHEMA_VERSION)
        self.assertEqual(result.diagnostics["publish_decision"], quality_gate.SUPPRESS_FINDINGS)
        self.assertEqual(result.diagnostics["unsupported_claim_count"], 1)
        self.assertTrue(gated[0]["unsupported_claim"])
        self.assertEqual(gated[0]["confidence"], "low")
        self.assertTrue(gated[0]["suppressed"])
        self.assertEqual(gated[0]["quality_gate_status"], "suppressed")

    def test_quality_gate_marks_truncated_reviews_partial(self) -> None:
        result = quality_gate.evaluate_output_quality(
            "No findings.",
            "[]",
            0,
            True,
            True,
            {"files": ["src/app.py"], "skipped_files": [{"path": "src/large.py", "reason": "max_files"}]},
            {"resolved_command": "review"},
            {"parser": {"schema": {"compatible": True}}},
            redaction.redact_text(""),
        )

        self.assertEqual(result.diagnostics["publish_decision"], quality_gate.PUBLISH_PARTIAL)
        self.assertEqual(result.diagnostics["coverage_status"], "partial")
        self.assertEqual(result.diagnostics["skipped_file_count"], 1)

    def test_quality_gate_blocks_redaction_failure(self) -> None:
        result = quality_gate.evaluate_output_quality(
            "Sensitive output.",
            "[]",
            0,
            True,
            False,
            {"files": []},
            {"resolved_command": "review"},
            {"parser": {"schema": {"compatible": True}}, "redaction_failure": True},
            redaction.redact_text(""),
        )

        self.assertEqual(result.diagnostics["publish_decision"], quality_gate.FAIL_BEFORE_PUBLISH)
        self.assertEqual(result.diagnostics["reason"], "redaction_failed")


class PromptParserRenderTests(unittest.TestCase):
    def test_build_prompt_preserves_response_contract_and_diagnostics(self) -> None:
        settings = {
            "language": "zh-CN",
            "max_findings": 5,
            "review_focus": "correctness,tests",
            "model": "auto",
            "config_loaded": "",
        }
        prompt = prompts.build_prompt(
            "review",
            "Focus on risky edge cases.",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            {"files": ["a.py"]},
            settings,
        )

        self.assertIn("Review this pull request", prompt)
        self.assertIn("Additional user instructions from PR comment", prompt)
        self.assertIn("<review_markdown>", prompt)
        self.assertIn('"command": "review"', prompt)
        self.assertIn(f'"prompt_template_version": "{prompts.prompt_template_version()}"', prompt)
        self.assertIn('"category": "bug|security|test_gap|performance|regression_risk|maintainability|docs|question"', prompt)
        self.assertIn('"severity": "critical|high|medium|low|info"', prompt)
        self.assertIn('"diff_truncated": false', prompt)

    def test_language_instruction_does_not_translate_schema_contract(self) -> None:
        prompt = prompts.build_prompt(
            "ask",
            "What changed?",
            "",
            "",
            False,
            {"files": [], "pull_request_context": {}},
            {"language": "en", "max_findings": 5, "review_focus": "correctness", "model": "auto"},
        )

        self.assertIn("Write all human-readable prose in en.", prompt)
        self.assertIn("Do not translate JSON field names", prompt)
        self.assertIn('"schema_version": "cursor-review-action/v1"', prompt)
        self.assertIn('"command": "ask"', prompt)
        self.assertIn('"answer"', prompt)

    def test_prompt_templates_are_versioned_and_contract_checked(self) -> None:
        self.assertEqual(prompts.prompt_template_version(), "prompt-template-v1")
        for command in ("review", "ask", "improve", "describe"):
            template_path = prompts.TEMPLATE_DIR / f"{command}.md"
            template = template_path.read_text(encoding="utf-8")
            self.assertIn("<review_markdown>", template)
            self.assertIn("<findings_json>", template)
            self.assertIn("{{schema_json}}", template)

    def test_build_prompt_uses_command_specific_template_and_schema(self) -> None:
        settings = {
            "language": "en",
            "max_findings": 3,
            "review_focus": "tests",
            "model": "auto",
            "config_loaded": "",
        }

        ask_prompt = prompts.build_prompt(
            "ask",
            "What changed?",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            {"files": ["a.py"]},
            settings,
        )
        improve_prompt = prompts.build_prompt(
            "improve",
            "",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            {"files": ["a.py"]},
            settings,
        )
        describe_prompt = prompts.build_prompt(
            "describe",
            "",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            {"files": ["a.py"]},
            settings,
        )

        self.assertIn("Answer the user's question", ask_prompt)
        self.assertIn('"command": "ask"', ask_prompt)
        self.assertIn('"answer"', ask_prompt)
        self.assertNotIn("Review this pull request for correctness", ask_prompt)
        self.assertIn("Suggest concrete improvements", improve_prompt)
        self.assertIn('"command": "improve"', improve_prompt)
        self.assertIn('"suggestions"', improve_prompt)
        self.assertIn("comment-only summary", describe_prompt)
        self.assertIn('"command": "describe"', describe_prompt)
        self.assertIn('"walkthrough"', describe_prompt)

    def test_build_prompt_includes_pull_request_context(self) -> None:
        settings = {
            "language": "en",
            "max_findings": 5,
            "review_focus": "correctness",
            "model": "auto",
            "config_loaded": "",
        }
        meta = {
            "files": ["a.py"],
            "pull_request_context": {
                "pr_number": "42",
                "title": "Add safer parser",
                "body": "Parser guardrails.",
                "base_ref": "main",
                "head_ref": "feature/parser",
                "commit_messages": ["Add parser"],
                "changed_files": ["a.py"],
                "diff_stat": "a.py | 1 +",
            },
        }

        prompt = prompts.build_prompt(
            "review",
            "",
            "diff --git a/a.py b/a.py",
            " a.py | 1 +",
            False,
            meta,
            settings,
        )

        self.assertIn("Pull request context:", prompt)
        self.assertIn('"title": "Add safer parser"', prompt)
        self.assertIn('"commit_messages": [', prompt)

    def test_each_command_uses_distinct_template_and_schema(self) -> None:
        settings = {
            "language": "en",
            "max_findings": 3,
            "review_focus": "correctness",
            "model": "auto",
            "config_loaded": "",
        }
        expected = {
            "review": ("Review this pull request", "cursor_review_findings"),
            "ask": ("Do not perform a general code review", "cursor_ask_evidence"),
            "improve": ("Do not repeat bug/security/test findings", "cursor_improve_suggestions"),
            "describe": ("Do not update or imply that you updated the PR body", "cursor_describe_sections"),
        }

        for command, (task_text, schema_name) in expected.items():
            with self.subTest(command=command):
                prompt = prompts.build_prompt(
                    command,
                    "Keep the answer concise.",
                    "diff --git a/a.py b/a.py",
                    " a.py | 1 +",
                    False,
                    {"files": ["a.py"]},
                    settings,
                )

                self.assertIn(task_text, prompt)
                self.assertIn(schema_name, prompt)
                self.assertIn(f'"prompt_template": "{command}.md"', prompt)
                self.assertIn("Additional user instructions from PR comment", prompt)

    def test_schema_contracts_keep_findings_json_as_json_array(self) -> None:
        for command in ("review", "ask", "improve", "describe"):
            with self.subTest(command=command):
                schema = schemas.schema_for_command(command)

                self.assertEqual(schema["type"], "array")
                self.assertEqual(schema["schema_version"], "1.0")
                self.assertIn("required", schema["items"])

    def test_parse_agent_output_formats_valid_findings_json(self) -> None:
        raw = """
<review_markdown>No issues.</review_markdown>
<findings_json>[{"severity":"low","file":"a.py"}]</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw)

        self.assertEqual(markdown, "No issues.")
        self.assertTrue(parsed_ok)
        parsed = json.loads(findings_json)
        self.assertEqual(parsed[0]["severity"], "low")
        self.assertEqual(parsed[0]["file"], "a.py")
        self.assertEqual(parsed[0]["schema_version"], taxonomy.FINDING_SCHEMA_VERSION)
        self.assertEqual(parsed[0]["category"], "bug")
        self.assertEqual(parsed[0]["confidence"], "medium")

    def test_parse_agent_output_applies_finding_taxonomy_diagnostics(self) -> None:
        raw = """
<review_markdown>Potential auth bypass.</review_markdown>
<findings_json>[{"category":"security","severity":"HIGH","confidence":"HIGH","file":"auth.py","line":4,"title":"Auth bypass","body":"A token can be reused.","evidence":"token"}]</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "review")
        parsed = json.loads(result.findings_json)

        self.assertTrue(result.parsed_ok)
        self.assertEqual(parsed[0]["schema_version"], taxonomy.FINDING_SCHEMA_VERSION)
        self.assertEqual(parsed[0]["category"], "security")
        self.assertEqual(parsed[0]["severity"], "high")
        self.assertEqual(parsed[0]["confidence"], "high")
        self.assertEqual(result.diagnostics["taxonomy"]["normalized_count"], 1)
        self.assertEqual(result.diagnostics["taxonomy"]["noise_suppressed_count"], 0)

    def test_parse_agent_output_marks_review_noise_for_improve_route(self) -> None:
        raw = """
<review_markdown>Prefer renaming this helper.</review_markdown>
<findings_json>[{"category":"style","severity":"high","confidence":"high","file":"a.py","line":2,"title":"Rename helper","body":"This is a readability preference.","evidence":"def x()"}]</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "review")
        parsed = json.loads(result.findings_json)

        self.assertEqual(parsed[0]["category"], "style")
        self.assertEqual(parsed[0]["severity"], "low")
        self.assertEqual(parsed[0]["confidence"], "low")
        self.assertTrue(parsed[0]["suppressed"])
        self.assertEqual(parsed[0]["suppression_reason"], "review_noise_control")
        self.assertEqual(parsed[0]["noise_control"], "route_to_cursor_improve")
        self.assertEqual(result.diagnostics["taxonomy"]["noise_suppressed_count"], 1)

    def test_parse_agent_output_accepts_command_json_object(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"schema_version":"cursor-review-action/v1","command":"describe","summary":"Parser update"}</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw, "describe")

        self.assertEqual(markdown, "It updates parser behavior.")
        self.assertTrue(parsed_ok)
        self.assertEqual(json.loads(findings_json)["command"], "describe")

    def test_schema_contract_lists_supported_versions_and_stable_fields(self) -> None:
        contract = schemas.schema_contract("describe")

        self.assertEqual(contract["schema_compatibility"], schemas.SCHEMA_COMPATIBILITY_VERSION)
        self.assertEqual(contract["current_output_schema_version"], schemas.OUTPUT_SCHEMA_VERSION)
        self.assertEqual(contract["supported_output_schema_versions"], [schemas.OUTPUT_SCHEMA_VERSION])
        self.assertIn("summary", contract["stable_fields"])
        self.assertIn("schema_version", contract["stable_fields"])

    def test_parse_agent_output_records_current_schema_diagnostics(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"schema_version":"cursor-review-action/v1","command":"describe","summary":"Parser update"}</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "describe")

        self.assertTrue(result.parsed_ok)
        self.assertEqual(result.diagnostics["schema"]["payload_schema_status"], "current")
        self.assertEqual(result.diagnostics["schema"]["payload_schema_version"], schemas.OUTPUT_SCHEMA_VERSION)
        self.assertTrue(result.diagnostics["schema"]["command_match"])

    def test_parse_agent_output_accepts_legacy_missing_schema_version(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"command":"describe","summary":"Parser update"}</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "describe")

        self.assertTrue(result.parsed_ok)
        self.assertEqual(result.diagnostics["schema"]["payload_schema_status"], "legacy_missing_schema_version")
        self.assertEqual(result.diagnostics["schema"]["reason"], "legacy_missing_schema_version")
        self.assertEqual(json.loads(result.findings_json)["summary"], "Parser update")

    def test_parse_agent_output_rejects_unsupported_schema_version(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"schema_version":"cursor-review-action/v999","command":"describe","summary":"Parser update"}</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "describe")

        self.assertFalse(result.parsed_ok)
        self.assertEqual(json.loads(result.findings_json), [])
        self.assertEqual(result.diagnostics["reason"], "unsupported_schema_version")
        self.assertEqual(result.diagnostics["schema"]["payload_schema_status"], "unsupported_schema_version")

    def test_parse_agent_output_rejects_schema_command_mismatch(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"schema_version":"cursor-review-action/v1","command":"ask","summary":"Parser update"}</findings_json>
"""

        result = parser.parse_agent_output_result(raw, "describe")

        self.assertFalse(result.parsed_ok)
        self.assertEqual(result.diagnostics["reason"], "command_mismatch")
        self.assertFalse(result.diagnostics["schema"]["command_match"])

    def test_parse_agent_output_falls_back_to_markdown_on_invalid_json(self) -> None:
        raw = """
<review_markdown>Check this.</review_markdown>
<findings_json>{not valid}</findings_json>
"""

        result = parser.parse_agent_output_result(raw)

        self.assertEqual(result.markdown, "Check this.")
        self.assertEqual(json.loads(result.findings_json), [])
        self.assertFalse(result.parsed_ok)
        self.assertEqual(result.diagnostics["reason"], "invalid_json")
        self.assertEqual(result.diagnostics["fallback"], "markdown")

    def test_parse_agent_output_reports_missing_json_as_markdown_fallback(self) -> None:
        result = parser.parse_agent_output_result("Plain markdown answer.")

        self.assertEqual(result.markdown, "Plain markdown answer.")
        self.assertEqual(json.loads(result.findings_json), [])
        self.assertFalse(result.parsed_ok)
        self.assertEqual(result.diagnostics["reason"], "missing_findings_json")

    def test_build_repair_prompt_embeds_command_schema(self) -> None:
        prompt = parser.build_repair_prompt("describe", "<review_markdown>Summary</review_markdown>")

        self.assertIn("Repair the previous Cursor review response", prompt)
        self.assertIn("<findings_json>...</findings_json>", prompt)
        self.assertIn('"command": "describe"', prompt)
        self.assertIn('"walkthrough"', prompt)

    def test_render_comment_includes_existing_diagnostics(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            True,
            True,
            {"files": ["a.py", "b.py"]},
            {
                "resolved_command": "review",
                "model": "auto",
                "filter_mode": "added",
                "prompt_template_version": prompts.prompt_template_version(),
            },
        )

        self.assertIn("No issues.", rendered)
        self.assertIn("Prompt template version: `prompt-template-v1`", rendered)
        self.assertIn("Diff truncated: `true`", rendered)
        self.assertIn("Files reviewed: `2`", rendered)
        self.assertIn("Files skipped: `0`", rendered)

    def test_render_comment_declares_human_advisory_policy(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": ["a.py"]},
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
        )

        self.assertIn("advisory and non-blocking", rendered)
        self.assertIn("does not approve, merge, or block PRs by default", rendered)
        self.assertIn("Review policy: `advisory_non_blocking`", rendered)
        self.assertIn("Human decision required: `true`", rendered)

    def test_render_comment_keeps_localization_diagnostics_stable(self) -> None:
        language_diagnostics = localization.normalize_language("en")
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": []},
            {
                "resolved_command": "review",
                "model": "auto",
                "filter_mode": "added",
                "language": language_diagnostics["effective_language"],
                "language_diagnostics": language_diagnostics,
            },
        )

        self.assertIn("Localization schema: `localization/v1`", rendered)
        self.assertIn("Language: `en`", rendered)
        self.assertIn("Language fallback used: `false`", rendered)
        self.assertNotIn("idioma", rendered.lower())

    def test_render_comment_reports_config_diagnostics(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": ["a.py"]},
            {
                "resolved_command": "review",
                "model": "auto",
                "filter_mode": "added",
                "config_diagnostics": {
                    "schema_version": config.CONFIG_SCHEMA_VERSION,
                    "loaded": True,
                    "unknown_key_count": 1,
                    "fallback_count": 2,
                    "warnings": [
                        "Unknown config key `surprise_option` was ignored.",
                        "Config `max_findings` expected an integer; using `5`.",
                    ],
                },
            },
        )

        self.assertIn("Config schema: `config/v1`", rendered)
        self.assertIn("Config loaded: `true`", rendered)
        self.assertIn("Config unknown keys: `1`", rendered)
        self.assertIn("Config fallback count: `2`", rendered)
        self.assertIn("Config warning: `Unknown config key `surprise_option` was ignored.`", rendered)

    def test_render_comment_reports_ci_policy_diagnostics(self) -> None:
        rendered = render.render_comment(
            "One issue.",
            json.dumps([{"schema_version": schemas.FINDING_SCHEMA_VERSION, "severity": "high"}]),
            0,
            "",
            False,
            True,
            {"files": ["a.py"]},
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
            {
                "ci_policy": ci_policy.evaluate_ci_policy(
                    0,
                    json.dumps([{"schema_version": schemas.FINDING_SCHEMA_VERSION, "severity": "high"}]),
                    {"fail_on_error": False, "fail_on_findings": True},
                )
            },
        )

        self.assertIn("CI policy schema: `ci-policy/v1`", rendered)
        self.assertIn("CI default: `advisory_non_blocking`", rendered)
        self.assertIn("CI fail on findings: `true`", rendered)
        self.assertIn("CI findings gate status: `reserved_no_threshold`", rendered)
        self.assertIn("CI workflow exit code: `0`", rendered)
        self.assertIn("CI high severity findings: `1`", rendered)

    def test_render_comment_reports_schema_compatibility_diagnostics(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": ["a.py"]},
            {"resolved_command": "describe", "model": "auto", "filter_mode": "added"},
            {
                "parser": {
                    "reason": "valid_json",
                    "fallback": "none",
                    "schema": {
                        "schema_compatibility": schemas.SCHEMA_COMPATIBILITY_VERSION,
                        "payload_schema_status": "current",
                        "payload_schema_version": schemas.OUTPUT_SCHEMA_VERSION,
                        "command_match": True,
                    },
                }
            },
        )

        self.assertIn("Output schema compatibility: `schema-compatibility/v1`", rendered)
        self.assertIn("Output schema status: `current`", rendered)
        self.assertIn("Output schema version: `cursor-review-action/v1`", rendered)
        self.assertIn("Output schema command match: `true`", rendered)

    def test_render_comment_reports_context_presence_without_leaking_body(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {
                "files": ["a.py"],
                "pull_request_context": {
                    "title": "Sensitive title",
                    "body": "Sensitive body",
                    "commit_messages": ["Add parser"],
                },
            },
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
        )

        self.assertIn("PR title provided: `true`", rendered)
        self.assertIn("PR body provided: `true`", rendered)
        self.assertIn("Commit messages provided: `1`", rendered)
        self.assertNotIn("Sensitive body", rendered)

    def test_render_comment_reports_guidance_diagnostics_without_content(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {
                "files": ["a.py"],
                "repo_guidance": {
                    "diagnostics": {
                        "enabled": True,
                        "bytes_used": 24,
                        "loaded": [{"path": ".cursor-review-instructions.md"}],
                        "skipped": [{"path": "best_practices.md", "reason": "command_not_applicable"}],
                    },
                    "sections": [{"content": "Do not leak this guidance body."}],
                },
            },
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
        )

        self.assertIn("Repo guidance enabled: `true`", rendered)
        self.assertIn("Repo guidance loaded files: `.cursor-review-instructions.md`", rendered)
        self.assertIn("best_practices.md:command_not_applicable", rendered)
        self.assertNotIn("Do not leak this guidance body.", rendered)

    def test_render_comment_reports_review_scope_diagnostics(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {
                "files": ["src/app.py"],
                "scope": {
                    "schema_version": scope.SCOPE_SCHEMA_VERSION,
                    "mode": "files",
                    "reason": "command_scoped_files",
                    "selected_file_count": 1,
                    "skipped_file_count": 2,
                    "warnings": [],
                },
            },
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
        )

        self.assertIn("Review scope schema: `review-scope/v1`", rendered)
        self.assertIn("Review scope mode: `files`", rendered)
        self.assertIn("Review scope skipped files: `2`", rendered)

    def test_render_comment_includes_run_state_diagnostics(self) -> None:
        rendered = render.render_comment(
            "No issues.",
            "[]",
            0,
            "",
            False,
            True,
            {"files": ["a.py"]},
            {
                "resolved_command": "review",
                "model": "auto",
                "filter_mode": "added",
                "run_state": {
                    "schema_version": "run-state/v1",
                    "generated_at": "2026-05-12T10:20:00Z",
                    "event_name": "pull_request",
                    "command_source": "slash_command",
                    "run_id": "1001",
                    "run_attempt": "2",
                    "base_sha": "base",
                    "head_sha": "head",
                    "stale_status": "unknown",
                    "idempotency_key": "cursor-review-action:review:42:head",
                },
            },
        )

        self.assertIn("Run state schema: `run-state/v1`", rendered)
        self.assertIn("Head SHA: `head`", rendered)
        self.assertIn("Idempotency key: `cursor-review-action:review:42:head`", rendered)

    def test_redaction_fixture_masks_token_like_strings(self) -> None:
        fixture = json.loads((ROOT / "tests" / "fixtures" / "privacy" / "token_like_output.json").read_text(encoding="utf-8"))

        result = redaction.redact_text(fixture["input"], env=fixture["env"])

        self.assertEqual(result.schema_version, redaction.REDACTION_SCHEMA_VERSION)
        self.assertGreaterEqual(result.redacted_count, 3)
        self.assertIn(fixture["placeholder"], result.text)
        for value in fixture["must_not_contain"]:
            self.assertNotIn(value, result.text)

    def test_render_comment_redacts_markdown_stderr_and_reports_policy(self) -> None:
        rendered = render.render_comment(
            "Do not publish ghp_1234567890abcdefghijklmnopqrstuvwxyz.",
            "[]",
            1,
            "secret=cursor_live_secret_12345",
            False,
            True,
            {"files": ["a.py"]},
            {"resolved_command": "review", "model": "auto", "filter_mode": "added", "debug_artifacts": False},
        )

        self.assertIn("Privacy redaction schema: `redaction/v1`", rendered)
        self.assertIn("Redaction status: `applied`", rendered)
        self.assertIn("Debug artifacts enabled: `false`", rendered)
        self.assertIn("[REDACTED]", rendered)
        self.assertNotIn("ghp_1234567890abcdefghijklmnopqrstuvwxyz", rendered)
        self.assertNotIn("cursor_live_secret_12345", rendered)

    def test_render_trigger_skip_reports_policy_without_raw_prompt(self) -> None:
        rendered = render.render_trigger_skip(
            {
                "reason": "untrusted_author_association",
                "trust_level": "untrusted",
                "event_name": "issue_comment",
                "command_prompt_source": "slash_command",
                "comment_author_association": "CONTRIBUTOR",
                "pr_is_fork": False,
                "cursor_api_key_present": True,
            },
            {"resolved_command": "review"},
        )

        self.assertIn("Cursor review skipped before contacting Cursor.", rendered)
        self.assertIn("untrusted_author_association", rendered)
        self.assertNotIn("/cursor-review", rendered)

    def test_render_help_lists_enabled_commands_only_and_no_cursor_call(self) -> None:
        rendered = help_renderer.render_help(
            {
                "enabled_commands": "review,ask",
                "config_path": ".cursor-review.yml",
                "command_prompt_source": "slash_command",
            }
        )

        self.assertIn("This static help response did not contact Cursor.", rendered)
        self.assertIn("/cursor-review", rendered)
        self.assertIn("/cursor-ask", rendered)
        self.assertNotIn("/cursor-improve -", rendered)
        self.assertIn("Cursor contacted: `false`", rendered)


class SupplyChainTests(unittest.TestCase):
    def test_scripts_remain_stdlib_only(self) -> None:
        diagnostics = supply_chain.scan_stdlib_imports([ROOT / "scripts"], repo_root=ROOT)

        self.assertEqual(diagnostics["schema_version"], supply_chain.SCHEMA_VERSION)
        self.assertTrue(diagnostics["stdlib_only"])
        self.assertEqual(diagnostics["external_imports"], [])
        self.assertIn("scripts/cursor_review.py", diagnostics["scanned_files"])

    def test_stdlib_scan_reports_external_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "uses_external.py"
            source.write_text("import requests\nfrom engine import config\n", encoding="utf-8")

            diagnostics = supply_chain.scan_stdlib_imports([source])

        self.assertFalse(diagnostics["stdlib_only"])
        self.assertEqual(diagnostics["external_imports"][0]["module"], "requests")

    def test_action_ref_policy_requires_tags_for_stable_examples(self) -> None:
        main_policy = supply_chain.action_ref_policy("main")
        tag_policy = supply_chain.action_ref_policy("v1")

        self.assertEqual(main_policy["status"], "pre_stable_only")
        self.assertFalse(main_policy["stable_release_allowed"])
        self.assertEqual(tag_policy["status"], "stable_tag")
        self.assertTrue(tag_policy["stable_release_allowed"])

    def test_release_and_dependency_docs_cover_required_supply_chain_gates(self) -> None:
        release_checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
        dependencies = (ROOT / "docs" / "dependencies.md").read_text(encoding="utf-8")

        for doc in [release_checklist, dependencies]:
            self.assertIn("SUPPLY-CHAIN-P0", doc)
            self.assertIn("stdlib", doc.lower())
            self.assertIn("Cursor CLI", doc)
        self.assertIn("Never auto-create release tags", release_checklist)
        self.assertIn("nanyang12138/cursor-review-action@main", release_checklist)
        self.assertIn("nanyang12138/cursor-review-action@v1", release_checklist)
        self.assertIn("actions/github-script@v7", dependencies)
        self.assertIn("scripts/install-cursor.sh", dependencies)


class TriggerTrustPolicyTests(unittest.TestCase):
    def test_trigger_fixture_decisions_match_expected_policy(self) -> None:
        fixture_dir = ROOT / "tests" / "fixtures" / "triggers"
        for fixture_path in sorted(fixture_dir.glob("*.json")):
            with self.subTest(fixture=fixture_path.name):
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                decision = trust_policy.evaluate_trigger_trust(fixture["settings"])
                expected = fixture["expected"]

                self.assertEqual(decision.allowed, expected["allowed"])
                self.assertEqual(decision.reason, expected["reason"])
                self.assertEqual(decision.should_comment, expected["should_comment"])

    def test_same_repo_pull_request_with_secret_is_allowed(self) -> None:
        decision = trust_policy.evaluate_trigger_trust(
            {
                "event_name": "pull_request",
                "pr_is_fork": "false",
                "cursor_api_key_present": True,
            }
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "pull_request_with_secret")
        self.assertTrue(decision.should_comment)

    def test_fork_pull_request_without_secret_is_skipped(self) -> None:
        decision = trust_policy.evaluate_trigger_trust(
            {
                "event_name": "pull_request",
                "pr_is_fork": "true",
                "cursor_api_key_present": False,
            }
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "fork_pull_request_without_secret")
        self.assertFalse(decision.should_comment)

    def test_issue_comment_requires_trusted_author_association(self) -> None:
        decision = trust_policy.evaluate_trigger_trust(
            {
                "event_name": "issue_comment",
                "command_prompt_source": "slash_command",
                "comment_author_association": "CONTRIBUTOR",
                "trusted_author_associations": "OWNER,MEMBER,COLLABORATOR",
                "cursor_api_key_present": True,
            }
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "untrusted_author_association")
        self.assertFalse(decision.should_comment)

    def test_issue_comment_allows_default_trusted_association(self) -> None:
        decision = trust_policy.evaluate_trigger_trust(
            {
                "event_name": "issue_comment",
                "command_prompt_source": "slash_command",
                "comment_author_association": "COLLABORATOR",
                "cursor_api_key_present": True,
            }
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "trusted_issue_comment_command")


class FixtureRegressionTests(unittest.TestCase):
    def test_pr_regression_fixtures_match_prompt_parser_render_contract(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "pr_regression"
        fixture_paths = fixtures.discover_fixture_paths(fixture_root)

        self.assertGreaterEqual(len(fixture_paths), 5)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                result = fixtures.run_fixture(fixture)

                self.assertEqual(fixtures.validate_fixture(fixture, result), [])

    def test_quality_gate_fixtures_match_prompt_parser_render_contract(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "quality_gate"
        fixture_paths = fixtures.discover_fixture_paths(fixture_root)

        self.assertGreaterEqual(len(fixture_paths), 1)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                result = fixtures.run_fixture(fixture)

                self.assertEqual(fixtures.validate_fixture(fixture, result), [])

    def test_pr_regression_fixtures_have_capability_trace_files(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "pr_regression"
        for fixture_path in fixtures.discover_fixture_paths(fixture_root):
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                capabilities_path = fixture_path.parent / "capabilities.txt"
                self.assertTrue(capabilities_path.exists())
                capabilities = [
                    line.strip()
                    for line in capabilities_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual(capabilities, fixture["capability_ids"])

    def test_quality_gate_fixtures_have_capability_trace_files(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "quality_gate"
        for fixture_path in fixtures.discover_fixture_paths(fixture_root):
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                capabilities_path = fixture_path.parent / "capabilities.txt"
                self.assertTrue(capabilities_path.exists())
                capabilities = [
                    line.strip()
                    for line in capabilities_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual(capabilities, fixture["capability_ids"])

    def test_config_invalid_fixtures_have_capability_trace_files(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "config_invalid"
        for fixture_path in fixtures.discover_fixture_paths(fixture_root):
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                capabilities_path = fixture_path.parent / "capabilities.txt"
                self.assertTrue(capabilities_path.exists())
                capabilities = [
                    line.strip()
                    for line in capabilities_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual(capabilities, fixture["capability_ids"])

    def test_fixture_capabilities_are_tracked_in_parity_scorecard(self) -> None:
        scorecard = (ROOT / "docs" / "parity-scorecard.md").read_text(encoding="utf-8")
        fixture_ids = set()
        for fixture_path in (ROOT / "tests" / "fixtures").rglob("*.json"):
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            fixture_ids.update(fixture.get("capability_ids") or [])
        for capability_id in sorted(fixture_ids):
            with self.subTest(capability_id=capability_id):
                self.assertIn(f"| {capability_id} |", scorecard)


class ComparisonProtocolTests(unittest.TestCase):
    def test_comparison_protocol_documents_clean_room_required_fields(self) -> None:
        reports_dir = ROOT / "docs" / "parity-reports"
        readme = (reports_dir / "README.md").read_text(encoding="utf-8")
        template = (reports_dir / "template.md").read_text(encoding="utf-8")
        normalized_readme = " ".join(readme.split())

        self.assertIn("Do not copy PR-Agent source code", normalized_readme)
        self.assertIn("Gap decision and owner document", normalized_readme)
        self.assertIn("Decision: backlog | deferred | non-goal", template)
        self.assertIn("Cursor-native evidence", template)

    def test_initial_comparison_gap_log_classifies_every_gap(self) -> None:
        report = (ROOT / "docs" / "parity-reports" / "2026-05-12-initial-gap-log.md").read_text(
            encoding="utf-8"
        )

        self.assertGreaterEqual(report.count("| sample-"), 5)
        gap_sections = [section for section in report.split("\n### ") if section.startswith("GAP-")]
        self.assertGreaterEqual(len(gap_sections), 5)
        for section in gap_sections:
            with self.subTest(gap=section.splitlines()[0]):
                self.assertRegex(section, r"Decision: (backlog|deferred|non-goal)")
                self.assertIn("Capability/status target:", section)
                self.assertIn("Release impact:", section)


class AcceptanceRubricTests(unittest.TestCase):
    REQUIRED_FIELDS = [
        "real_issue_found",
        "false_positive_count",
        "missed_issue_count",
        "evidence_quality",
        "command_intent_respected",
        "output_conciseness",
        "diagnostics_usefulness",
        "skipped_content_transparency",
        "follow_up_action",
    ]

    def test_acceptance_rubric_documents_required_fields_and_clean_room_boundary(self) -> None:
        rubric = (ROOT / "docs" / "acceptance-rubric.md").read_text(encoding="utf-8")

        self.assertIn("ACCEPTANCE-RUBRIC-P1", rubric)
        self.assertIn("Do not copy PR-Agent source code", " ".join(rubric.split()))
        for field in self.REQUIRED_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", rubric)

    def test_every_pr_regression_fixture_has_human_acceptance_record(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "pr_regression"
        for fixture_path in fixtures.discover_fixture_paths(fixture_root):
            with self.subTest(fixture=fixture_path.parent.name):
                fixture = fixtures.load_fixture(fixture_path)
                human_eval_path = fixture_path.parent / "human_eval.md"
                self.assertTrue(human_eval_path.exists())
                human_eval = human_eval_path.read_text(encoding="utf-8")

                self.assertIn("# Human Evaluation", human_eval)
                self.assertIn("ACCEPTANCE-RUBRIC-P1", human_eval)
                for capability_id in fixture["capability_ids"]:
                    self.assertIn(capability_id, human_eval)
                for field in self.REQUIRED_FIELDS:
                    self.assertRegex(human_eval, rf"(?m)^- {field}: .+", msg=f"missing {field}")


class RunnerContractTests(unittest.TestCase):
    def test_run_cursor_result_records_success_contract(self) -> None:
        completed = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(runner, "run_command", return_value=completed) as run_command:
            result = runner.run_cursor_result("prompt", {"model": "auto", "resolved_command": "review"})

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.raw_text, "ok")
        self.assertEqual(result.failure_kind, "none")
        self.assertEqual(result.model, "auto")
        self.assertEqual(result.command_name, "review")
        self.assertEqual(result.timeout_seconds, 600)
        self.assertEqual(result.diagnostics["requested_model"], "auto")
        self.assertEqual(result.diagnostics["max_cursor_calls"], 1)
        self.assertEqual(result.diagnostics["cursor_calls_attempted"], 1)
        run_command.assert_called_once()
        self.assertEqual(run_command.call_args.kwargs["timeout"], 600)

    def test_run_cursor_result_classifies_install_failure(self) -> None:
        with mock.patch.object(runner, "run_command", side_effect=FileNotFoundError()):
            result = runner.run_cursor_result("prompt", {"model": "auto"})

        self.assertEqual(result.exit_code, 127)
        self.assertEqual(result.failure_kind, "install")
        self.assertIn("not found", result.stderr)

    def test_run_cursor_result_classifies_auth_model_runtime_and_output_failures(self) -> None:
        cases = [
            (1, "", "Unauthorized API key", "auth"),
            (2, "", "Unknown model requested", "model"),
            (3, "", "Unexpected failure", "runtime"),
            (0, "   ", "", "output"),
        ]
        for exit_code, stdout, stderr, expected in cases:
            with self.subTest(expected=expected):
                completed = mock.Mock(returncode=exit_code, stdout=stdout, stderr=stderr)
                with mock.patch.object(runner, "run_command", return_value=completed):
                    result = runner.run_cursor_result("prompt", {"model": "auto"})

                self.assertEqual(result.failure_kind, expected)

    def test_run_cursor_result_classifies_timeout_as_runtime(self) -> None:
        timeout = runner.subprocess.TimeoutExpired(cmd=["agent"], timeout=5, output="partial", stderr="late")
        with mock.patch.object(runner, "run_command", side_effect=timeout):
            result = runner.run_cursor_result("prompt", {"model": "auto", "timeout_seconds": 5})

        self.assertEqual(result.exit_code, 124)
        self.assertEqual(result.raw_text, "partial")
        self.assertEqual(result.failure_kind, "runtime")
        self.assertIn("timed out", result.stderr)


class EntrypointTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_main_orchestrates_engine_modules_without_cursor_api(self) -> None:
        fake_context = context.ReviewContext(
            diff_text="diff --git a/a.py b/a.py",
            stat=" a.py | 1 +",
            truncated=False,
            meta={"files": ["a.py"]},
        )
        fake_output = """
<review_markdown>No issues found.</review_markdown>
<findings_json>[]</findings_json>
"""
        fake_runner_result = runner.CursorRunResult(
            raw_text=fake_output,
            exit_code=0,
            stderr="",
            duration_seconds=0.01,
            retry_count=0,
            failure_kind="none",
            model="auto",
            command_name="review",
            timeout_seconds=600,
            diagnostics={
                "runner": "cursor_cli",
                "command": "review",
                "requested_model": "auto",
                "exit_code": 0,
                "failure_kind": "none",
                "duration_seconds": 0.01,
                "retry_count": 0,
                "timeout_seconds": 600,
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "INPUT_COMMAND": "review",
                "INPUT_ENABLED_COMMANDS": "review",
                "INPUT_COMMENT_BODY": "/cursor-review --focus=security,tests --max-findings=2\nCheck auth.",
                "INPUT_CONFIG_PATH": str(Path(tmp) / "missing.yml"),
                "INPUT_EVENT_NAME": "issue_comment",
                "INPUT_COMMENT_AUTHOR_ASSOCIATION": "MEMBER",
                "CURSOR_API_KEY": "test-key",
                "GITHUB_OUTPUT": str(Path(tmp) / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(Path(tmp) / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "build_review_context", return_value=fake_context):
                    with mock.patch.object(cursor_review, "run_cursor_result", return_value=fake_runner_result) as run_cursor:
                        cwd = os.getcwd()
                        os.chdir(tmp)
                        try:
                            exit_code = cursor_review.main()
                        finally:
                            os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            self.assertIn("No issues found.", (Path(tmp) / "cursor_review.md").read_text(encoding="utf-8"))
            self.assertIn("Lifecycle final state: `published`", (Path(tmp) / "cursor_review.md").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((Path(tmp) / "findings.json").read_text(encoding="utf-8")), [])
            self.assertIn("resolved_command", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertIn("comment_marker", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertIn("run_metadata_json", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertIn("ci_policy_json", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertFalse((Path(tmp) / "cursor_review_prompt.txt").exists())
            self.assertFalse((Path(tmp) / "cursor_review_raw.txt").exists())
            prompt = run_cursor.call_args.args[0]
            self.assertIn("Maximum findings: 2.", prompt)
            self.assertIn("Review focus: security, tests.", prompt)
            self.assertIn("Check auth.", prompt)

    def test_main_local_dry_run_builds_prompt_and_render_without_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git(root, "init")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test User")
            (root / ".cursor-review.yml").write_text("language: en\nmax_findings: 2\n", encoding="utf-8")
            (root / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "base")
            (root / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self._git(root, "add", "app.py")
            self._git(root, "commit", "-m", "head")
            stored_output = root / "stored-output.txt"
            stored_output.write_text(
                """
<review_markdown>Stored dry-run result.</review_markdown>
<findings_json>[]</findings_json>
""".strip(),
                encoding="utf-8",
            )
            env = {
                "INPUT_COMMAND": "review",
                "INPUT_ENABLED_COMMANDS": "review",
                "INPUT_CONFIG_PATH": ".cursor-review.yml",
                "INPUT_EVENT_NAME": "pull_request",
                "INPUT_PR_IS_FORK": "false",
                "GITHUB_OUTPUT": str(root / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "run_cursor_result") as run_cursor:
                    cwd = os.getcwd()
                    os.chdir(root)
                    try:
                        exit_code = cursor_review.main(["--dry-run", "--dry-run-output", str(stored_output)])
                    finally:
                        os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            run_cursor.assert_not_called()
            prompt = (root / "cursor_review_prompt.txt").read_text(encoding="utf-8")
            rendered = (root / "cursor_review.md").read_text(encoding="utf-8")
            diagnostics = json.loads((root / "cursor_review_diagnostics.json").read_text(encoding="utf-8"))
            outputs = (root / "outputs.txt").read_text(encoding="utf-8")
            self.assertIn("+    return 2", prompt)
            self.assertIn("Stored dry-run result.", rendered)
            self.assertIn("Runner: `local_dry_run`", rendered)
            self.assertIn("Cursor contacted: `false`", rendered)
            self.assertIn("Lifecycle final state: `published`", rendered)
            self.assertIn("Dry-run output source: `stored_file`", rendered)
            self.assertEqual(json.loads((root / "findings.json").read_text(encoding="utf-8")), [])
            self.assertEqual(diagnostics["mode"], "local_dry_run")
            self.assertFalse(diagnostics["cursor_contacted"])
            self.assertEqual(diagnostics["lifecycle"]["final_state"], "published")
            self.assertIn("should_comment<<", outputs)
            self.assertIn("false", outputs)

    def test_main_skips_untrusted_issue_comment_before_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "INPUT_COMMAND": "review",
                "INPUT_ENABLED_COMMANDS": "review",
                "INPUT_COMMENT_BODY": "/cursor-review please run",
                "INPUT_CONFIG_PATH": str(Path(tmp) / "missing.yml"),
                "INPUT_EVENT_NAME": "issue_comment",
                "INPUT_COMMENT_AUTHOR_ASSOCIATION": "CONTRIBUTOR",
                "CURSOR_API_KEY": "test-key",
                "GITHUB_OUTPUT": str(Path(tmp) / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(Path(tmp) / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "build_review_context") as build_context:
                    with mock.patch.object(cursor_review, "run_cursor_result") as run_cursor:
                        cwd = os.getcwd()
                        os.chdir(tmp)
                        try:
                            exit_code = cursor_review.main()
                        finally:
                            os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            build_context.assert_not_called()
            run_cursor.assert_not_called()
            rendered = (Path(tmp) / "cursor_review.md").read_text(encoding="utf-8")
            outputs = (Path(tmp) / "outputs.txt").read_text(encoding="utf-8")
            self.assertIn("untrusted_author_association", rendered)
            self.assertIn("Lifecycle final state: `skipped`", rendered)
            self.assertIn("should_comment<<", outputs)
            self.assertIn("false", outputs)

    def test_main_renders_static_help_without_cursor_or_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "INPUT_COMMAND": "review",
                "INPUT_ENABLED_COMMANDS": "review,ask",
                "INPUT_COMMENT_BODY": "/cursor-help",
                "INPUT_CONFIG_PATH": str(Path(tmp) / "missing.yml"),
                "INPUT_EVENT_NAME": "issue_comment",
                "INPUT_COMMENT_AUTHOR_ASSOCIATION": "CONTRIBUTOR",
                "GITHUB_OUTPUT": str(Path(tmp) / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(Path(tmp) / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "build_review_context") as build_context:
                    with mock.patch.object(cursor_review, "run_cursor_result") as run_cursor:
                        cwd = os.getcwd()
                        os.chdir(tmp)
                        try:
                            exit_code = cursor_review.main()
                        finally:
                            os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            build_context.assert_not_called()
            run_cursor.assert_not_called()
            rendered = (Path(tmp) / "cursor_review.md").read_text(encoding="utf-8")
            outputs = (Path(tmp) / "outputs.txt").read_text(encoding="utf-8")
            self.assertIn("Cursor Review Action Help", rendered)
            self.assertIn("Cursor contacted: `false`", rendered)
            self.assertIn("Lifecycle final state: `published`", rendered)
            self.assertNotIn("/cursor-improve -", rendered)
            self.assertEqual(json.loads((Path(tmp) / "findings.json").read_text(encoding="utf-8")), [])
            self.assertIn("resolved_command", outputs)
            self.assertIn("help", outputs)
            self.assertIn("should_comment", outputs)
            self.assertIn("true", outputs)

    def test_main_repairs_invalid_structured_output_when_budget_allows(self) -> None:
        fake_context = context.ReviewContext(
            diff_text="diff --git a/a.py b/a.py",
            stat=" a.py | 1 +",
            truncated=False,
            meta={"files": ["a.py"]},
        )
        invalid_output = """
<review_markdown>Check this.</review_markdown>
<findings_json>{not valid}</findings_json>
"""
        repaired_output = """
<review_markdown>Check this.</review_markdown>
<findings_json>[{"severity":"low","file":"a.py","line":1,"title":"Check","body":"Body","confidence":"high"}]</findings_json>
"""
        first_result = runner.CursorRunResult(
            raw_text=invalid_output,
            exit_code=0,
            stderr="",
            duration_seconds=0.01,
            retry_count=0,
            failure_kind="none",
            model="auto",
            command_name="review",
            timeout_seconds=600,
            diagnostics={
                "runner": "cursor_cli",
                "command": "review",
                "requested_model": "auto",
                "exit_code": 0,
                "failure_kind": "none",
                "duration_seconds": 0.01,
                "retry_count": 0,
                "timeout_seconds": 600,
                "max_cursor_calls": 2,
                "cursor_calls_attempted": 1,
            },
        )
        repair_result = runner.CursorRunResult(
            raw_text=repaired_output,
            exit_code=0,
            stderr="",
            duration_seconds=0.01,
            retry_count=0,
            failure_kind="none",
            model="auto",
            command_name="review",
            timeout_seconds=600,
            diagnostics={
                "runner": "cursor_cli",
                "command": "review",
                "requested_model": "auto",
                "exit_code": 0,
                "failure_kind": "none",
                "duration_seconds": 0.01,
                "retry_count": 0,
                "timeout_seconds": 600,
                "max_cursor_calls": 2,
                "cursor_calls_attempted": 1,
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "INPUT_COMMAND": "review",
                "INPUT_ENABLED_COMMANDS": "review",
                "INPUT_MAX_CURSOR_CALLS": "2",
                "INPUT_CONFIG_PATH": str(Path(tmp) / "missing.yml"),
                "INPUT_EVENT_NAME": "pull_request",
                "INPUT_PR_IS_FORK": "false",
                "CURSOR_API_KEY": "test-key",
                "GITHUB_OUTPUT": str(Path(tmp) / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(Path(tmp) / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "build_review_context", return_value=fake_context):
                    with mock.patch.object(
                        cursor_review,
                        "run_cursor_result",
                        side_effect=[first_result, repair_result],
                    ) as run_cursor:
                        cwd = os.getcwd()
                        os.chdir(tmp)
                        try:
                            exit_code = cursor_review.main()
                        finally:
                            os.chdir(cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(run_cursor.call_count, 2)
            repair_prompt = run_cursor.call_args_list[1].args[0]
            self.assertIn("Repair the previous Cursor review response", repair_prompt)
            self.assertEqual(
                json.loads((Path(tmp) / "findings.json").read_text(encoding="utf-8"))[0]["title"],
                "Check",
            )
            rendered = (Path(tmp) / "cursor_review.md").read_text(encoding="utf-8")
            self.assertIn("Parser repair retry count: `1`", rendered)
            self.assertIn("Parser repair succeeded: `true`", rendered)
            self.assertIn("Cursor calls attempted: `2`", rendered)


if __name__ == "__main__":
    unittest.main()
