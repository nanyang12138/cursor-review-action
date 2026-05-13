# Human Evaluation

Capability IDs: PARSER-FALLBACK-P0, PARSER-RETRY-P1, OUTPUT-QUALITY-GATE-P0, FIXTURE-HARNESS-P0, ACCEPTANCE-RUBRIC-P1

- real_issue_found: not_applicable; fixture validates malformed model output handling rather than a product bug.
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: medium; the markdown is preserved while malformed structured findings are not treated as actionable.
- command_intent_respected: yes; `/cursor-review` falls back to a diagnostic review result instead of publishing untrusted JSON.
- output_conciseness: good; no malformed structured finding is rendered as an actionable issue.
- diagnostics_usefulness: good; parser reason, fallback mode, and quality gate decision identify the failure path.
- skipped_content_transparency: not applicable; no selected files were skipped.
- follow_up_action: keep as regression evidence for invalid JSON model output and max-call retry exhaustion behavior.
