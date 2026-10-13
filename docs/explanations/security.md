# Security & compliance posture

Both this template repository and the projects it generates follow the
[OpenSSF Scorecard](https://securityscorecards.dev) checks. This page maps
each Scorecard check to the mechanism that satisfies it.

## Scorecard checks → implementation

| Scorecard check | Risk | Mechanism |
|---|---|---|
| Token-Permissions | Critical | Every workflow declares `permissions: contents: read` (or a narrower job-level scope); checkout steps set `persist-credentials: false` except the workflow that pushes the example repo |
| Pinned-Dependencies | High | renovate's `helpers:pinGitHubActionDigests` converts every third-party `uses:` to a 40-char commit SHA (with the version tag as a comment); `unpinned-uses` is re-enabled in zizmor once the pinning PR lands. What renovate cannot see — the gitleaks binary, actionlint digest, zizmor cli/action pair and the three `uvx` tool pins in the hygiene and security workflows — is tracked by the weekly `check-upstream.yml` drift check (`tools/check_upstream.py`, `tests/test_security_pins.py`) |
| Dangerous-Workflow | Critical | No `pull_request_target`; `github.event` contexts are never interpolated into `run:` shells (zizmor's `template-injection` audit is enabled) |
| SAST | Medium | zizmor (`.github/workflows/security.yml`) audits the workflow files on every push/PR; pip-audit scans dependencies via the on-demand `audit` task, run on a schedule by the weekly `Dependency audit` workflow (`dependency-audit.yml`, Thursdays 07:00 UTC + manual dispatch, which opens a deduplicated issue on findings) |
| Security-Policy | Low | Root `SECURITY.md`; generated projects get one under the `use_recommended_security` gate |
| Branch-Protection | High | Not enforceable from the repo: enable signed commits, linear history and required reviews in GitHub settings / rulesets |
| Binary-Artifacts | High | `.gitignore` excludes build outputs; no compiled artifacts are committed |

## Scorecard score, tracked weekly

Measured 2026-10-14 via the [public Scorecard API](https://api.scorecard.dev)
(`GET /projects/github.com/ConstitutiveTemplates/daimonion`, Scorecard
v5.5.0, commit `3185c0e6`): **5.2 / 10**. The API refreshes on each call —
re-measure with `curl -s
https://api.scorecard.dev/projects/github.com/ConstitutiveTemplates/daimonion`
and update the table below, not the prose around it. The weekly
`scorecard.yml` run (push to `main` + Saturdays 01:30 UTC,
`publish_results: true`) keeps the published result current; the weekly
`check-upstream.yml` run (Mondays 06:00 UTC) keeps the pins behind the
scores current. Neither workflow records history — the table is the record,
so append a dated row when the score moves instead of editing old ones.

| Scorecard check | Score | Dated finding → response |
|---|---|---|
| Token-Permissions | 10 | 2026-10-14: least-privilege holds. Five `contents: write` grants remain, each with a stated reason: `ci.yml` docs/release jobs (gh-pages publish, GitHub Release creation), `scheduled-check.yml` docs pass-through (a reusable workflow's permissions may not exceed the caller's), `_release.yml` release job (called workflows receive the intersection), `update-rehearsal.yml` (report push + results PR). No change needed. |
| Pinned-Dependencies | inconclusive | 2026-10-14: `internal error: invalid Dockerfile` — the check cannot parse the template's Jinja-gated `Dockerfile` (`{% if docker or cicd_extras %}`), not a real unpinned dependency. Every `uses:` is SHA-pinned (`tests/test_workflow_security.py`) and renovate's `helpers:pinGitHubActionDigests` keeps the digests current. No change needed; re-check if Scorecard learns to skip `.jinja` Dockerfiles. |
| Dangerous-Workflow | 10 | 2026-10-14: no dangerous patterns. Guarded by zizmor's `template-injection` audit on every push/PR. |
| SAST | 0 | 2026-10-14: `no SAST tool detected` — Scorecard only recognises its own allowlist (CodeQL et al.), not the zizmor workflow audit that actually runs here on every push/PR (`security.yml`) plus weekly pip-audit (`dependency-audit.yml`, Thursdays 07:00 UTC). Accepted gap: the mechanism exists, the badge does not. |
| Security-Policy | 10 | 2026-10-14: policy detected (`SECURITY.md` with disclosure, vulnerability and timeline text). |
| Branch-Protection | 0 | 2026-10-14: `branch protection not enabled for branch 'main'` (verified: `GET /repos/{repo}/branches/main/protection` → 404 `Branch not protected`). Not enforceable from the repo — enable in GitHub settings / rulesets (signed commits, required reviews). Human action, still open. |
| Binary-Artifacts | 10 | 2026-10-14: no binaries committed. |
| Signed-Releases | 0 | 2026-10-14: release 7.0.0 ships neither signatures nor provenance. Commits are likewise unsigned (`git log --show-signature` → `N`, no key configured). Human action, still open: sign tags / attach provenance when cutting the next release. |
| Dependency-Update-Tool | 10 | 2026-10-14: renovate detected. |
| Vulnerabilities | 10 | 2026-10-14: 0 known vulnerabilities (OSV feed). Backstop: weekly pip-audit opens a deduplicated issue on findings. |
| License | 10 | 2026-10-14: license detected (Apache-2.0, REUSE-compliant `LICENSES/` + `REUSE.toml`). |
| Code-Review | 0 | 2026-10-14: `0/30 approved changesets` — a young-repo artefact (created within the last 90 days), not a process gap; reviews happen but the 30-changeset window is not full yet. |
| Maintained | 0 | 2026-10-14: same 90-day new-repo notice. Rises with age, not action. |
| Contributors | 3 | 2026-10-14: 1 contributing organisation. Informational, not a gate. |
| CI-Tests | inconclusive | 2026-10-14: `no pull request found` — the check needs merged PRs to evaluate; CI runs on every push/PR regardless. Rises with history, not action. |
| Packaging | inconclusive | 2026-10-14: `packaging workflow not detected` — expected: this is a copier template, not a distributable package (generated projects own the PyPI publish path). |
| CII-Best-Practices | 0 | 2026-10-14: no badge effort registered. Accepted gap unless a downstream consumer requires it. |
| Fuzzing | 0 | 2026-10-14: not fuzzed. Accepted gap: a template repo has no long-running parser surface of its own to fuzz. |

Score history:

| Date | Score | Note |
|---|---|---|
| 2026-10-14 | 5.2 | First recorded measurement (Scorecard v5.5.0, commit `3185c0e6`). |

## Repository hygiene files

The "repo layout" items from the OSPS baseline live at these paths:

- `.github/workflows/` — hardened CI/CD (SHA pins, least-privilege, SAST,
  scorecard on `main` + weekly)
- `.github/ISSUE_TEMPLATE/` — structured issue forms with validation
- `.github/CODEOWNERS` — change approval for CI/security-sensitive paths
- `LICENSES/` + `REUSE.toml` — [REUSE](https://reuse.software) license
  compliance (aggregate SPDX annotation; the project license is Apache-2.0)
- `CITATION.cff` — machine-readable citation metadata
- `codemeta.json` — CodeMeta software metadata (JSON-LD)
- `SECURITY.md` — coordinated vulnerability disclosure

## Generated projects

When you generate a project, the `use_recommended_security` gate (default
**yes**) ships:

- the same hardened CI: minimal permissions, SHA-pinned actions (renovate
  keeps the digests current), a zizmor CI job, `SECURITY.md`;
- a generated `tests/test_qa.py` that verifies every module imports, the
  `__all__` public API resolves, and no module imports a missing internal
  sibling (dependency completeness against `pyproject.toml` is deptry's
  static job, run in `task type-check`).

The gate applies to GitHub projects. GitLab projects skip `SECURITY.md` and
the Scorecard workflow (GitHub private advisories and the Scorecard badge
both require github.com); they keep the hardened `.gitlab-ci.yml` instead.

Answer **No** to the gate (on GitHub) to also choose:

- `security_policy` (default yes): include `SECURITY.md`;
- `scorecard` (default no): add the OpenSSF Scorecard workflow + README
  badge. Only meaningful for public repositories — the badge and published
  results require one.
