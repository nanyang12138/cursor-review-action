# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - CMD-DESCRIBE-P1
  - PROMPT-COMMAND-SCHEMA-P0
  - PARSER-COMMAND-SCHEMA-P1
  - PUB-PERSISTENT-P0
  - FIXTURE-HARNESS-P0
- Command: describe
- Scenario: describe command should summarize the PR without mutating the PR body.
- real_issue_found: not_applicable
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 2
- command_intent_respected: yes
- output_conciseness: 2
- diagnostics_usefulness: 2
- skipped_content_transparency: not_applicable
- follow_up_action: none

## Notes

- Comment-only describe behavior is accepted for this fixture; PR body updates
  remain outside the current stable scope.
