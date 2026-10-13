# Run the tests

The fast path is the tiered loop in [Check a Change Without the Full
Suite](test-loop.md): `task test-fast` for the edit loop (no venv, no
network), `task test-heavy` before pushing dependency/toolchain changes,
`task test` as the pre-release gate with coverage. The tiers and their
budgets are the contract — this page is only the one-line entry point.

```sh
task test-fast   # edit loop
task test        # everything, with coverage (see [Coverage](coverage.md))
```
