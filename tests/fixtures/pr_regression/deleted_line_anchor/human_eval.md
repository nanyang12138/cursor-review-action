# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - DIFF-INDEX-P0
  - FINDING-GROUNDING-P0
  - OUTPUT-QUALITY-GATE-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: deleted-only diff evidence should anchor to the old side without requiring a new-line anchor.
- real_issue_found: yes
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 2
- command_intent_respected: yes
- output_conciseness: 2
- diagnostics_usefulness: 2
- skipped_content_transparency: not_applicable
- follow_up_action: fixture

## Notes

- This fixture verifies deleted-line grounding remains deterministic for summary
  comments while inline deleted-line publishing stays deferred.
