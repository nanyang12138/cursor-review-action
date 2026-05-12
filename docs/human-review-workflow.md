# Human Review Workflow

Cursor Review Action is an advisory reviewer. It can summarize risk, point to
possible issues, and suggest follow-up, but humans remain responsible for review
decisions.

## Default policy

- AI findings are non-blocking by default.
- The action does not approve pull requests.
- The action does not merge pull requests.
- The action does not fail CI because of findings by default.
- Maintainers decide whether to accept, dismiss, or follow up on findings.

This policy applies to automatic `pull_request` reviews and trusted slash
commands such as `/cursor-review`, `/cursor-ask`, `/cursor-improve`, and
`/cursor-describe`.

## Author checklist

Authors can use this checklist when a Cursor review comment appears:

- Read each actionable finding and inspect the linked code or evidence.
- Fix confirmed bugs, security risks, or missing tests.
- Dismiss false positives in the PR conversation when useful for reviewers.
- Create follow-up issues for valid work that should not block the current PR.
- Ask for human reviewer confirmation before treating an AI finding as resolved.

## Maintainer override

Maintainers can override the AI review by applying normal repository policy:

- Merge when human reviewers are satisfied, even if the AI comment contains
  non-blocking findings.
- Request changes when a human reviewer agrees with a high-risk finding.
- Ignore or document false positives without changing action configuration.
- Disable PR comments with `comment-mode: off` if the repository only wants
  Actions summary output.

## CI and blocking behavior

The default workflow status reports whether the action executed successfully, not
whether the model liked the pull request. Finding-based merge blocking is a
separate, experimental policy decision and should only be enabled after fixture
coverage and dogfooding evidence justify it.

See `docs/ci-policy.md` when that policy is implemented.

## Diagnostics evidence

Rendered review comments include:

- `Review policy: advisory_non_blocking`
- `Human decision required: true`

These diagnostics make the human workflow explicit without granting the bot
approval, merge, or release authority.
