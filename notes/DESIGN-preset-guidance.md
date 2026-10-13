# DESIGN: 質問票のプリセット案内（PLAN-widespread-adoption P2 / 内部 HUMAN_TODO Phase 1 補遺）

2026-10-04。対話レンダ利用者に「推奨プリセットから選ぶ」導線を質問票内に
追加するかの判断材料。採否は人間判断（この文書は選択肢と影響範囲の整理）。

## 現状

- プリセットは `presets/<name>.yml`（回答ファイル）。`daimonion new --preset
  <name>` または `copier copy --data-file` で使う。対話レンダ時には一切
  表示されない。
- `project_type`（`copier.yml` 先頭の質問）は `help:` に 8 選択肢の説明を
  持つが、プリセットへの言及はない。プリセットへの既存の言及は
  `questions/_common_b.yml:365`（`bare` プリセット）1 箇所のみ。
- `docs/tutorials/create-new.md` にプリセット一覧表と非対話用法あり。
  `docs/reference/questionnaire.md` は `tools/gen_docs.py` の生成物で、
  プリセット表は持たない（手書き表を入れるなら生成側に実装が要る）。
- copier の質問は `help:` 文字列を持てる（`_combo.yml` 等で多用済み）。
  「導線」を質問票内に実装できる実質的な機構はこれだけ。

## 選択肢と影響範囲

### A. `project_type.help` にプリセット導線を追記（推奨）

8 選択肢の説明の末尾に「同じ構成が `presets/<name>.yml` として出荷されて
いるもの: library/bare/cli/mcp-server/web-api/data-science/ros2/
micropython/online-judge-{atcoder,codeforces,kattis}。非対話なら
`daimonion new --preset <name>`」の 1〜2 行を足す。

- **blast radius: ほぼゼロ**。`help:` は answer でも `when:` 条件でもない
  ため Z3 witness の葉空間（`tests/matrix/witnesses.json`、234 葉基準）
  に影響しない。変わるのは対話時の表示テキストのみ。
- 注意: preset 追加時に help も同期する運用ルールが要る（
  `tests/test_copier_structure.py` 系の構造テストで「プリセット名が
  help に載っている」断言を足すと機械化できる。こちらは実装込みで
  エージェントに振れる）。

### B. `preset:` 疑似質問の追加（非推奨）

質問票の先頭に「プリセットを使いますか」を尋ね、Yes なら以降を `when:`
で畳む設計。

- **blast radius: 大**。新しい asked 質問は全質問の `when:` に影響し、
  witness 葉空間が変わる = `z3_witnesses.py` 再生成 + batch 再判定 +
  層台帳更新（`task regen` のフル実行）。さらに copier の `when:` は
  前問回答への参照なので「preset を選ぶ → その質問群を skip」は
  質問グラフの全ノードに条件を足す必要があり、保守コストが常駐する。
- `--preset`/`--data-file` が既に同機能を CLI 側で提供しており、質問票で
  再実装する必然性が薄い。

### C. ドキュメント側の案内のみ（中間）

`docs/reference/questionnaire.md`（生成物）にプリセット表を生成込みで
載せ、`docs/reference/non-interactive.md` から逆リンクする。
質問票の対話中には届かないが、生成ドキュメントと質問票の乖離を生まない。

- **blast radius: 小**（gen_docs.py の生成ロジック + テスト）。
- A と独立に実施可能。A の導線からこの表を参照させる形が自然。

## 判断

**A（+ 任意で C）を推奨**。導線の目的は「対話で始めた人に非対話経路の
存在を知らせる」ことであり、help 追記で費用対効果が最大。B は leaf
空間の再生成コストに対し CLI 側で既に解決済みの機能を重複させるだけ。

## 人間の判断事項

1. `project_type.help` へのプリセット導線追記を採用するか（A）。
2. 採用する場合、プリセット名と help の一致を構造テストで強制するか。
3. C（生成ドキュメントへのプリセット表）を併せて入れるか。

## 決定（2026-10-05）

**A + 構造テスト、採用済み**（C は未着手 — 生成側に実装が要るため別途）。
`project_type.help` に全 11 プリセット名の列挙と `daimonion new --preset`
導線を追加し、`test_every_preset_is_named_in_project_type_help`
（tests/test_presets.py）でプリセット名 ↔ help の一致を機械化した。
leaf 空間非接触を確認済み。
