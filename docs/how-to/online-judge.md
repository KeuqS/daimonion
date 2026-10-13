# Online-judge workspaces

The template can generate a **competitive-programming workspace** for the
code-submission judges: AtCoder, LeetCode, yukicoder, AOJ, Codeforces, Kattis
and any other stdin/stdout judge. Answering **online_judge** to
`project_type` and **Competitive coding** to `oj_category` produces a *bare*
repository — no package, no `src/` layout, no library — that you drive with
the judge's own command-line tools. The generated task runner (all runners
except poe) adds four recipes (`new` / `dl` / `sample` / `submit`) that wrap
those tools, and an `AGENTS.md` whose AI wording defers to the contest rules.

## Choosing `oj_kind`

The `oj_kind` question picks the judge. Each judge has its own tooling
story, so the recipes and the README lead with the right CLI:

| `oj_kind` | Workspace driven with | Terminal workflow |
|-----------|----------------------|-------------------|
| `atcoder` | [atcoder-cli](https://github.com/Tatamo/atcoder-cli) (`acc`) + [online-judge-tools](https://github.com/online-judge-tools/oj) (`oj`) | contest folders from `acc new`, samples / tests / submit from `oj` |
| `leetcode` | none — LeetCode's editor is the judge | a `main.py` per problem as your working copy; paste it into the editor to run and submit |
| `yukicoder` | `oj` | download, test and submit all work from the terminal |
| `aoj` | [aoj-cli](https://github.com/YuminosukeSato/AOJ-cli) (`aoj`) | `aoj init` / `aoj test` / `aoj submit`; `oj` can download samples but not submit |
| `codeforces` | `oj` | download and test work; `oj submit` where the service allows, else the browser |
| `kattis` | `oj` + the [Kattis client](https://github.com/Kattis/kattis-cli) (`submit.py`) | samples via `oj`; submit with `submit.py` and a personal `~/.kattisrc` |
| `other` | `oj` | download and test where the service allows; submit through the judge's website |

## What gets generated

- **A bare workspace**: `main.py` lives in *your* per-problem folders — the
  template creates none, because the judge tooling (or the `new` recipe)
  creates them. There is no installable package and no `src/` tree, so
  `deptry` / `vulture` and the coverage flags are skipped, and the generated
  `pytest` task runs a single workspace smoke test.
- **The judge CLIs are not project dependencies** — they are user-installed
  tools. Every recipe that reaches for one first fails with an install hint
  (`pip install online-judge-tools`, `npm install -g atcoder-cli`,
  `go install github.com/YuminosukeSato/AOJ-cli/cmd/aojcli@latest`) instead
  of a bare "command not found".
- **`test/` sample directories and `~/.kattisrc` are git-ignored** — the
  downloaded sample cases and the Kattis submission token stay out of git.
- **Four task-runner recipes** in every task runner except poe
  (just / task / make / invoke / duty; poe has no OJ recipe support yet),
  named `new`, `dl`, `sample`, `submit`.
- An `AGENTS.md` agent guide (always generated since 2026-09-21) whose AI
  wording follows `oj_allow_ai` (see below).

## The daily loop

One task per step, in every supported task runner:

| Step | Recipe | What it does |
|------|--------|--------------|
| 1 | `new <path>` | Scaffold a problem dir: `<path>/main.py` + `<path>/test/` (AtCoder: `acc new <contest>`) |
| 2 | `dl <url>` | Download the samples into `<path>/test/` (`aoj init <problem>` on AOJ; a manual note on LeetCode) |
| 3 | — | Edit `main.py` |
| 4 | `sample <dir>` | Run the judge's sample tests (`oj test -c "python3 main.py"`, `aoj test main.py`) |
| 5 | `submit <dir>` | Submit `main.py` (`oj submit`, `aoj submit`, `python3 submit.py` on Kattis; a browser note on LeetCode / other) |

Per judge, the recipe table (the same commands in the supported runners):

| Judge | `new` | `dl` | `sample` | `submit` |
|-------|-------|------|----------|----------|
| AtCoder | `acc new <contest>` | `oj download <url>` | `oj test` | `oj submit` |
| yukicoder | `mkdir` + starter | `oj download <url>` | `oj test` | `oj submit` |
| Codeforces | `mkdir` + starter | `oj download <url>` | `oj test` | `oj submit` (or the browser) |
| AOJ | `mkdir` + starter | `aoj init <problem>` | `aoj test` | `aoj submit` |
| Kattis | `mkdir` + starter | `oj download <url>` | `oj test` | `python3 submit.py` |
| LeetCode | `mkdir` + starter | copy samples by hand | the LeetCode editor | the LeetCode editor |
| other | `mkdir` + starter | `oj download <url>` | `oj test` | the judge's website |

The `mkdir`-based `new` writes a tiny stdin-reading starter (`import sys;
print(sys.stdin.read())`) so `sample` has something to run; `oj test` guesses
the problem URL from the earlier `oj download` in the same directory, and
`oj submit main.py` does the same for submit. Login once per judge with
`oj login <judge-url>` (or `aoj login`), and set up `~/.kattisrc` for the
Kattis client.

Why `sample` and not `test`? The canonical task model already ships a `test`
task — the pytest suite that the generated CI invokes on every push — and
`just` refuses a recipe redefinition. "Sample" also says what it runs: the
judge's sample cases, not the unit tests.

## The `oj_sample` CI workflow

`oj_sample` (asked for the code-submission judges, default **No**) adds
`.github/workflows/oj-sample.yml`: an opt-in workflow that runs the judge
CLI's *own* sample test against one pinned problem per site. It is
dispatch-only (manual + weekly Sunday schedule — the judges' pages and CLIs
move without notice), and installs only that site's tool:

- `oj`-based judges (AtCoder / yukicoder / Codeforces / other): `uv pip
  install online-judge-tools`, then `oj download` + `oj test` on the pinned
  problem;
- AOJ: `go install .../AOJ-cli/cmd/aojcli@latest`, then `aoj init` + `aoj
  test`;
- Kattis and LeetCode: a local run only (no network submission) — the
  Kattis client is not exercised because it needs credentials.

It stays out of `check` and the push CI on purpose: it needs network and
the judge's tool. The `workflow_dispatch` input `problem` lets you point the
check at any problem URL or id.

## The `oj_allow_ai` wording difference

AI coding agents are governed by each contest's rules, which vary per judge
and per contest. The workspace always ships an `AGENTS.md`; `oj_allow_ai`
(asked for AtCoder / LeetCode / Codeforces / Kattis / other, default **No**)
picks its wording:

- **Yes** — the guide states the judge permits AI assistance;
- **No** — the guide states submissions must stay hand-written and the agent
  must not produce them;
- yukicoder / AOJ never ask and get the check-the-rules wording;
- Kaggle projects always allow AI coding agents (their `AGENTS.md` says so).

Either way, the guide tells the agent to check the current contest rules
before submitting — they override the answer.

## Reference

- [online-judge-tools/oj](https://github.com/online-judge-tools/oj) — sample
  download / test / submit across judges
- [Tatamo/atcoder-cli](https://github.com/Tatamo/atcoder-cli) — AtCoder
  contest folders
- [YuminosukeSato/AOJ-cli](https://github.com/YuminosukeSato/AOJ-cli) — AOJ
  problem folders, test and submit
- [Kattis/kattis-cli](https://github.com/Kattis/kattis-cli) — the
  `submit.py` client and `.kattisrc` setup

Whatever a judge's rules say is final: the template's recipes and the
`AGENTS.md` wording are a starting point, and the contest's current rules
override them — the template deliberately never automates around a judge's
restrictions.
