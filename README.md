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
- It supports automatic PR review and manual `/cursor-review`, `/cursor-ask`, `/cursor-improve`, and `/cursor-describe` comments.
- It lets reviewers add extra prompt instructions directly in a PR comment.
- It is easy to copy into personal repos, prototypes, and small team repos.
- It checks trigger trust before contacting Cursor, so untrusted slash commands and fork PRs without secrets are skipped safely.

## What It Can Do

- Automatically review PRs when they are opened, updated, or reopened.
- Manually review, ask about, improve, or describe a PR with slash commands.
- Accept extra instructions after a supported slash command.
- Accept allowlisted slash command arguments such as `--focus` and `--max-findings`.
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

## Step 2: Add the Required Workflow File

Create this file in the target repository:

```text
.github/workflows/cursor-review.yml
```

This is the GitHub Actions workflow file. It tells GitHub when to run Cursor Review Action, which permissions it needs, and how PR slash command comment events should trigger it.

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
       (
         contains(github.event.comment.body, '/cursor-review') ||
         contains(github.event.comment.body, '/cursor-ask') ||
         contains(github.event.comment.body, '/cursor-improve') ||
         contains(github.event.comment.body, '/cursor-describe')
       ) &&
       contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association))
    runs-on: ubuntu-latest

    steps:
      - name: Resolve PR information
        id: pr
        uses: actions/github-script@v7
        with:
          script: |
            async function setPullRequestOutputs(pr) {
              core.setOutput('number', pr.number);
              core.setOutput('base_sha', pr.base.sha);
              core.setOutput('head_sha', pr.head.sha);
              core.setOutput('title', pr.title || '');
              core.setOutput('body', pr.body || '');
              core.setOutput('base_ref', pr.base.ref || '');
              core.setOutput('head_ref', pr.head.ref || '');
              core.setOutput('is_fork', String(Boolean(pr.head.repo && pr.head.repo.fork)));
              const commits = await github.paginate(github.rest.pulls.listCommits, {
                owner: context.repo.owner,
                repo: context.repo.repo,
                pull_number: pr.number,
                per_page: 100
              });
              core.setOutput('commit_messages', commits.map((item) => item.commit.message.split('\n')[0]).join('\n'));
            }

            if (context.eventName === 'pull_request') {
              await setPullRequestOutputs(context.payload.pull_request);
              return;
            }

            const pr = await github.rest.pulls.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: context.issue.number
            });

            await setPullRequestOutputs(pr.data);

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
          pr-title: ${{ steps.pr.outputs.title }}
          pr-body: ${{ steps.pr.outputs.body }}
          base-ref: ${{ steps.pr.outputs.base_ref }}
          head-ref: ${{ steps.pr.outputs.head_ref }}
          pr-is-fork: ${{ steps.pr.outputs.is_fork }}
          commit-messages: ${{ steps.pr.outputs.commit_messages }}
          event-name: ${{ github.event_name }}
          comment-body: ${{ github.event_name == 'issue_comment' && github.event.comment.body || '' }}
          comment-author-association: ${{ github.event_name == 'issue_comment' && github.event.comment.author_association || '' }}
          enabled-commands: review,ask,improve,describe
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

Manual commands run when a trusted user comments on the PR conversation:

```text
/cursor-review
/cursor-ask
/cursor-improve
/cursor-describe
```

You can add extra instructions:

```text
/cursor-review
Focus on architecture boundaries, missing tests, and risky edge cases.
Do not summarize the whole PR.
```

The text after the slash command is passed to Cursor as additional instructions.

## Optional: Add a Repo Configuration File

Create `.cursor-review.yml` in the target repository if you want repo-specific defaults.

This file is different from `.github/workflows/cursor-review.yml`.

- `.github/workflows/cursor-review.yml` is required. It starts the action.
- `.cursor-review.yml` is optional. It customizes how the action reviews PRs in this repository.

