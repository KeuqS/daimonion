# Run GitHub Actions locally with act

[nektos/act](https://github.com/nektos/act) runs this repository's workflows
on your machine, inside Docker containers, before you push. The push->CI loop
is minutes long and shared with everyone; the local loop is seconds-to-minutes
and free.

## Setup (once per machine)

- Docker running (`docker info`).
- The `act` binary (>= 0.2.80): install from
  [nektos/act releases](https://github.com/nektos/act/releases) into
  `~/.local/bin`, or `brew install act`.
- The repository's `.actrc` maps `ubuntu-24.04` to
  `catthehacker/ubuntu:act-24.04` — an Ubuntu-like runner image. act's own
  default (`node:16-buster-slim`) cannot run this repository's jobs, which
  need apt, git and a glibc Python; the catthehacker image covers that, and
  the jobs install everything else themselves (uv, task, toolchains), exactly
  as they do on GitHub's runners. First use pulls the image (~1.5 GB).

## Running a workflow

```sh
task act                                   # ci.yml, all jobs (push event)
task act JOB=lint                          # one job
task act WORKFLOW=witness.yml EVENT=pull_request
task act JOB=test CLI_ARGS="--dryrun"      # plan without executing
```

`-W` targets any workflow file under `.github/workflows/`, including the
reusable ones (pass `EVENT=workflow_call` for `_*.yml` files).

## What transfers and what does not

- Job logic, steps, conditions, matrix, `timeout-minutes` and the actions
  themselves run for real: a local failure is a real failure.
- GitHub-hosted specifics do not: the Actions cache (act serves a local
  cache server, so cache steps run but do not persist), deploy keys and
  environment secrets (put fakes in a git-ignored `.secrets` file), branch
  protection, and Pages deployment. Jobs that exist only to publish
  (`_release.yml`, `_docs.yml`) are better left to real CI.
- The rendered tree your local run sees is your **working tree** — including
  uncommitted edits — which is exactly the point: break the lint job, run
  `task act JOB=lint`, fix, repeat, and push only when the remote loop would
  have been green anyway.
