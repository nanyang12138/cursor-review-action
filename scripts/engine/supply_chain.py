import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


SCHEMA_VERSION = "supply-chain/v1"
INTERNAL_TOP_LEVEL_MODULES = {"cursor_review", "engine"}
FALLBACK_STDLIB_MODULES = {
    "__future__",
    "argparse",
    "ast",
    "copy",
    "dataclasses",
    "datetime",
    "fnmatch",
    "json",
    "os",
    "pathlib",
    "re",
    "subprocess",
    "sys",
    "tempfile",
    "time",
    "typing",
    "unittest",
}


@dataclass(frozen=True)
class ImportViolation:
    file: str
    module: str
    line: int


def _stdlib_modules() -> Set[str]:
    return set(getattr(sys, "stdlib_module_names", set())) | FALLBACK_STDLIB_MODULES


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def _is_allowed_module(module: str, stdlib_modules: Set[str]) -> bool:
    if not module:
        return True
    top_level = _top_level(module)
    return (
        top_level in INTERNAL_TOP_LEVEL_MODULES
        or top_level in stdlib_modules
        or top_level.startswith("_")
    )


def discover_python_files(paths: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(
                candidate
                for candidate in path.rglob("*.py")
                if "__pycache__" not in candidate.parts
            )
    return sorted(set(files))


def scan_stdlib_imports(paths: Sequence[Path], repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return deterministic diagnostics for non-stdlib Python imports."""
    root = repo_root.resolve() if repo_root else None
    stdlib_modules = _stdlib_modules()
    files = discover_python_files(paths)
    violations: List[ImportViolation] = []

    for file_path in files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            modules: Iterable[str]
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                modules = [node.module or ""]
            else:
                continue

            for module in modules:
                if not _is_allowed_module(module, stdlib_modules):
                    display_path = str(file_path)
                    if root:
                        try:
                            display_path = str(file_path.resolve().relative_to(root))
                        except ValueError:
                            display_path = str(file_path)
                    violations.append(ImportViolation(display_path, module, getattr(node, "lineno", 0)))

    return {
        "schema_version": SCHEMA_VERSION,
        "stdlib_only": not violations,
        "scanned_files": [str(path.resolve().relative_to(root)) if root else str(path) for path in files],
        "external_imports": [
            {"file": violation.file, "module": violation.module, "line": violation.line}
            for violation in violations
        ],
    }


def action_ref_policy(action_ref: str) -> Dict[str, Any]:
    ref = str(action_ref or "").strip()
    if ref in {"main", "master"}:
        status = "pre_stable_only"
        stable_release_allowed = False
        message = "Branch refs are acceptable before stable release only; stable examples must use a tag."
    elif re.fullmatch(r"v\d+(?:\.\d+){0,2}", ref):
        status = "stable_tag"
        stable_release_allowed = True
        message = "Version tag is acceptable for stable release examples."
    elif re.fullmatch(r"[0-9a-f]{40}", ref):
        status = "pinned_sha"
        stable_release_allowed = True
        message = "Pinned SHA is acceptable for audited examples, but release docs should prefer a maintained tag."
    else:
        status = "unclassified_ref"
        stable_release_allowed = False
        message = "Use an immutable version tag or audited SHA before stable release."

    return {
        "schema_version": SCHEMA_VERSION,
        "action_ref": ref,
        "status": status,
        "stable_release_allowed": stable_release_allowed,
        "message": message,
    }
