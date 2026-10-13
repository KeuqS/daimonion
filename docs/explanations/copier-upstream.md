# Working With Upstream copier

daimonion is built on [copier](https://github.com/copier-org/copier) and drives
it harder than most templates do: non-interactive renders in CI, a wrapper CLI,
presets, an update rehearsal against every release, and coding agents that
render projects through the template's MCP server. Where that use runs into
friction in copier itself, we work around it in this repository first. This
page records those frictions with reproductions, so anyone, including copier's
maintainers, can check them against the copier they have installed.

It is a log of where we ran into trouble, not a wishlist. copier's design is
copier's to decide; the workarounds below already keep daimonion working
whatever upstream does.

## How daimonion drives copier

- **Non-interactive by default.** The documented commands and the CI matrix run
  `copier copy --trust --defaults --data-file ...`
  ([Non-Interactive Generation](../reference/non-interactive.md)). Every asked
  question must therefore have a default, and
  `tests/test_copier_structure.py::test_every_asked_question_has_a_default`
  checks that.
- **Unsafe features on purpose.** The template uses `_tasks` and `_migrations`,
  so every render needs `--trust`. The shipped CLI (`tools/cli.py`) passes it
  for the user.
- **Tag-based releases.** `copier copy <url>` expands the newest tag, so the
  release tag *is* the user-facing version (see
  [Branching Model](branching.md)).
- **Pinned in CI.** copier is pinned `<10` in `pyproject.toml`, and the weekly
  `periodic.yml` run checks our patch branches against a fixed copier tag.

## Frictions we have hit

All reproductions below were last run on copier 9.19.1 (2026-10-14) with this
minimal template:

```shell
mkdir tpl && cd tpl
printf '_tasks:\n  - echo hi\nname:\n  type: str\n' > copier.yml
echo '{{ name }}' > out.txt.jinja
git init -q && git add -A && git commit -qm init && cd ..
```

### Refusing an unsafe template looks like a failed run

```console
$ uvx copier copy --defaults tpl dst
Template uses potentially unsafe feature: tasks.
If you trust this template, consider adding the `--trust` option when running `copier copy/update`.
$ echo $?
4
```

Nothing was written to `dst`, and the message does not say so. We misread this
ourselves: our own tracker logged it as "`--data-file` values are not applied
to `when` conditions", and only later did we find that the missing `--trust`
was the real cause. Exit status 4 means "refused as unsafe", but that is
only recorded in a code comment in `copier/_cli.py`, not in copier's docs.

The message also points at `--trust` only. copier's settings file can trust a
template permanently (`trust:` in `settings.yml`), but the message does not
mention it.

**What we do locally:** the wrapper CLI always passes `--trust`;
[Non-Interactive Generation](../reference/non-interactive.md) has a
troubleshooting table that maps "exit 4, nothing generated" to `--trust`.

### Missing required answers are reported one at a time, as a traceback

```console
$ uvx copier copy --trust --defaults tpl dst
Traceback (most recent call last):
  ...
ValueError: Question "name" is required
```

In CI this costs a full round trip for every missing answer, and the
traceback makes a configuration problem look like a crash in copier.

**What we do locally:** every question has a default, enforced by the test
named above.

### `--answers-file` path errors

`--answers-file` is relative to the destination. An absolute path fails
validation with a raw pydantic error:

```console
$ uvx copier copy --trust --defaults --answers-file /tmp/ans.yml tpl dst
  Value error, "/tmp/ans.yml" is not a relative path [type=value_error, ...]
```

A path relative to the current directory, which is the usual guess, is
silently resolved against the destination instead, not found, and the run then
fails with the unrelated `Question "name" is required` above.

**What we do locally:** our docs use `--data-file` for answers prepared ahead
of time and say that `--answers-file` is destination-relative.

### Implicit latest-tag checkout can be far behind

When daimonion was still a fork, it inherited 38 tags from the template it was
forked from. `copier copy <url>` resolved to the newest *inherited* tag and
rendered an old questionnaire, with no hint that the default
branch had moved on. Our docs had to pin `--vcs-ref` everywhere until we
deleted the inherited tags.

**What we do locally:** the inherited tags are gone, and `tools/adopt.py` uses a
tag only when it carries the current questionnaire
(`tests/test_adopt.py::test_resolve_ref_uses_a_tag_only_when_it_carries_the_questionnaire`).

### Jinja extension dependencies are invisible to `uvx copier`

Early versions used `copier-template-extensions`. `uvx copier copy` runs copier
in an isolated environment, so the extension import failed until users learned
to run `uvx --with copier-template-extensions copier ...`. A template has no
way to declare the packages its extensions need.

**What we do locally:** we removed the extension dependency altogether.

## What we have prepared

Four small changes live as branches on our fork,
[kasi-x/copier](https://github.com/kasi-x/copier), each one commit on top of
copier's history:

| Branch | Change |
| --- | --- |
| `f6-trust-discoverability` | The unsafe-template refusal also mentions the `trust` setting; `generating.md` links to it. |
| `f3-missing-batch` | Under `--defaults`, collect every required question without a default and report them in one clean error. |
| `f7-pretend-summary` | `--pretend` prints a one-line summary confirming the dry run. |
| `f5-stale-tag-warning` | Warn when the implicit latest tag is behind the default branch. |

They are proposals to discuss, not requests to merge. Whether to open any of
them as a pull request is decided case by case, after talking to copier's
maintainers, and following their contribution rules.

## How this project uses AI

This repository is developed with heavy help from AI coding agents, and the
agent configuration in the repository shows it. The branches above were
written with that help as well.

copier's [AI policy](https://github.com/copier-org/copier/blob/master/AI_POLICY.md)
requires a human to write issues and pull requests in their own words and to
understand what they submit. Anything this project brings to copier follows
that policy: the daimonion maintainer writes and files it personally, and
answers review personally. Where a translation tool is used, the original text
is included as the policy suggests. Nothing is filed by an agent.
