import subprocess
from typing import Any, Dict, List, Tuple


def run_command(command: List[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def run_cursor(prompt: str, settings: Dict[str, Any]) -> Tuple[int, str, str]:
    model = str(settings.get("model", "auto"))
    command = ["agent", "-p", "--trust", "--model", model, "--output-format", "text", prompt]
    try:
        result = run_command(command, check=False)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", "Cursor CLI `agent` was not found. Enable install-cursor or install Cursor CLI first."
