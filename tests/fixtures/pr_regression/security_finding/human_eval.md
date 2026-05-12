# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
  - CMD-REVIEW-P0
  - PROMPT-REVIEW-P0
  - PARSER-FALLBACK-P0
  - FINDING-TAXONOMY-P0
  - PUB-PERSISTENT-P0
  - FIXTURE-HARNESS-P0
- Command: review
- Scenario: security-sensitive PR should surface a concrete high-risk finding.
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

- Grounding and output quality gate work should strengthen evidence quality
  before stable release readiness.
