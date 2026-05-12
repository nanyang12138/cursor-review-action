from dataclasses import dataclass
from typing import Any, Dict

from .diff_selector import build_diff


@dataclass
class ReviewContext:
    diff_text: str
    stat: str
    truncated: bool
    meta: Dict[str, Any]


def build_review_context(settings: Dict[str, Any]) -> ReviewContext:
    diff_text, stat, truncated, meta = build_diff(settings)
    return ReviewContext(diff_text=diff_text, stat=stat, truncated=truncated, meta=meta)
