# Metadata Cache

Capability IDs: `METADATA-CACHE-P1`, `CMD-DESCRIBE-P1`, `CTX-METADATA-P0`,
`SEC-PRIVACY-P0`

The metadata cache lets later `/cursor-review` and `/cursor-improve` runs reuse
the comment-only `/cursor-describe` summary for the same PR head SHA. It is a
small hidden marker in the bot's own describe comment, not an external cache and
not a PR body update.

## Stable behavior

- Missing cache is normal and never fails a command.
- Cache reuse is enabled by default but can be disabled with
  `metadata_cache_enabled: false` in `.cursor-review.yml`.
- A cache entry is reused only when all of these checks pass:
  - marker schema is `metadata-cache/v1`
  - source command is `describe`
  - cached output schema is `cursor-review-action/v1`
  - cached `head_sha` matches the current PR head SHA
  - content fits within `metadata_cache_max_bytes`
- Stale, invalid, oversized, disabled, or missing cache entries are diagnosed and
  ignored. The engine falls back to rebuilding context from current PR data.
- Only redacted structured describe fields are cached: summary, walkthrough,
  risks, tests, and changelog. Raw prompts, raw diffs, Cursor stdout, stderr, and
  secrets are not cached.

## GitHub comment flow

When a describe run publishes a comment, the action includes a hidden marker:

```text
<!-- cursor-review-action-metadata-cache:{...} -->
```

Before a later run, the composite action reads the latest bot describe comment
and passes only that hidden marker into the Python engine. The engine validates
the marker locally before adding the cached describe metadata to prompt context.

The marker is intentionally scoped to persistent comments. It does not require a
GitHub App, Actions cache, artifacts, or a release tag.

## Diagnostics

Rendered comments include compact diagnostics without exposing cached content:

- `Metadata cache schema`
- `Metadata cache enabled`
- `Metadata cache status`
- `Metadata cache reason`
- `Metadata cache source`
- `Metadata cache head match`
- `Metadata cache bytes`

Common statuses:

| Status | Meaning |
| --- | --- |
| `valid` | Cache was generated or reused after validation. |
| `missing` | No hidden cache marker was available. |
| `stale` | Cached head SHA did not match the current PR head SHA. |
| `invalid` | Marker JSON, schema, source command, or output schema was not acceptable. |
| `disabled` | Repository config disabled metadata cache reuse. |
| `not_applicable` | The current command does not consume metadata cache. |
| `suppressed` | Describe output was blocked by the output quality gate. |
| `too_large` | Generated cache marker exceeded the configured budget. |

## Compatibility and deferrals

- `/cursor-describe` remains comment-only. The action does not update the PR body.
- Review/improve cache reuse is opportunistic; it never narrows the selected diff
  or replaces current PR metadata.
- External artifact/cache-backed metadata remains a P2 private-repo opt-in.
- Since-last-run incremental review remains deferred; cache reuse is not used as a
  stale-run or incremental-scope source of truth.
