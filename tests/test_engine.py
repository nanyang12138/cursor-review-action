import json
import os
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
from engine import command_args, commands, config, context, diff_selector, parser, prompts, render, runner, run_state, trust_policy  # noqa: E402


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
        self.assertIn('"severity": "critical|high|medium|low"', prompt)
        self.assertIn('"diff_truncated": false', prompt)

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

    def test_parse_agent_output_formats_valid_findings_json(self) -> None:
        raw = """
<review_markdown>No issues.</review_markdown>
<findings_json>[{"severity":"low","file":"a.py"}]</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw)

        self.assertEqual(markdown, "No issues.")
        self.assertTrue(parsed_ok)
        self.assertEqual(json.loads(findings_json), [{"severity": "low", "file": "a.py"}])

    def test_parse_agent_output_accepts_command_json_object(self) -> None:
        raw = """
<review_markdown>It updates parser behavior.</review_markdown>
<findings_json>{"schema_version":"cursor-review-action/v1","command":"describe","summary":"Parser update"}</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw)

        self.assertEqual(markdown, "It updates parser behavior.")
        self.assertTrue(parsed_ok)
        self.assertEqual(json.loads(findings_json)["command"], "describe")

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
            {"resolved_command": "review", "model": "auto", "filter_mode": "added"},
        )

        self.assertIn("No issues.", rendered)
        self.assertIn("Diff truncated: `true`", rendered)
        self.assertIn("Files reviewed: `2`", rendered)
        self.assertIn("Files skipped: `0`", rendered)

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
            self.assertEqual(json.loads((Path(tmp) / "findings.json").read_text(encoding="utf-8")), [])
            self.assertIn("resolved_command", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertIn("comment_marker", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            self.assertIn("run_metadata_json", (Path(tmp) / "outputs.txt").read_text(encoding="utf-8"))
            prompt = run_cursor.call_args.args[0]
            self.assertIn("Maximum findings: 2.", prompt)
            self.assertIn("Review focus: security, tests.", prompt)
            self.assertIn("Check auth.", prompt)

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
            self.assertIn("should_comment<<", outputs)
            self.assertIn("false", outputs)

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
