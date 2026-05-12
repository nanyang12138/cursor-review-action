from dataclasses import dataclass
from typing import Any, Dict, List

from .config import split_csv


DEFAULT_TRUSTED_AUTHOR_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")


@dataclass
class TriggerTrustDecision:
    allowed: bool
    reason: str
    trust_level: str
    should_comment: bool
    diagnostics: Dict[str, Any]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _to_bool(value: Any) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "y", "on"}


def _trusted_author_associations(settings: Dict[str, Any]) -> List[str]:
    configured = split_csv(settings.get("trusted_author_associations"))
    values = configured or list(DEFAULT_TRUSTED_AUTHOR_ASSOCIATIONS)
    return [item.upper() for item in values if item]


def _base_diagnostics(settings: Dict[str, Any]) -> Dict[str, Any]:
    trusted = _trusted_author_associations(settings)
    author_association = _clean(settings.get("comment_author_association")).upper()
    event_name = _clean(settings.get("event_name")).lower()
    return {
        "event_name": event_name or "unknown",
        "command_prompt_source": _clean(settings.get("command_prompt_source")) or "unknown",
        "comment_author_association": author_association or "unknown",
        "trusted_author_associations": trusted,
        "pr_is_fork": _to_bool(settings.get("pr_is_fork")),
        "cursor_api_key_present": bool(settings.get("cursor_api_key_present")),
    }


def _decision(
    settings: Dict[str, Any],
    *,
    allowed: bool,
    reason: str,
    trust_level: str,
    should_comment: bool,
) -> TriggerTrustDecision:
    diagnostics = _base_diagnostics(settings)
    diagnostics.update(
        {
            "allowed": allowed,
            "reason": reason,
            "trust_level": trust_level,
            "should_comment": should_comment,
        }
    )
    return TriggerTrustDecision(
        allowed=allowed,
        reason=reason,
        trust_level=trust_level,
        should_comment=should_comment,
        diagnostics=diagnostics,
    )


def evaluate_trigger_trust(settings: Dict[str, Any]) -> TriggerTrustDecision:
    """Decide whether this run may construct PR context and call Cursor."""
    event_name = _clean(settings.get("event_name")).lower()
    source = _clean(settings.get("command_prompt_source"))
    author_association = _clean(settings.get("comment_author_association")).upper()
    trusted_associations = set(_trusted_author_associations(settings))
    has_cursor_secret = bool(settings.get("cursor_api_key_present"))

    if event_name == "pull_request_target":
        return _decision(
            settings,
            allowed=False,
            reason="pull_request_target_not_supported",
            trust_level="untrusted",
            should_comment=False,
        )

    if event_name == "pull_request":
        if _to_bool(settings.get("pr_is_fork")) and not has_cursor_secret:
            return _decision(
                settings,
                allowed=False,
                reason="fork_pull_request_without_secret",
                trust_level="untrusted",
                should_comment=False,
            )
        if not has_cursor_secret:
            return _decision(
                settings,
                allowed=False,
                reason="missing_cursor_api_key",
                trust_level="unknown",
                should_comment=False,
            )
        return _decision(
            settings,
            allowed=True,
            reason="pull_request_with_secret",
            trust_level="trusted",
            should_comment=True,
        )

    if not has_cursor_secret:
        return _decision(
            settings,
            allowed=False,
            reason="missing_cursor_api_key",
            trust_level="unknown",
            should_comment=False,
        )

    if event_name == "issue_comment":
        if source not in {"slash_command", "trigger_phrase"}:
            return _decision(
                settings,
                allowed=False,
                reason="issue_comment_without_cursor_command",
                trust_level="unknown",
                should_comment=False,
            )
        if author_association not in trusted_associations:
            return _decision(
                settings,
                allowed=False,
                reason="untrusted_author_association",
                trust_level="untrusted",
                should_comment=False,
            )
        return _decision(
            settings,
            allowed=True,
            reason="trusted_issue_comment_command",
            trust_level="trusted",
            should_comment=True,
        )

    if event_name == "workflow_dispatch":
        return _decision(
            settings,
            allowed=True,
            reason="workflow_dispatch_with_secret",
            trust_level="trusted",
            should_comment=True,
        )

    return _decision(
        settings,
        allowed=True,
        reason="event_not_classified_with_secret",
        trust_level="unknown",
        should_comment=True,
    )
