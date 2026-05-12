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
from engine import commands, config, context, parser, prompts, render, runner  # noqa: E402


class CommandTests(unittest.TestCase):
    def test_derives_slash_command_and_prompt(self) -> None:
        settings = {
            "command": "review",
            "comment_body": "/cursor-ask\nWhy did this change?",
        }

        command, user_prompt = commands.derive_command_and_prompt(settings)

        self.assertEqual(command, "ask")
        self.assertEqual(user_prompt, "Why did this change?")

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
        self.assertIn('"diff_truncated": false', prompt)

    def test_parse_agent_output_formats_valid_findings_json(self) -> None:
        raw = """
<review_markdown>No issues.</review_markdown>
<findings_json>[{"severity":"low","file":"a.py"}]</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw)

        self.assertEqual(markdown, "No issues.")
        self.assertTrue(parsed_ok)
        self.assertEqual(json.loads(findings_json), [{"severity": "low", "file": "a.py"}])

    def test_parse_agent_output_falls_back_to_markdown_on_invalid_json(self) -> None:
        raw = """
<review_markdown>Check this.</review_markdown>
<findings_json>{not valid}</findings_json>
"""

        markdown, findings_json, parsed_ok = parser.parse_agent_output(raw)

        self.assertEqual(markdown, "Check this.")
        self.assertEqual(findings_json, "{not valid}")
        self.assertFalse(parsed_ok)

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
                "INPUT_CONFIG_PATH": str(Path(tmp) / "missing.yml"),
                "GITHUB_OUTPUT": str(Path(tmp) / "outputs.txt"),
                "GITHUB_STEP_SUMMARY": str(Path(tmp) / "summary.md"),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cursor_review, "build_review_context", return_value=fake_context):
                    with mock.patch.object(cursor_review, "run_cursor_result", return_value=fake_runner_result):
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


if __name__ == "__main__":
    unittest.main()
