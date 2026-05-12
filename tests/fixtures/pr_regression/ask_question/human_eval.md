# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - CMD-ASK-P1
  - PROMPT-COMMAND-SCHEMA-P0
  - PARSER-COMMAND-SCHEMA-P1
  - FIXTURE-HARNESS-P0
- Command: ask
- Scenario: ask command should answer the user's question without broad review noise.
- real_issue_found: not_applicable
- false_positive_count: 0
- missed_issue_count: 0
- evidence_quality: 2
- command_intent_respected: yes
- output_conciseness: 3
- diagnostics_usefulness: 2
- skipped_content_transparency: not_applicable
- follow_up_action: none

## Notes

- The acceptance target is command intent: answer the question, do not emit
  unrelated review findings.
