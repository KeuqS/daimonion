# Scaffold and Extend the Questionnaire, Layers, and Presets

The `daimonion scaffold` command guides extending the template without
breaking the 272-leaf composition contract or the Z3 reachability invariants.

```sh
# 1. Check consistency across questionnaire, Z3 model, presets, and invariants
daimonion scaffold check

# 2. Add or preview a new question block
daimonion scaffold question my_feature --when "not oj_bare" --help-text "Enable my feature?" --dry-run
daimonion scaffold question my_feature --when "not oj_bare" --help-text "Enable my feature?"

# 3. Scaffold an opt-in layer (include_<layer>)
daimonion scaffold layer grpc --description "gRPC service layer" --dry-run
daimonion scaffold layer grpc --description "gRPC service layer"

# 4. Scaffold a new answers preset under presets/
daimonion scaffold preset grpc-service --base web_api --description "gRPC microservice preset" --dry-run
daimonion scaffold preset grpc-service --base web_api --description "gRPC microservice preset"
```

## What it automates

1. **Z3 Satisfiability Validation**: If a `when` condition contains a typo or is
   logically unsatisfiable (never asked), `scaffold` warns immediately.
2. **Invariants Synchronization**: Provides exact YAML snippets for
   `tests/matrix/invariants.yml` to satisfy witness generation.
3. **One-Command DoD**: After adding features, run `task regen` to regenerate
   witnesses, update test tier records, and synchronize docs.
