import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .budget import normalized_budget_settings


@dataclass
class CursorRunResult:
    raw_text: str
    exit_code: int
    stderr: str
    duration_seconds: float
    retry_count: int
    failure_kind: str
    model: str
    command_name: str
    timeout_seconds: int
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def run_command(command: List[str], check: bool = False, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=timeout,
    )


def _classify_failure(exit_code: int, stdout: str, stderr: str, timed_out: bool = False) -> str:
    combined = f"{stdout}\n{stderr}".lower()
    if timed_out:
        return "runtime"
    if exit_code == 127:
        return "install"
    if exit_code != 0 and any(token in combined for token in ("auth", "api key", "unauthorized", "forbidden", "login")):
        return "auth"
    if exit_code != 0 and any(token in combined for token in ("model", "unsupported", "unknown", "not available")):
        return "model"
    if exit_code != 0:
        return "runtime"
    if not stdout.strip():
        return "output"
    return "none"


def _timeout_seconds(settings: Dict[str, Any]) -> int:
    return normalized_budget_settings(settings)["timeout_seconds"]


def _write_prompt_file(prompt: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix="cursor-review-prompt-",
        suffix=".txt",
        delete=False,
    ) as handle:
        handle.write(prompt)
        return handle.name


def _prompt_file_reference(prompt_file: str) -> str:
    return f"Read the full cursor-review prompt from this file and follow it exactly: {prompt_file}"


def _remove_prompt_file(prompt_file: str) -> None:
    try:
        os.unlink(prompt_file)
    except OSError:
        pass


def run_cursor_result(prompt: str, settings: Dict[str, Any]) -> CursorRunResult:
    model = str(settings.get("model", "auto"))
    command_name = str(settings.get("resolved_command") or settings.get("command") or "review")
    budgets = normalized_budget_settings(settings)
    timeout_seconds = _timeout_seconds(settings)
    prompt_file = _write_prompt_file(prompt)
    command = ["agent", "-p", "--trust", "--model", model, "--output-format", "text", _prompt_file_reference(prompt_file)]
    started = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code = 0
    timed_out = False

    try:
        try:
            result = run_command(command, check=False, timeout=timeout_seconds)
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode
        except FileNotFoundError:
            exit_code = 127
            stderr = "Cursor CLI `agent` was not found. Enable install-cursor or install Cursor CLI first."
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = f"Cursor CLI timed out after {timeout_seconds} seconds."
            if exc.stderr:
                stderr = f"{stderr}\n{exc.stderr}"
    finally:
        _remove_prompt_file(prompt_file)

    duration_seconds = time.monotonic() - started
    failure_kind = _classify_failure(exit_code, stdout, stderr, timed_out=timed_out)
    diagnostics = {
        "runner": "cursor_cli",
        "command": command_name,
        "requested_model": model,
        "exit_code": exit_code,
        "failure_kind": failure_kind,
        "duration_seconds": round(duration_seconds, 3),
        "retry_count": 0,
        "timeout_seconds": timeout_seconds,
        "max_cursor_calls": budgets["max_cursor_calls"],
        "cursor_calls_attempted": 1,
    }
    return CursorRunResult(
        raw_text=stdout,
        exit_code=exit_code,
        stderr=stderr,
        duration_seconds=duration_seconds,
        retry_count=0,
        failure_kind=failure_kind,
        model=model,
        command_name=command_name,
        timeout_seconds=timeout_seconds,
        diagnostics=diagnostics,
    )


def run_cursor(prompt: str, settings: Dict[str, Any]) -> Tuple[int, str, str]:
    result = run_cursor_result(prompt, settings)
    return result.exit_code, result.raw_text, result.stderr
