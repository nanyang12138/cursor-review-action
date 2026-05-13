# Human Evaluation

Capability IDs: PARSER-FALLBACK-P0, PARSER-RETRY-P1, OUTPUT-QUALITY-GATE-P0, FIXTURE-HARNESS-P0, CURSOR-RUNNER-P0, ACCEPTANCE-RUBRIC-P1

- real_issue_found: not_applicable; fixture validates empty Cursor stdout handling rather than a product bug.
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: medium; no actionable finding is emitted when the model output is empty.
- command_intent_respected: yes; `/cursor-review` reports a diagnostic fallback instead of inventing findings.
- output_conciseness: good; the user-facing markdown is a short failure explanation plus diagnostics.
- diagnostics_usefulness: good; parser reason, runner failure kind, retry exhaustion, and quality gate decision identify the failure path.
- skipped_content_transparency: not applicable; no selected files were skipped.
- follow_up_action: keep as regression evidence for empty Cursor stdout and max-call retry exhaustion behavior.
