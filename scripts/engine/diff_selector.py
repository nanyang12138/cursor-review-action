import fnmatch
from typing import Any, Dict, List, Tuple

from .config import DEFAULTS, split_csv, to_int
from .runner import run_command


def diff_range(settings: Dict[str, Any]) -> Tuple[str, str, str]:
    base = str(settings.get("base_sha", "") or "").strip()
    head = str(settings.get("head_sha", "") or "").strip()
    if base and head:
        return base, head, f"{base}...{head}"

    rev_parse = run_command(["git", "rev-parse", "--verify", "HEAD~1"], check=False)
    if rev_parse.returncode == 0:
        return "HEAD~1", "HEAD", "HEAD~1...HEAD"
    return "", "HEAD", "HEAD"


def changed_files(base: str, head: str) -> List[str]:
    if base and head:
        result = run_command(["git", "diff", "--name-only", f"{base}...{head}"], check=False)
    else:
        result = run_command(["git", "show", "--name-only", "--format=", "HEAD"], check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def selected_files(files: List[str], settings: Dict[str, Any]) -> List[str]:
    include_patterns = split_csv(settings.get("include_patterns"))
    exclude_patterns = split_csv(settings.get("exclude_patterns"))

    selected = []
    for file_name in files:
        include_ok = True
        if include_patterns:
            include_ok = any(fnmatch.fnmatch(file_name, pattern) for pattern in include_patterns)
        exclude_hit = any(fnmatch.fnmatch(file_name, pattern) for pattern in exclude_patterns)
        if include_ok and not exclude_hit:
            selected.append(file_name)
    return selected


def build_diff(settings: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
    base, head, range_label = diff_range(settings)
    files = changed_files(base, head)
    files = selected_files(files, settings)
    max_bytes = to_int(settings.get("max_diff_bytes"), DEFAULTS["max_diff_bytes"])
    filter_mode = str(settings.get("filter_mode", "added"))

    if not files:
        return "", "No changed files selected.", False, {
            "base": base,
            "head": head,
            "range": range_label,
            "files": [],
            "filter_mode": filter_mode,
        }

    stat_cmd = ["git", "diff", "--stat", range_label, "--"] + files if base else ["git", "show", "--stat", "--format=", "HEAD"]
    stat = run_command(stat_cmd, check=False).stdout

    if filter_mode == "diff_context":
        diff_cmd = ["git", "diff", "-U20", range_label, "--"] + files
        diff_text = run_command(diff_cmd, check=False).stdout
    elif filter_mode == "file":
        chunks = []
        for file_name in files:
            show = run_command(["git", "show", f"{head}:{file_name}"], check=False) if head else run_command(["git", "show", f"HEAD:{file_name}"], check=False)
            if show.returncode == 0:
                chunks.append(f"--- FILE: {file_name} ---\n{show.stdout}")
        diff_text = "\n\n".join(chunks)
    else:
        diff_cmd = ["git", "diff", "-U3", range_label, "--"] + files if base else ["git", "show", "--format=", "HEAD"]
        diff_text = run_command(diff_cmd, check=False).stdout

    encoded = diff_text.encode("utf-8", errors="replace")
    truncated = len(encoded) > max_bytes
    if truncated:
        diff_text = encoded[:max_bytes].decode("utf-8", errors="replace")
        diff_text += "\n\n[Diff truncated by cursor-review-action due to max_diff_bytes]\n"

    meta = {
        "base": base,
        "head": head,
        "range": range_label,
        "files": files,
        "filter_mode": filter_mode,
        "max_diff_bytes": max_bytes,
        "diff_bytes": len(encoded),
    }
    return diff_text, stat, truncated, meta
