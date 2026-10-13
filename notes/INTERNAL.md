# Internal memos moved out of this repository (2026-10-13)

The following working memos were moved to the private repository
`kasi-x/daimonion-internal` (same relative layout under `notes/`):

- `HUMAN_TODO.md` — human-task checklist (single source of truth there)
- `notes/outreach/` — Show HN / Zenn / newsletter / awesome-list drafts
  (draft texts lose effect if their audience can read them here)
- `notes/upstream-drafts/` + `notes/COPIER_UPSTREAM.md` — copier upstream
  issue/PR drafts, patches, and the filing procedure (copier AI_POLICY
  requires a human to write and file every submission)
- `copier-fork/` — fork workbench (feature specs, patch exports, sync
  scripts). The contribution branches themselves stay public at
  `kasi-x/copier` (`f3-missing-batch`, `f5-stale-tag-warning`,
  `f6-trust-discoverability`, `f7-pretend-summary`); `periodic.yml`'s
  `patch-rot` job now verify-applies those branch diffs against the pinned
  upstream tag instead of local patch files.

If you are a maintainer without access, ask the org owner for an invite.
