# Explain a preset or an answer before choosing it

`daimonion explain` answers "why this value" and "what changes if I pick
something else" from the questionnaire's own words — no need to read the
whole feature catalogue first:

```shell
daimonion explain --preset web-api          # why the preset pins what it pins
daimonion explain project_type cli          # the question's help, values, and support rows
daimonion explain --deviate project_type cli  # which questions appear/disappear, which tier promises it
```

The explanation has a single source: the `help` text in `questions/*.yml`,
each question's `choices` / `when` context, the preset file's own leading
comment, and the measured `why` lines in `support.yml`. The "what changes"
half is derived, not written — it lists every definition whose `when` or
`default` reads the answer (the same edges `task question-graph` reports),
split into questions that get asked or skipped and internals that change
the render.

A combination no `support.yml` row names says so explicitly ("it renders,
but no tier is promised") rather than inventing a tier. Unknown preset or
question names fail with exit 2 and list the valid names.

The same explanations are available to agents over MCP as `explain_choice`
(`preset=`, `question=` + `value=`, or `deviate_question=` +
`deviate_value=`; see [Use the template's own MCP server](mcp-tools.md)).
The logic lives in `tools/explain.py`; the CLI subcommand and the MCP tool
are thin shells over it.

## Related

- [Questionnaire](../reference/questionnaire.md) — the full question list with gates.
- [Support](../reference/support.md) — the declared tiers the explanations quote.
- [Propose a Configuration from Requirements](suggest.md) — from requirement words to a validated answer set.
