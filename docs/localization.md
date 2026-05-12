# Localization Contract

`language` controls human-readable prose only. It does not change machine-readable
contracts, diagnostic keys, schema versions, XML-style response tags, file paths,
or code identifiers.

## Stable machine contracts

These fields remain English/stable for every language:

- JSON keys in `<findings_json>`, including `schema_version`, `command`,
  `severity`, `confidence`, `file`, `line`, `title`, `body`, `suggestion`, and
  `evidence`.
- Output schema versions such as `cursor-review-action/v1` and
  `cursor-review-finding/v1`.
- Rendered diagnostic labels such as `Language`, `Runner`, `Files reviewed`, and
  `CI policy reason`.
- Action outputs such as `summary`, `findings-json`, `ci-policy-json`, and
  `exit-code`.

## Human-readable content

Cursor-backed commands include a prompt instruction to write human-readable prose
in the configured language. This applies to review markdown, finding titles and
bodies, answers, improvement suggestions, summaries, risks, and test-plan prose.

Static engine diagnostics and help text stay stable so automation, tests, and
maintainer troubleshooting do not need per-language parsers.

## Input normalization

The action accepts short language tags or names such as:

```yaml
with:
  language: zh-CN
```

```yaml
with:
  language: en
```

Underscores are normalized to hyphens, so `en_US` becomes `en-US`. Empty,
multi-line, overlong, or unsafe language strings fall back to `zh-CN` and are
reported through stable localization diagnostics:

```text
- Localization schema: `localization/v1`
- Language: `zh-CN`
- Language fallback used: `true`
- Language reason: `multiline_language_defaulted`
```

## Validation checklist

- Changing `language` changes the requested prose language for Cursor-backed
  review content.
- JSON schema keys and `schema_version` values do not change with `language`.
- Diagnostics remain stable and machine-readable for every language.
