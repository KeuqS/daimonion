# Propose a configuration from requirements

`daimonion suggest` turns "what the project needs" into a preset candidate,
then checks the full answer set before anything is generated. The model (or
you) proposes; the questionnaire's own machinery disposes:

```shell
daimonion suggest "internal API, postgres, github actions"  # preset candidates with reasons
daimonion suggest --validate answers.yml                    # check a drafted answer set (exit 2 when rejected)
```

The flow the command enforces:

1. **Propose from requirements.** `suggest` ranks the `presets/*.yml`
   families by keyword match — no model, no render, no network. Each match
   names its score, its human reasons, and the answers it pins.
2. **Draft the full answer set.** Write every answer the render needs (the
   preset's pins plus the rest of the questionnaire — see
   [Questionnaire](../reference/questionnaire.md) for the full list).
3. **Validate before generating.** `--validate` runs the draft through
   copier's own questionnaire pass and rejects unknown questions, values
   outside the choices, answers to questions that would never be asked, and
   layer includes on a base that cannot carry them, with machine-readable
   `{question, reason}` pairs. Only an approved set reaches `daimonion new
   --preset` (or `--data-file`).

What is refused, and why:

- **Unknown questions** — copier would silently render the default instead,
  so a typo (`unknown_q`) fails rather than generating the wrong project.
- **Values outside the choices** — copier's own choice verdict, including
  the templated `oj_kind` choices and the `domain_traits` multiselect.
- **Answers to unasked questions** — a forced value copier keeps but the
  render discards (e.g. `include_scraping: true` on a `web_api` base).
- **Layers on non-combinable bases** — `include_web_api: true` on `ros2`
  trips the `combinable` / `has_*` guard in `questions/_combo.yml`.
- **Derived internals** — `combinable`, `has_web_api` and friends are
  computed at render time and must not be answered.

A combination no `support.yml` row promises is a warning, not a rejection:
it renders, but no tier is promised (see
[Support](../reference/support.md)).

The same gate is available to agents over MCP as `suggest_config`
(requirement words in, candidates out) and `validate_answers` (candidate
answers in, `{"ok", "errors"}` out; see [Use the template's own MCP
server](mcp-tools.md)). The logic lives in `tools/suggest.py`; the CLI
subcommand and the MCP tools are thin shells over it. The questionnaire
itself is untouched — the no-model CLI/questionnaire path keeps working
exactly as before.

## Related

- [Presets](../reference/presets.md) — the ready-made answer files `suggest` ranks.
- [Questionnaire](../reference/questionnaire.md) — the full question list with gates.
- [Support](../reference/support.md) — the declared tiers the validation quotes.
- [Explain a Preset or an Answer](explain.md) — why one choice, and what changes otherwise.
