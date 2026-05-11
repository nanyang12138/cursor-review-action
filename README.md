# Cursor Review Action

Reusable GitHub Action for Cursor-powered pull request review.

This action is a lightweight alternative when Cursor Bugbot cannot be enabled for a repository. It runs Cursor CLI in GitHub Actions, reviews the PR diff, and creates or updates a PR comment.

## Features

- PR automatic review on `opened`, `synchronize`, and `reopened`.
- Manual review by commenting `/cursor-review` on a PR.
- Extra instructions after `/cursor-review` are passed into the review prompt.
- Repo-local `.cursor-review.yml` configuration.
- Model selection through the `model` input.
- Diff filtering with include/exclude patterns.
- Large diff truncation with diagnostics.
- Persistent PR comment updates to avoid comment spam.
- Structured findings output for future inline comment support.
- Safe default behavior: only `review` is enabled by default.

## Quick Start

1. Add a repository secret named `CURSOR_API_KEY`.
2. Copy [`examples/cursor-review.yml`](examples/cursor-review.yml) to:

```text
.github/workflows/cursor-review.yml
```

3. Commit the workflow to the default branch.
4. Open or update a PR, or comment:

```text
/cursor-review
```

With extra prompt:

```text
/cursor-review
Focus only on architecture boundaries and missing tests.
```

## Minimal Caller Workflow

```yaml
name: Cursor Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  cursor-review:
    if: >
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       github.event.issue.pull_request &&
       contains(github.event.comment.body, '/cursor-review') &&
       contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association))
    runs-on: ubuntu-latest

    steps:
      - name: Resolve PR information
        id: pr
        uses: actions/github-script@v7
        with:
          script: |
            if (context.eventName === 'pull_request') {
              core.setOutput('number', context.payload.pull_request.number);
              core.setOutput('base_sha', context.payload.pull_request.base.sha);
              core.setOutput('head_sha', context.payload.pull_request.head.sha);
              return;
            }

            const pr = await github.rest.pulls.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: context.issue.number
            });

            core.setOutput('number', pr.data.number);
            core.setOutput('base_sha', pr.data.base.sha);
            core.setOutput('head_sha', pr.data.head.sha);

      - name: Checkout PR
        uses: actions/checkout@v4
        with:
          ref: ${{ steps.pr.outputs.head_sha }}
          fetch-depth: 0

      - name: Cursor review
        uses: nanyang12138/cursor-review-action@v1
        with:
          cursor-api-key: ${{ secrets.CURSOR_API_KEY }}
          github-token: ${{ github.token }}
          base-sha: ${{ steps.pr.outputs.base_sha }}
          head-sha: ${{ steps.pr.outputs.head_sha }}
          pr-number: ${{ steps.pr.outputs.number }}
          event-name: ${{ github.event_name }}
          comment-body: ${{ github.event_name == 'issue_comment' && github.event.comment.body || '' }}
          model: auto
          language: zh-CN
```

## Repo Configuration

Create `.cursor-review.yml` in the target repository:

```yaml
model: auto
language: zh-CN
review_focus:
  - correctness
  - security
  - performance
  - tests
  - edge-cases
max_findings: 5
max_diff_bytes: 120000
filter_mode: added
persistent_comment: true
enabled_commands:
  - review
include_patterns: []
exclude_patterns:
  - "*.lock"
  - "dist/**"
  - "build/**"
```

Configuration precedence:

```text
PR comment prompt > .cursor-review.yml > workflow inputs > action defaults
```

## Inputs

Important inputs:

- `cursor-api-key`: required Cursor API key.
- `github-token`: GitHub token used for PR comment update.
- `base-sha` / `head-sha`: PR diff range.
- `pr-number`: PR number for comment output.
- `comment-body`: PR comment body, used to extract extra instructions.
- `model`: Cursor model, default `auto`.
- `language`: output language, default `zh-CN`.
- `max-findings`: maximum actionable findings, default `5`.
- `max-diff-bytes`: maximum diff size sent to Cursor, default `120000`.
- `filter-mode`: `added`, `diff_context`, or `file`.
- `include-patterns` / `exclude-patterns`: comma-separated file globs.
- `persistent-comment`: update previous review comment, default `true`.
- `comment-mode`: `update`, `create`, or `off`.
- `fail-on-error`: fail the job when Cursor review fails, default `false`.

## Commands

Default enabled command:

```text
/cursor-review
```

Reserved commands:

```text
/cursor-ask
/cursor-improve
/cursor-describe
```

These are intentionally disabled by default. Enable them later through `enabled_commands` once their behavior is validated.

## Model Selection

Use `auto` unless you know your Cursor account supports a specific model.

```yaml
with:
  model: auto
```

To inspect available models in a separate debug workflow, run:

```bash
agent models
```

## Security Notes

- Do not hardcode `CURSOR_API_KEY` in workflow files.
- Keep `permissions` minimal: `contents: read`, `pull-requests: write`, `issues: write`.
- Restrict comment-triggered runs to trusted users such as `OWNER`, `MEMBER`, or `COLLABORATOR`.
- PR comment text and diff content are treated as untrusted prompt input and are never executed as shell.

## Troubleshooting

`Resource not accessible by integration`

- Ensure workflow permissions include `issues: write` and `pull-requests: write`.
- Check repository settings: Actions workflow permissions may need read/write access.

`Cursor CLI agent was not found`

- Keep `install-cursor: true`, or install Cursor CLI before calling the action.

`401` or auth failure

- Confirm `CURSOR_API_KEY` is valid and stored as a GitHub Actions secret.

Review comment says diff was truncated

- Increase `max-diff-bytes`, or narrow review scope with `include-patterns`.

Manual `/cursor-review` does not trigger

- The workflow must exist on the default branch for `issue_comment` events.
- The comment must be on the PR conversation, not only a file review thread.
