import fnmatch
from typing import Any, Dict, List, Tuple

from .budget import normalized_budget_settings
from .config import split_csv
from .diff_index import build_diff_index
from .runner import run_command
from .scope import apply_review_scope


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


def _apply_file_budget(files: List[str], settings: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    max_files = normalized_budget_settings(settings)["max_files"]
    if max_files <= 0 or len(files) <= max_files:
        return files, []
    return files[:max_files], [{"path": file_name, "reason": "max_files"} for file_name in files[max_files:]]


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


def _count_hunks(chunk: str) -> int:
    return sum(1 for line in chunk.splitlines() if line.startswith("@@ "))


def _limit_hunks(chunk: str, max_hunks: int) -> Tuple[str, int, bool]:
    if max_hunks <= 0:
        return chunk, _count_hunks(chunk), False

    lines = chunk.splitlines(keepends=True)
    hunk_indexes = [index for index, line in enumerate(lines) if line.startswith("@@ ")]
    if len(hunk_indexes) <= max_hunks:
        return chunk, len(hunk_indexes), False

    cutoff = hunk_indexes[max_hunks]
    limited = "".join(lines[:cutoff]).rstrip()
    limited = f"{limited}\n[Diff truncated by cursor-review-action due to max_hunks]\n"
    return limited, max_hunks, True


def _select_diff_chunks(files: List[str], settings: Dict[str, Any], base: str, head: str, range_label: str, filter_mode: str) -> Tuple[str, bool, int, int, List[Dict[str, Any]], List[Dict[str, str]], List[str]]:
    budgets = normalized_budget_settings(settings)
    max_bytes = budgets["max_diff_bytes"]
    max_hunks = budgets["max_hunks"]
    chunks = []
    reviewed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    truncation_reasons: List[str] = []
    used_bytes = 0
    used_hunks = 0
    truncated = False

    for index, file_name in enumerate(files):
        if max_hunks > 0 and used_hunks >= max_hunks:
            skipped.extend({"path": remaining_file, "reason": "max_hunks"} for remaining_file in files[index:])
            truncation_reasons.append("max_hunks")
            truncated = True
            break

        chunk = _file_diff(file_name, base, head, range_label, filter_mode)
        raw_hunks = _count_hunks(chunk)
        hunk_truncated = False
        chunk_hunks = raw_hunks
        if max_hunks > 0 and raw_hunks > 0:
            remaining_hunks = max_hunks - used_hunks
            chunk, chunk_hunks, hunk_truncated = _limit_hunks(chunk, remaining_hunks)

        chunk_bytes = len(chunk.encode("utf-8", errors="replace"))
        if chunk_bytes == 0:
            skipped.append({"path": file_name, "reason": "empty_diff"})
            continue

        if used_bytes + chunk_bytes <= max_bytes:
            chunks.append(chunk)
            used_bytes += chunk_bytes
            used_hunks += chunk_hunks
            reviewed.append(
                {
                    "path": file_name,
                    "bytes": chunk_bytes,
                    "hunks": chunk_hunks,
                    "status": "partial" if hunk_truncated else "included",
                }
            )
            if hunk_truncated:
                skipped.append({"path": file_name, "reason": "max_hunks_partial"})
                skipped.extend({"path": remaining_file, "reason": "max_hunks"} for remaining_file in files[index + 1 :])
                truncation_reasons.append("max_hunks")
                truncated = True
                break
            continue

        remaining = max_bytes - used_bytes
        if remaining > 0 and not chunks:
            encoded = chunk.encode("utf-8", errors="replace")
            partial = encoded[:remaining].decode("utf-8", errors="replace")
            chunks.append(partial)
            used_bytes += len(partial.encode("utf-8", errors="replace"))
            used_hunks += _count_hunks(partial)
            reviewed.append({"path": file_name, "bytes": chunk_bytes, "hunks": chunk_hunks, "status": "partial"})
            skipped.append({"path": file_name, "reason": "max_diff_bytes_partial"})
        else:
            skipped.append({"path": file_name, "reason": "max_diff_bytes"})

        skipped.extend({"path": remaining_file, "reason": "max_diff_bytes"} for remaining_file in files[index + 1 :])
        truncation_reasons.append("max_diff_bytes")
        truncated = True
        break

    return "\n\n".join(chunks), truncated, used_bytes, used_hunks, reviewed, skipped, truncation_reasons


def build_diff(settings: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
    base, head, range_label = diff_range(settings)
    all_files = changed_files(base, head)
    scoped_files, scope_skipped_files, scope_diagnostics = apply_review_scope(all_files, settings)
    files, skipped_files = classify_files(scoped_files, settings)
    skipped_files = scope_skipped_files + skipped_files
    files, file_budget_skipped = _apply_file_budget(files, settings)
    skipped_files.extend(file_budget_skipped)
    budgets = normalized_budget_settings(settings)
    max_bytes = budgets["max_diff_bytes"]
    filter_mode = str(settings.get("filter_mode", "added"))
    truncation_reasons = ["max_files"] if file_budget_skipped else []

    if not files:
        diff_index = build_diff_index("", skipped_files)
        return "", "No changed files selected.", False, {
            "base": base,
            "head": head,
            "range": range_label,
            "files": [],
            "changed_files": all_files,
            "reviewed_files": [],
            "skipped_files": skipped_files,
            "scope": scope_diagnostics,
            "filter_mode": filter_mode,
            "budget": budgets,
            "truncation_reasons": truncation_reasons,
            "diff_index": diff_index,
        }

    stat_cmd = ["git", "diff", "--stat", range_label, "--"] + files if base else ["git", "show", "--stat", "--format=", "HEAD", "--"] + files
    stat = run_command(stat_cmd, check=False).stdout

    diff_text, truncated, diff_bytes, hunk_count, reviewed_files, budget_skipped_files, chunk_truncation_reasons = _select_diff_chunks(files, settings, base, head, range_label, filter_mode)
    skipped_files.extend(budget_skipped_files)
    truncation_reasons.extend(reason for reason in chunk_truncation_reasons if reason not in truncation_reasons)
    truncated = truncated or bool(file_budget_skipped)
    if truncated and "max_diff_bytes" in truncation_reasons and "[Diff truncated by cursor-review-action due to max_diff_bytes]" not in diff_text:
        diff_text += "\n\n[Diff truncated by cursor-review-action due to max_diff_bytes]\n"
    diff_index = build_diff_index(diff_text, skipped_files)

    meta = {
        "base": base,
        "head": head,
        "range": range_label,
        "files": files,
        "changed_files": all_files,
        "reviewed_files": reviewed_files,
        "skipped_files": skipped_files,
        "scope": scope_diagnostics,
        "filter_mode": filter_mode,
        "max_diff_bytes": max_bytes,
        "diff_bytes": diff_bytes,
        "hunks": hunk_count,
        "budget": budgets,
        "truncation_reasons": truncation_reasons,
        "diff_index": diff_index,
    }
    return diff_text, stat, truncated, meta
