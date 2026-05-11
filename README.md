# Cursor Review Action

A lightweight Cursor CLI powered pull request review bot for GitHub Actions.

Use this action when you want Cursor to review GitHub PRs, but you cannot enable Cursor Bugbot for the repository, do not have organization admin access, or want a simple workflow-based review bot that you can fully control.

It installs Cursor CLI inside GitHub Actions, reviews the PR diff, and creates or updates a PR comment.

## Why This Exists

Cursor Bugbot is the official PR review product, but it requires the GitHub App to be installed and the repository to be enabled by the right admin. That is not always possible.

PR-Agent is a mature open-source AI review system with many features, but it is a larger framework with its own provider and configuration model.

This action is intentionally smaller:

- It is Cursor-native: it uses Cursor CLI and your `CURSOR_API_KEY`.
- It does not require a GitHub App installation.
- It works with normal GitHub Actions workflows.
- It supports automatic PR review and manual `/cursor-review` comments.
- It lets reviewers add extra prompt instructions directly in a PR comment.
- It is easy to copy into personal repos, prototypes, and small team repos.

## What It Can Do

- Automatically review PRs when they are opened, updated, or reopened.
- Manually review a PR by commenting `/cursor-review`.
- Accept extra instructions after `/cursor-review`.
- Use a repo-local `.cursor-review.yml` configuration file.
- Select a Cursor model with the `model` input.
- Filter files with include/exclude patterns.
- Truncate very large diffs and explain that the review is partial.
- Update the previous Cursor review comment instead of creating comment spam.
- Output diagnostics for permissions, model, diff size, and Cursor CLI failures.

## Requirements

You need these in each repository that wants to use the action:

1. GitHub Actions enabled.
2. Permission to add a workflow file under `.github/workflows/`.
3. A GitHub Actions secret named `CURSOR_API_KEY`.
4. Workflow permissions that allow PR comments:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```

For repository settings, check:

```text
Repository -> Settings -> Actions -> General -> Workflow permissions
```

If your organization forces read-only workflow tokens, the review can still run, but the action may fail to comment on the PR.

## Step 1: Create a Cursor API Key

Create a Cursor API key from your Cursor dashboard, then store it as a GitHub Actions secret.

In your target GitHub repository:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Use this exact name:

```text
CURSOR_API_KEY
```

Do not put the real key in your workflow file, PR comment, issue, or README.

## Step 2: Add the Workflow

Create this file in the target repository:

```text
.github/workflows/cursor-review.yml
```

Copy this workflow:

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

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"

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
        uses: nanyang12138/cursor-review-action@main
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

Until the first stable release is published, use:

```yaml
uses: nanyang12138/cursor-review-action@main
```

After `v1` is released, prefer:

```yaml
uses: nanyang12138/cursor-review-action@v1
```

## Step 3: Trigger a Review

Automatic review runs when a PR is:

- opened
- updated with new commits
- reopened

Manual review runs when a trusted user comments on the PR conversation:

```text
/cursor-review
```

You can add extra instructions:

```text
/cursor-review
Focus on architecture boundaries, missing tests, and risky edge cases.
Do not summarize the whole PR.
```

The text after `/cursor-review` is passed to Cursor as additional review instructions.

## Optional: Add Repo Configuration

Create `.cursor-review.yml` in the target repository if you want repo-specific defaults.

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

## Common Customizations

Change output language:

```yaml
with:
  language: en
```

Use a specific model:

```yaml
with:
  model: auto
```

Limit reviewed files:

```yaml
with:
  include-patterns: "src/**,packages/**"
  exclude-patterns: "*.lock,dist/**,build/**"
```

Disable PR comments and only print the result in the Actions summary:

```yaml
with:
  comment-mode: off
```

Create a new comment every time instead of updating the previous one:

```yaml
with:
  persistent-comment: false
  comment-mode: create
```

## Inputs

Important inputs:

- `cursor-api-key`: Required. Cursor API key, usually `${{ secrets.CURSOR_API_KEY }}`.
- `github-token`: Token used to create or update PR comments, usually `${{ github.token }}`.
- `base-sha` / `head-sha`: PR diff range.
- `pr-number`: PR number for comment output.
- `event-name`: GitHub event name.
- `comment-body`: PR comment body used to extract extra instructions.
- `model`: Cursor model. Default: `auto`.
- `language`: Output language. Default: `zh-CN`.
- `review-focus`: Comma-separated review focus list.
- `max-findings`: Maximum actionable findings. Default: `5`.
- `max-diff-bytes`: Maximum diff size sent to Cursor. Default: `120000`.
- `filter-mode`: `added`, `diff_context`, or `file`.
- `include-patterns` / `exclude-patterns`: Comma-separated file globs.
- `persistent-comment`: Update the previous Cursor review comment. Default: `true`.
- `comment-mode`: `update`, `create`, or `off`.
- `fail-on-error`: Fail the job when Cursor review fails. Default: `false`.

## Commands

Enabled by default:

```text
/cursor-review
```

Reserved for future use:

```text
/cursor-ask
/cursor-improve
/cursor-describe
```

Only `/cursor-review` is enabled by default. The other commands are intentionally reserved until their behavior is validated.

## Security Model

- Never hardcode `CURSOR_API_KEY` in workflow files.
- Keep GitHub token permissions minimal.
- Restrict comment-triggered runs to trusted users.
- Treat PR comments and diff content as untrusted prompt input.
- The action passes comment text to Cursor as prompt text only; it does not execute comment text as shell.

The example workflow restricts manual triggers to:

```text
OWNER, MEMBER, COLLABORATOR
```

## Troubleshooting

### `Resource not accessible by integration`

The workflow token cannot create or update PR comments.

Check the workflow has:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```

Also check repository settings:

```text
Settings -> Actions -> General -> Workflow permissions
```

### Manual `/cursor-review` does not trigger

Common causes:

- The workflow file is not on the default branch.
- The comment was not posted on the PR conversation.
- The commenter is not `OWNER`, `MEMBER`, or `COLLABORATOR`.
- The workflow condition was changed and no longer matches `/cursor-review`.

### `Cursor CLI agent was not found`

Keep this input enabled:

```yaml
with:
  install-cursor: true
```

It is enabled by default.

### `401`, `Unauthorized`, or authentication failure

Check that:

- `CURSOR_API_KEY` exists in repository secrets.
- The key is valid.
- The key was not revoked.
- The key was not pasted with extra spaces.

### Review says the diff was truncated

The PR diff was larger than `max-diff-bytes`.

Options:

- Increase `max-diff-bytes`.
- Narrow scope with `include-patterns`.
- Exclude generated files with `exclude-patterns`.
- Split the PR.

## Limitations

- This is not Cursor Bugbot. It is a GitHub Actions based integration.
- Very large PRs may be partially reviewed if the diff is truncated.
- Inline comments are not enabled yet.
- `/cursor-ask`, `/cursor-improve`, and `/cursor-describe` are reserved but disabled by default.

## When to Use This

Use this action if:

- You want Cursor-powered PR review.
- You cannot enable Cursor Bugbot.
- You do not have GitHub organization admin permissions.
- You want a simple workflow-based review bot.
- You want reviewers to guide the review through `/cursor-review` comments.

If you need a mature multi-provider review framework with many built-in commands, PR-Agent may be a better fit. If you need the official Cursor PR review product and can enable it, Cursor Bugbot is the preferred option.
