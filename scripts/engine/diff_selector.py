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


def classify_files(files: List[str], settings: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    include_patterns = split_csv(settings.get("include_patterns"))
    exclude_patterns = split_csv(settings.get("exclude_patterns"))

    selected = []
    skipped = []
    for file_name in files:
        include_ok = True
        if include_patterns:
            include_ok = any(fnmatch.fnmatch(file_name, pattern) for pattern in include_patterns)
        exclude_hit = any(fnmatch.fnmatch(file_name, pattern) for pattern in exclude_patterns)
        if include_ok and not exclude_hit:
            selected.append(file_name)
        elif not include_ok:
            skipped.append({"path": file_name, "reason": "not_included"})
        else:
            skipped.append({"path": file_name, "reason": "excluded"})
    return selected, skipped


def selected_files(files: List[str], settings: Dict[str, Any]) -> List[str]:
    selected, _ = classify_files(files, settings)
    return selected


def _file_diff(file_name: str, base: str, head: str, range_label: str, filter_mode: str) -> str:
    if filter_mode == "diff_context":
        diff_cmd = ["git", "diff", "-U20", range_label, "--", file_name] if base else ["git", "show", "--format=", "HEAD", "--", file_name]
        return run_command(diff_cmd, check=False).stdout

    if filter_mode == "file":
        revision = head or "HEAD"
        show = run_command(["git", "show", f"{revision}:{file_name}"], check=False)
        if show.returncode == 0:
            return f"--- FILE: {file_name} ---\n{show.stdout}"
        return ""

    diff_cmd = ["git", "diff", "-U3", range_label, "--", file_name] if base else ["git", "show", "--format=", "HEAD", "--", file_name]
    return run_command(diff_cmd, check=False).stdout


def _select_diff_chunks(files: List[str], settings: Dict[str, Any], base: str, head: str, range_label: str, filter_mode: str) -> Tuple[str, bool, int, List[Dict[str, Any]], List[Dict[str, str]]]:
    max_bytes = to_int(settings.get("max_diff_bytes"), DEFAULTS["max_diff_bytes"])
    chunks = []
    reviewed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    used_bytes = 0
    truncated = False

    for index, file_name in enumerate(files):
        chunk = _file_diff(file_name, base, head, range_label, filter_mode)
        chunk_bytes = len(chunk.encode("utf-8", errors="replace"))
        if chunk_bytes == 0:
            skipped.append({"path": file_name, "reason": "empty_diff"})
            continue

        if used_bytes + chunk_bytes <= max_bytes:
            chunks.append(chunk)
            used_bytes += chunk_bytes
            reviewed.append({"path": file_name, "bytes": chunk_bytes, "status": "included"})
            continue

        remaining = max_bytes - used_bytes
        if remaining > 0 and not chunks:
            encoded = chunk.encode("utf-8", errors="replace")
            partial = encoded[:remaining].decode("utf-8", errors="replace")
            chunks.append(partial)
            used_bytes += len(partial.encode("utf-8", errors="replace"))
            reviewed.append({"path": file_name, "bytes": chunk_bytes, "status": "partial"})
            skipped.append({"path": file_name, "reason": "max_diff_bytes_partial"})
        else:
            skipped.append({"path": file_name, "reason": "max_diff_bytes"})

        skipped.extend({"path": remaining_file, "reason": "max_diff_bytes"} for remaining_file in files[index + 1 :])
        truncated = True
        break

    return "\n\n".join(chunks), truncated, used_bytes, reviewed, skipped


def build_diff(settings: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
    base, head, range_label = diff_range(settings)
    all_files = changed_files(base, head)
    files, skipped_files = classify_files(all_files, settings)
    max_bytes = to_int(settings.get("max_diff_bytes"), DEFAULTS["max_diff_bytes"])
    filter_mode = str(settings.get("filter_mode", "added"))

    if not files:
        return "", "No changed files selected.", False, {
            "base": base,
            "head": head,
            "range": range_label,
            "files": [],
            "changed_files": all_files,
            "reviewed_files": [],
            "skipped_files": skipped_files,
            "filter_mode": filter_mode,
        }

    stat_cmd = ["git", "diff", "--stat", range_label, "--"] + files if base else ["git", "show", "--stat", "--format=", "HEAD"]
    stat = run_command(stat_cmd, check=False).stdout

    diff_text, truncated, diff_bytes, reviewed_files, budget_skipped_files = _select_diff_chunks(files, settings, base, head, range_label, filter_mode)
    skipped_files.extend(budget_skipped_files)
    if truncated:
        diff_text += "\n\n[Diff truncated by cursor-review-action due to max_diff_bytes]\n"

    meta = {
        "base": base,
        "head": head,
        "range": range_label,
        "files": files,
        "changed_files": all_files,
        "reviewed_files": reviewed_files,
        "skipped_files": skipped_files,
        "filter_mode": filter_mode,
        "max_diff_bytes": max_bytes,
        "diff_bytes": diff_bytes,
    }
    return diff_text, stat, truncated, meta
