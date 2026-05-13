# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - DIFF-GENERATED-P0
  - PROMPT-REVIEW-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: generated assets and lockfiles should be skipped while the source wrapper remains reviewable.
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

- This fixture verifies `DIFF-GENERATED-P0` without treating generated or lockfile
  contents as reviewable model evidence by default.