You can skip `.cursor-review.yml` if the default settings are enough.

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
  - ask
  - improve
  - describe
include_patterns: []
exclude_patterns:
  - "*.lock"
  - "dist/**"
  - "build/**"
```

Configuration precedence:

```text
slash command arguments > PR comment prompt > .cursor-review.yml > workflow inputs > action defaults
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

By default, persistent comments are tracked separately per command. For example, `/cursor-review` updates the latest Cursor Review comment, while `/cursor-ask` updates the latest Cursor Ask comment instead of overwriting the review result.

## Inputs

Important inputs:

- `cursor-api-key`: Required. Cursor API key, usually `${{ secrets.CURSOR_API_KEY }}`.
- `github-token`: Token used to create or update PR comments, usually `${{ github.token }}`.
- `base-sha` / `head-sha`: PR diff range.
- `pr-number`: PR number for comment output.
- `pr-title` / `pr-body`: PR title and description passed as review context.
- `base-ref` / `head-ref`: Base and source branch names passed as review context.
- `pr-is-fork`: Whether the PR head repo is a fork. Used for pre-Cursor trigger trust diagnostics.
- `commit-messages`: Newline-separated commit messages passed as review context.
- `event-name`: GitHub event name.
- `comment-body`: PR comment body used to extract extra instructions.
- `comment-author-association`: GitHub author association for `issue_comment` slash command trust checks.
- `trusted-author-associations`: Comma-separated trusted associations. Default: `OWNER,MEMBER,COLLABORATOR`.
- `model`: Cursor model. Default: `auto`.
- `language`: Output language. Default: `zh-CN`.
- `review-focus`: Comma-separated review focus list.
- `max-findings`: Maximum actionable findings. Default: `5`.
- `max-diff-bytes`: Maximum diff size sent to Cursor. Default: `120000`.
- `filter-mode`: `added`, `diff_context`, or `file`.
- `include-patterns` / `exclude-patterns`: Comma-separated file globs.
- `persistent-comment`: Update the previous comment for the same command. Default: `true`.
- `comment-mode`: `update`, `create`, or `off`.
- `fail-on-error`: Fail the job when Cursor review fails. Default: `false`.

## Commands

Supported slash commands:

```text
/cursor-review
/cursor-ask
/cursor-improve
/cursor-describe
```

The recommended workflow and `.cursor-review.yml` enable all four commands. If you pass `enabled-commands` manually, include every command you want to allow.

`/cursor-review` supports a small allowlist of per-run arguments:

```text
/cursor-review --focus=security,tests --max-findings=3
Check authentication edge cases first.
```

Supported arguments:

- `--focus` or `--review-focus`: comma-separated review focus values.
- `--max-findings`: integer from 1 to 50.

Unknown arguments are not used as configuration overrides. They remain ordinary prompt text and are never passed to a shell.

## Security Model

- Never hardcode `CURSOR_API_KEY` in workflow files.
- Keep GitHub token permissions minimal.
- Restrict comment-triggered runs to trusted users.
- Treat PR comments and diff content as untrusted prompt input.
- The action parses only allowlisted slash command arguments and passes remaining comment text to Cursor as prompt text only; it does not execute comment text as shell.
- The action also enforces the same trusted author association policy before context construction and Cursor CLI execution.

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

### Manual slash command does not trigger

Common causes:

- The workflow file is not on the default branch.
- The comment was not posted on the PR conversation.
- The commenter is not `OWNER`, `MEMBER`, or `COLLABORATOR`.
- The workflow condition was changed and no longer matches the slash command.

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

## When to Use This

Use this action if:

- You want Cursor-powered PR review.
- You cannot enable Cursor Bugbot.
- You do not have GitHub organization admin permissions.
- You want a simple workflow-based review bot.
- You want reviewers to guide the review through PR slash commands.

If you need a mature multi-provider review framework with many built-in commands, PR-Agent may be a better fit. If you need the official Cursor PR review product and can enable it, Cursor Bugbot is the preferred option.
