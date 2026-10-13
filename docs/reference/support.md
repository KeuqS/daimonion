<!-- BEGIN GENERATED: support-matrix (tools/gen_docs.py --write) -->
Every combination this template keeps working, the tier that guarantees
it, and the measured evidence behind that tier.

## Supported

Executed end to end in CI by the witness full tier: `uv sync`, the
generated project's own pytest, basedpyright and its docs build.
Measured at ~3 minutes per leaf, so only these 8 run it.

| combination | tier | why |
|---|---|---|
| `project_type=library/gate=recommended` | `full` | recommended library path, executed end to end (~3 min): uv sync + generated pytest + basedpyright + docs |
| `project_type=cli/gate=recommended` | `full` | recommended CLI path, executed end to end (~3 min): console-script entry point and its CLI tests in the generated pytest run |
| `project_type=web_api/gate=recommended` | `full` | recommended web-API path, executed end to end (~3 min): FastAPI + SQLAlchemy + Alembic stack, tests against SQLite |
| `project_type=data_science/gate=recommended` | `full` | recommended data-science path, executed end to end (~3 min): the torch dependency sync is the slowest leaf but still inside the sample |
| `project_type=script/gate=recommended` | `full` | recommended script path, executed end to end (~3 min): flat stdlib-style workspace, pytest + basedpyright + docs run |
| `project_type=micropython/gate=recommended` | `full` | recommended MicroPython path, executed end to end (~3 min): generated type checks pass against the micropython-*-stubs |
| `project_type=online_judge/gate=recommended/oj=competitive_coding/atcoder` | `full` | AtCoder workspace, executed end to end (~3 min): the one online-judge leaf in the sample; the other judges render only |
| `project_type=cli/gate=off:use_recommended_agent` | `full` | the only branch-only artifact set in the sample: the agent gate off renders prompts/, which no recommended leaf produces |

## Best effort

Declared so the questionnaire's existing answers keep rendering, but
never executed by CI. The witness fast tier renders and ruff-checks
these leaves (272 renders at ~1.3 s each, 10-20 s in parallel); a
regression that only breaks install or run is not caught there.

| combination | tier | why |
|---|---|---|
| `task_runner = make \| poe \| invoke \| duty` | `best_effort` | measured: only lint/test/check execute (test_task_runners.py::test_lint_task_executes for all four, ::test_test_task_executes_on_make, ::test_check_task_executes_on_poe); fix/type-check/audit/license-check/docs/docs-serve are render-only on these runners, and no witness leaf selects one |
| `package_manager = poetry` | `best_effort` | no witness leaf selects it (every leaf renders uv), but the weekly poetry-render-test job proves install/run: a poetry render ships an explicit [tool.poetry] packages table plus an importlib.metadata _version fallback, so `poetry install` + the generated pytest pass; tests/test_example_toolchain.py::test_template_poetry pins both |
| `log_library = loguru \| picologging` | `best_effort` | structlog is the default and the full sample exercises only it; loguru/picologging execute solely in the network-marked test_example_toolchain cases (::test_template_log_library_loguru / ::test_template_log_library_picologging) |
| `type_checker = ty` | `best_effort` | pyrefly is the checker with deps installed (test_generated_typecheck.py runs `pyrefly check`); ty is render-only (tests/test_example_docs_ci.py::test_template_ty asserts the rendered pyproject) |
| `project_type=ros2` | `best_effort` | the full tier omits it: the generated test/build recipes need a ROS distribution (/opt/ros/$ROS_DISTRO), not a bare runner; the fast tier still renders all 8 ros2 leaves |
| `project_type=online_judge/.../oj=* except atcoder` | `best_effort` | the non-AtCoder judges (leetcode / yukicoder / aoj / codeforces / kattis / other / ctf / kaggle) render and ruff-check in the fast tier but never get a venv; only atcoder is in the full sample |
| `any leaf under an opt-in layer (include_ctf \| include_data_science \| include_scraping \| include_web_api \| include_bot)` | `best_effort` | the layer leaves render and ruff-check in the fast tier; only the eight sampled leaves get the execution tier |
| `any detailed-question branch (gate=off:use_recommended_*)` | `best_effort` | only cli/gate=off:use_recommended_agent is in the sample; the remaining gate-off branches are fast-tier renders, not executions |
| `any domain-trait variant (domain_traits selects personal-data / face-recognition / medtech)` | `best_effort` | the domain traits route ethics sections and one dependency; the derived variants render and ruff-check in the fast tier, and the sections' presence is asserted by the ethics-appendix predicate there rather than by executing a project |
| `any distribution variant (distribution answers commercial and/or oss)` | `best_effort` | the distribution answer routes the EU CRA section; the derived variants render and ruff-check in the fast tier, and the art. 24 exemption (oss alone ships nothing) is asserted by the additivity check rather than by executing a project |

## Tier policy

Which tier each class of witness leaf is declared for. `none` is
reserved for a future W4 exclusion: it is declared as `tier: none`
plus a `reason` in `tests/matrix/witnesses.json`, and no leaf uses it
today because every declared leaf has a recorded fast-tier run.

| leaf_class | tier | why |
|---|---|---|
| `project_type=*/gate=recommended (library, web_api, cli, data_science, script, micropython, online_judge)` | `full` | one leaf per project family is executed end to end; ros2 is deliberately not among them (see below) |
| `project_type=cli/gate=off:use_recommended_agent` | `full` | the branch-only prompts/ artifact set is only produced with the agent gate off, so its leaf is in the sample |
| `project_type=ros2/gate=recommended` | `fast` | render + ruff only: executing a ros2 leaf needs /opt/ros/$ROS_DISTRO on the runner |
| `project_type=*/gate=off:use_recommended_* (detailed branches)` | `fast` | rendered and ruff-checked; the 3 m/leaf execution cost limits the full tier to the sample above |
| `project_type=*/.../include=include_*` | `fast` | the opt-in layers (ctf / data_science / scraping / web_api / bot) are coverable by rendering: their artifacts are file-set invariants; the bot layer's real execution is tests/test_bot_layer.py's heavy case |
| `project_type=online_judge/.../oj=*` | `fast` | AtCoder carries the execution sample; leetcode / yukicoder / aoj / codeforces / kattis / other / ctf / kaggle are render-only |
| `project_type=*/.../domain=* (domain_traits variants)` | `fast` | a domain trait adds an ethics section (and for face-recognition a dependency) and no artifact: its presence is the ethics-appendix predicate's business, which render + ruff-check already exercises. The co-occurrence leaf is what the additivity check compares against the solo ones |
| `project_type=*/.../distribution=* (distribution variants)` | `fast` | the distribution answer adds one ethics section (the EU CRA duties on `commercial`) and no artifact; render + ruff-check exercises it, and the additivity check pins that `oss` alone ships nothing (art. 24's non-commercial exemption) |
| `(reserved) no class today` | `none` | every declared witness leaf has a recorded fast-tier run; tests/matrix/witnesses.json keeps the tier:none + reason hook as the future exclusion mechanism |

## Update rehearsal

No rehearsal has been recorded yet.
<!-- END GENERATED: support-matrix -->
