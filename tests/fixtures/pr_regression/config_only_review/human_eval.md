# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - CONFIG-SCHEMA-P1
  - PROMPT-REVIEW-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: configuration-only PR should remain reviewable, show config diagnostics, and avoid claiming application-code findings.
- real_issue_found: no
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 2
- command_intent_respected: yes
- output_conciseness: 2
- diagnostics_usefulness: 2
- skipped_content_transparency: 2
- follow_up_action: fixture

## Notes

- This fixture verifies that `CONFIG-SCHEMA-P1` diagnostics and effective review
  settings are visible for a configuration-only change without exposing the PR
  body in the rendered comment.
