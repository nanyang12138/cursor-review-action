# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - PROMPT-REVIEW-P0
  - FINDING-TAXONOMY-P0
  - FINDING-GROUNDING-P0
  - OUTPUT-QUALITY-GATE-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: missing test coverage for a new billing discount branch should remain an actionable review finding.
- real_issue_found: yes
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 3
- command_intent_respected: yes
- output_conciseness: 3
- diagnostics_usefulness: 3
- skipped_content_transparency: not_applicable
- follow_up_action: fixture

## Notes

- Acceptance focuses on keeping test-gap findings actionable when a selected
  diff adds a behavior branch without nearby regression coverage.
