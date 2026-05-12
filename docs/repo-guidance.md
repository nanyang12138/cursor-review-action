# Repository Guidance

Repository guidance lets maintainers add small, repo-local instructions to the
Cursor prompt without changing the action code. Guidance is optional, bounded,
and treated as untrusted repository content.

## Default files

The engine looks for these files when guidance is enabled:

| File | Commands | Purpose |
| --- | --- | --- |
| `.cursor-review-instructions.md` | all commands | General repository review instructions. |
| `best_practices.md` | `/cursor-improve` only | Improvement-focused conventions and preferred patterns. |

Missing files do not fail the review. The diagnostics list missing, skipped, or
loaded guidance files.

## Configuration

`.cursor-review.yml` can override the defaults:

```yaml
guidance_enabled: true
guidance_files:
  general: ".cursor-review-instructions.md"
  improve: "best_practices.md"
guidance_max_bytes: 20000
guidance_max_lines: 400
```

Rules:

- Paths must be repository-relative. Absolute paths and `..` traversal are
  rejected.
- `guidance_max_bytes` is a total prompt budget across loaded guidance files.
- `guidance_max_lines` limits each loaded guidance section.
- Guidance text cannot override trigger trust, output schema, security, budget,
  or publishing rules.
- Diagnostics expose file names and budget usage, but not the guidance body.

## Capability coverage

- Capability ID: `REPO-GUIDANCE-P1`
- Implementation: `scripts/engine/guidance.py`, `scripts/engine/context.py`,
  `scripts/engine/prompts.py`
- Tests: `tests/test_engine.py::RepoGuidanceTests`
