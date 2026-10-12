# Design principles

*English translation of the standing rules for adding, removing, and
reorganising template options (previously only in `TODO.md` "設計原則").
Proposals that contradict these principles are re-thought before they are
scheduled — they are how the questionnaire stays maintainable.*

## `project_type` is for execution environments, not flavours

A new `project_type` is justified only when **the build/run environment is
fundamentally different** or when there is a clear **rule-of-use axis** the
other types cannot express:

- `library` (importable package), `web_api` (HTTP + Docker), `cli`
  (short-lived process), `data_science`, `script`,
  `online_judge` (competition rules), `ros2` (colcon/rosdep),
  `micropython` (device + firmware build).

**The AI-rules axis counts.** `online_judge` is executionally a script/cli
project, but whether AI coding agents are permitted differs per contest,
which changes what the generated `AGENTS.md` says. That is a first-class
difference independent of the runtime.

Conversely, if neither the environment nor a rules axis differs, the idea
is a **layer on an existing project_type**, not a new one. CTF, bots
(discord/slack/LINE), data-science extensions, SRE tooling all live as
layers (`include_*` questions). Any request for a new project type must
first answer: *"which existing layer does this sit on?"*

## `AGENTS.md` ships in every project

Since 2026-09-21 every project type generates `AGENTS.md`
(`agents_md_effective` is a constant `true`). For `online_judge`,
`oj_allow_ai` selects the *wording* ("AI permitted, contest rules take
precedence" vs. "submissions must be hand-written") rather than the file's
presence, and every variant carries "check the current contest rules
before submitting". There is no per-project on/off question — the agent
guide is part of the built-in baseline.

This coupling is deliberate but reviewed (TODO §43-2): the file mixes agent
commands/editing rules with the ethics appendix. Verified 2026-10-11 on real
renders — a library carries license-drift + pqc-fips, an `online_judge`
workspace carries the contest-integrity rules, micropython carries the PKI
trust-chain section — the appendix has no other distribution channel, so
always-on is kept until an alternative carrier exists or user reports show
the guide is noise in agent-free repos. Splitting agent instructions from
human/legal content (option b) and re-gating the file (option c) both stay
open pending that evidence.

## Out-of-scope is rejected explicitly, not ignored

Areas this template deliberately does not cover (IaC, Terraform/K8s,
Django-shaped stacks, ...) are **not** advertised as `project_type`
choices — the questionnaire lists only supported types, and an invalid
value (a bad preset key, an unsupported `--data` answer) is rejected
before anything is written, pointing at an alternative. This fail-closed
behavior replaced the earlier `web_django` trap choice: out-of-scope
stacks are rejected, never silently ignored or baited. Reinstating an
out-of-scope name as a first-question candidate is considered only if a
real user need exists and the rejected choice cannot be mistaken for a
supported one (TODO §43).

## One recommended path + "No" for custom

Each area gate follows `use_recommended_*`: one recommended bundle, or
"No" which opens the detailed questions. The template does not grow into a
catalogue (five ORMs, GraphQL-vs-REST pickers) — depth is delegated to the
generated project, not to the questionnaire.

## The questionnaire is a verified artifact

Every `when:`/`default:`/`choices:` expression must resolve against names
declared earlier, every `when:` must be satisfiable, and the leaf space is
swept by Z3 witnesses (`tests/matrix/witnesses.json`, 272 leaves). A change
that adds a question or a gate changes the leaf space and therefore must
run `task regen` — witness regeneration, tier ledger, docs — as its
definition of done.

## Scope follows maintenance capacity

Support is a promise, not just a successful render. Before adding a project
type, layer, package-manager path, or other supported variant, a proposal must
name its users, the maintainer responsible for it, and the support tier it can
meet. If nobody can own its updates and failures, keep it experimental or
decline it; do not imply the same support as a staffed path.

Prefer improving the reliability and usability of existing paths over adding
another option. Remove or narrow a path when its maintenance cost exceeds its
demonstrated value. A larger questionnaire or witness count is not, by itself,
evidence of a better template.

## Claims match verification evidence

The support matrix is the source of truth for what is actually exercised.
Rendering and linting prove that files can be generated and checked; they do
not prove that every generated project can be installed, tested, or updated.
Describe those paths as best-effort unless the corresponding execution tier
proves more. Do not claim full coverage from representative witnesses: state
the sampled paths and the gaps.

Release confidence also depends on the published revision, not only the
working tree. Validate the revision users will resolve, and keep release
claims, CI status, support tiers, and update-rehearsal results consistent.

## Change classification (blast radius)

Contributors classify their change before choosing a verification path:

| Class | Examples | Verification |
|---|---|---|
| docs-only | `README.md`, `docs/*.md` | `task lint type-check` (CI skips the render matrix) |
| render-only | template files, `_shared/` | twin render + fast tier |
| questionnaire | `copier.yml`, `questions/` | `task regen` — full regeneration |

See the [test-loop guide](../how-to/test-loop.md) for verification commands.
