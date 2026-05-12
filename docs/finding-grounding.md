# Finding Grounding

Capability IDs: `DIFF-INDEX-P0`, `FINDING-GROUNDING-P0`

This action validates review findings against the selected diff before treating
file and line claims as precise. The implementation is clean-room and does not
copy PR-Agent source, prompts, schemas, tests, or fixtures.

## Selected-diff index

`scripts/engine/diff_index.py` builds a `diff-index/v1` structure from the exact
diff selected for the Cursor call. The index records:

- selected file paths and aliases from `diff --git`, `---`, and `+++` headers
- hunk headers
- new-side changed line numbers for additions
- old-side changed line numbers for deletions
- skipped file paths from diff selection budgets and filters

The index covers only the selected diff. A file skipped by max files, max hunks,
scope filters, or byte budget cannot produce an anchored finding in the same run.

## Grounding statuses

`scripts/engine/grounding.py` applies grounding after structured parsing:

- `anchored`: the finding's file and changed line exist in the selected diff.
- `file_only`: the file exists in the selected diff, but the line is missing or
  is not a changed line. These findings require human verification.
- `unanchored`: the finding has no file path.
- `invalid`: the finding points to a skipped file or a file outside the selected
  diff.

Invalid and unanchored findings are downgraded in `findings-json` with low
confidence and suppression metadata. File-only findings remain visible as
machine-readable findings, but are marked with `needs_human_verification`.

## Deleted-line evidence

Deleted-line evidence may use:

```json
{
  "line": null,
  "old_line": 42,
  "line_side": "old"
}
```

When the old-side line appears as a deletion in the selected diff, the finding is
anchored with an old-side anchor object. Inline deleted-line publishing remains a
deferred reporter concern; summary comments remain the P0 publishing surface.

## Diagnostics

Rendered diagnostics include the grounding schema, whether grounding ran, the
diff-index schema, anchored/file-only/unanchored counts, invalid anchor count,
and skipped-file finding count. CI policy excludes invalid, unanchored, file-only,
and suppressed findings from future gating counts; review findings remain
advisory and non-blocking by default.
