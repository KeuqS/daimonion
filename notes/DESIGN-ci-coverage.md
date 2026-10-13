# DESIGN: 未検証の組合せ・経路（archive §19 の残り）

2026-10-04。`notes/archive/TODO-sections-01-27.md` §19「未検証の組合せ・経路を
埋める」に残っている 3 系統と、その実証状況の棚卸し + 追加で取れる選択肢。

## 現状（2026-10-04 時点で実証済み）

| 経路 | 状態 | 実証 |
|---|---|---|
| 生成 CI Python matrix 3.11–3.14 (ubuntu, uv) | ✅ 実走 | daimonion-example CI: test (3.11/3.12/3.13/3.14) 全緑（run 37204484538） |
| 生成 `dist` / `container` / `lint` / `docs` / `hygiene` jobs | ✅ 実走 | 同 run で dist/container/docs/lint 緑。hygiene の gitleaks は 2026-10-13 に license-gated action → pin バイナリ直実行へ置換（secret 不要化、green） |
| テンプレ本体の heavy tier / test-randomly | ✅ 夜間 | ci.yml schedule 03:00 JST 毎日 |
| `_example.yml` publish | ⚠️ 経路は実走済み・現状赤 | deploy key 無効 org ポリシー（内部 HUMAN_TODO Secrets 項 — kasi-x/daimonion-internal） |
| `check_upstream` network モード / `generate_license_template` | ✅ | 2026-09-21 ローカル実走記録（§19 本文） |
| `audit` task | ✅ 週次 | dependency-audit.yml（冒頭コメントに経路明記済み） |
| `use_recommended_agent` 経路 | ✅ | witness 葉 + test_example_layers（fixture 除外は test_answer_fixtures でピン済み） |

## 未実走の残り 3 系統

### 1. 生成 CI の windows/macos

生成 `ci.yml` の test matrix は `runs-on: ["ubuntu-latest"]` に windows/macos
追加のコメント付き。daimonion-example が ubuntu のみなので非ubuntu 実走ゼロ。

- **blast radius 小**: コストは CI 分数のみ。実装は daimonion-example を
  「マルチ OS の例」に変えるだけ（matrix の runs-on を拡張する PR を
  daimonion-example に出す）— ただし `_example.yml` が main を毎回再生成する
  ため、変更は template 側のデフォルトか preset で表現する必要がある。
  例: `ci_os` 構造化回答 or matrix コメントを実値に。
- **費用対効果**: 生成物のほぼ全コードは OS 非依存。OS 差が出るのは
  task runner（task/just/make の Windows シェル差）と pixi の env 周辺。
  `task_runner_effective` の組合せを 1 例だけ macos に載せる形が現実的。
- **保留理由**: matrix に windows を足すと全生成物の CI 分数が増える。
  「デフォルト ubuntu + コメントで拡張可」の現状は設計として既に正しい。
  実証だけ欲しければ witness 葉の 1 つを scheduled-check の週次 matrix で
  windows/macos render+test する追加ジョブ（generated 側 CI でなく
  template 側テストとして）。

### 2. pixi / poetry venv 経路の生成物 CI

example は uv。pixi・poetry 選択時の生成物は render のみで CI 実走なし。

- 実証経路の選択肢:
  - (a) 第 2 example リポ（daimonion-example-pixi）を `_example.yml` から
    週次生成・push → その repo の CI が pixi 経路を実走。コスト: repo 追加。
  - (b) scheduled-check.yml に「pixi render + `task test` 実走」ジョブを
    追加（repo 内完結、重いが既存の witness heavy tier と同型）。
- **推奨は (b)**。(a) は公開 repo をもう 1 つ保守する常駐コスト、
  (b) は週次 CI に載るだけ。

### 3. tag 起点の release 経路（`_release` / `_pypi` / example の release job）

`_release.yml` は tag push でしか走らず、example repo では
`release: skipped`（main push のため）。タグを打たない限り永遠に未検証。

- v1.0.0 タグ（内部 HUMAN_TODO のリリース作業）がこの検証を兼ねる。
  **タグ後に release/example ジョブの結果を確認する** を内部 HUMAN_TODO の
  v1.0.0 項目に追記済みと同義（追加作業なし、タグ自体が trigger）。
- `workflow_dispatch` で `_release.yml` を空打ちする選択肢もあるが、
  release workflow は副作用（release 作成）があるため dispatch 検証は
  dry-run 相当が無いと打てない。設計上は「v1.0.0 で初回実走」を受け入れる。

## 判断まとめ

- **2(b) scheduled-check に pixi render+test を載せる** — 実装可能、コスト週次数分。
  採否は人間判断（weekly CI の分数増）。
- **1・3 は「今のままが設計」または「v1.0.0 で解消」** — 追加実装不要。
  archive §19 の `- [ ]` は「未実走経路の棚卸し完了 + 判断を notes に固定」
  として閉じてよいかは人間判断。
