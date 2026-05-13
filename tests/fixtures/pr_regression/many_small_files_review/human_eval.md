# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - DIFF-LARGE-P0
  - BUDGET-CONTROLS-P1
  - PROMPT-REVIEW-P0
  - FINDING-GROUNDING-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: many-small-files PR should prioritize security/test/config context, show skipped-file coverage, and keep selected finding anchors grounded.
- real_issue_found: yes
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 3
- command_intent_respected: yes
- output_conciseness: 2
- diagnostics_usefulness: 3
- skipped_content_transparency: 3
- follow_up_action: fixture

## Notes

- The fixture covers the `many-small-files` inventory gap without contacting
  Cursor and verifies that max-file budget diagnostics remain visible when only
  part of a many-file PR is selected for review.
