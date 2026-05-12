# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - DIFF-INDEX-P0
  - FINDING-GROUNDING-P0
  - PARSER-FALLBACK-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: model output includes one selected-diff finding and one finding for a skipped file.
- real_issue_found: partial
- false_positive_count: 1
- missed_issue_count: 0
- evidence_quality: 1
- command_intent_respected: yes
- output_conciseness: 2
- diagnostics_usefulness: 2
- skipped_content_transparency: yes
- follow_up_action: fixture

## Notes

- The skipped-file finding must be downgraded through grounding diagnostics and
  must not count as a precise high-confidence review finding.
