# PLAN: §36 S5 — invariants / layers の導出化（設計メモ、実装はしない）

対象: TODO.md §49.C「§36 S5: invariants/layers の導出化」。
witness / ledger / docs が生成化済みのいま、残る手動結合点は
`tests/matrix/invariants.yml`（36 leaf 行 + predicates + excluded + merges）と
`tests/matrix/layers.yml`（6 layer 行 + 1 excluded）である。
本メモはリファクタの計画であり、コード・行列ファイルの変更は含まない。

現状の読み方（2026-10-13 実測）:

- `tools/invariants.py` が唯一の reader。`select` を質問票の語彙
  （`tools/questionnaire.py` + `tools/when_model.py` 経由）に照合し、
  行の和集合から leaf の `expect`（ships/absent）・markers・content・
  predicates・tier を出す。`unclaimed` が「どの行も選ばない次元値」を
  拒否するので、新質問・新 layer・新 judge は行追加なしでは通らない。
- 消費者は `tools/z3_witnesses.py`（`expect_for` で committed `expect` を鋳造）、
  `tests/test_witness_matrix.py`（fast tier の file-set 表明）、
  `tests/test_recommended_path.py`（markers の branch tell）、
  `tests/test_render_invariants.py`（predicates の実装所有者。id 表と実装表の
  双方向一致を検査）、`tests/test_invariants.py`（union == committed expect の固定）、
  `tests/test_layer_matrix.py`（layers.yml と live `when` の双方向一致）。
- `tools/predicates.py`（site 収集 + 全 leaf 評価 + 分類木）は導出化の土台に使える
  既存機械である。`tools/gen_docs.py --check/--write` と
  `tools/gen_ethics_appendix.py --check` が drift ゲートの前例である。

---

## 1. 行カテゴリ別の導出可能性判定

`grep '^  - id:'` で数えた現行 41 id のうち predicates 登録 5 件を除く 36 leaf 行を、
「機械が書けるもの」と「人間が書き続けなければならないもの」に分ける。
判定基準は「質問票 + template 条件 + REGISTRY から一意に復元できるか」である。

### 1.1 完全導出可能（ships/absent/content が機械復元できる行）

| # | 行カテゴリ | 該当行 | 導出源 |
|---|---|---|---|
| D1 | layout 行 | `layout=data_science`、`layout=web_api` | `questions/_internal.yml` の `data_science_layout` / `web_api` と、該当 internal を読む template ファイル名条件の走査。`notebooks/.gitkeep`・`data/DEIDENTIFICATION.md`・`app/main.py`・`ethics/regions.yml` はいずれもファイル名 `{% if %}` が所有者。`content` の `[pyproject.toml, polars/fastapi]` も `pyproject.toml.jinja` の同条件分支の走査で復元できる |
| D2 | oj_kind 行 | `oj_kind=kaggle`、`oj_kind=ctf`、`oj_kind=code` | `oj_kind` の静的 choice 値 × `kaggle` / `oj_ctf` / `oj_code` genre internal × `pkg_dir` の分岐（`src/utils` / `challenges/...` / bare）。`content` の `torch` / `pwntools` / `dependencies = []` は pyproject 分岐の走査で復元できる |
| D3 | layer エイリアス行 | `include=include_data_science`、`include=include_web_api` | ships/absent 空で「実体は layout 行」と `why` に明記済み。`has_*`（`questions/_combo.yml`）→ `web_api` / `data_science`（`_internal.yml`）の含意を辿れば、エイリアスであること自体が機械判定できる。真っ先に生成化できる行 |
| D4 | bot platform 派生 6 行 | `include_bot[/_web_api]/bot_platform={slack,line,gmail}` | `bot_platform` の静的 choices × 配置（`web_api` 真なら `app/`、偽なら `src/<pkg>/`）× 依存名対応（slack-bolt / line-bot-sdk / google-api-python-client）の直積。`z3_witnesses.py` の `BOT_PLATFORM_VARIANTS` が既に同直積を別綴りで持つ二重管理であり、導出化で一本化できる最大の重複 |
| D5 | gate_off=agent 行の ships | `gate_off=use_recommended_agent` の `prompts` | `prompts_scaffold`（`_internal.yml`）を読む `template/.../prompts/` パス条件の走査で復元できる |

### 1.2 部分導出可能（骨格は機械、主張は人間の行）

| # | 行カテゴリ | 該当行 | 機械が出すもの / 人間が残すもの |
|---|---|---|---|
| P1 | project_type 8 行 | `project_type={library,cli,script,web_api,data_science,online_judge,ros2,micropython}` | 機械: `pkg_dir` 配置由来の ships/absent（`src/<pkg>/` vs flat `smoke_example/` vs `app/` vs `firmware/main.py` vs `package.xml`）。人間: `markers`（隣接分岐との差分は「何を tell とみなすか」の判断）、`tier`（§1.4）、`why` の設計理由 |
| P2 | layer 実体行 | `include_ctf`、`include_scraping`、`include_mcp`、`include_bot(+_web_api)` | 機械: `*_effective` internal（`ctf_effective` / `scraping_effective` / `mcp_effective` / `bot_*_effective`）を読むファイル名条件の走査（`challenges/...` / `fetcher.py`+`CHARTER.md`+`LEGAL.md` / `mcp_server.py` / `bot_<platform>.py`）。人間: `tier`、配置注記（mcp の src/flat 限定と web_api 配置を gate_off 行が担う分担宣言）、`why` |
| P3 | gate_off=details-chosen 行 | `gate_off=use_recommended_integrations/details-chosen` | 機械: `DETAIL_VARIANTS`（docker / include_mcp）の展開と `.mcp.json`・`app/mcp_server.py` の条件走査。人間: 「inverse template の flagship query がこの構成に一致する」という要求由来の主張 |
| P4 | domain 3 行・distribution 2 行 | `domain=*`、`distribution={commercial,oss}` | 機械: ships/absent 空 + `ethics-appendix` predicate の要否は `_shared/ethics/REGISTRY.yml` の gate 評価から復元できる（`gen_ethics_appendix.py` と同入力）。人間: `tier: fast` の政策宣言と、`why` の法令根拠（CRA art. 24 等の法解釈は質問票から出ない） |
| P5 | gate_off=other 行 | `gate_off=other`（11 gate 列挙・ships 空） | 機械: 「この gate-off 分岐は宣言 artifact を変えない」ことの検証は全 leaf レンダの差分でできる。人間: 「変えない」こと自体の宣言（空集合の主張は走査だけでは「見落とし」と区別できないため、行の存在は残す） |
| P6 | layout=no_src 行 | `absent: [src]` | 機械: `use_src_layout` の定義式と `pkg_dir` の分岐網羅で復元できる。人間: 除外リストが `layout.when` のものと「意図的に異なる」ことの注記（`_internal.yml` のコメント所有）。式が変わったとき注記が陳腐化しないかの目視は残る |

### 1.3 手書き維持（導出しないもの）

| # | 対象 | 理由 |
|---|---|---|
| H1 | 全行の `why`・`markers` | `why` は設計理由・法令根拠・測定証拠の散文であり、質問票からの関数ではない。`markers` は「隣の分岐と何で見分けるか」という検査設計の判断であり、ships の部分集合でもない（data_science の de-identification guide のように witness `expect` にない tell がある）。生成器は `why` の空欄と `markers` の未宣言を拒否する側に回り、中身は書かない |
| H2 | 全行の `tier`（と `support.yml` の `tier_policy`） | tier は「~3 min/leaf の実行コストをどこに払うか」という CI 政策であり、質問票の関数ではない。導出化は tier の複写元を `support.yml:tier_policy` に一本化すること（現状は `why` の文面コピーで二重管理）までとし、値の決定は人間のままにする |
| H3 | `predicates:` 登録 5 件 | id の語彙は `tests/test_render_invariants.py` の実装表が所有者であり、質問票には述語の概念がない。行→述語の割当の一部（`pyproject` は全行、`ethics-appendix` は REGISTRY gate が発火する行）は機械提案できるが、登録自体は手書き維持し、双方向一致検査も残す |
| H4 | `excluded`（project_type=web_django、question={include_sentry, oj_sample}） | いずれも設計判断（生成 abort の非目標、layer ではない詳細質問、leaf 空間が変動させない質問）であり、質問票からは「未計上」として検出できるだけで、除外理由は書けない。`z3_witnesses.py::_check_includes` の declared-not-discovered 規則は維持する |
| H5 | `merges:` 7 kind | adopt-time merge の事後条件であり、質問票・witness・render と無関係な軸が `invariants.yml` に同居している（歴史的経緯）。導出対象ではなく、移転対象（§3 M4 で `tests/matrix/merges.yml` に分割し `tools/invariants.py` の reader を薄く残すか、現状維持かを選ぶ。いずれにせよ生成はしない） |
| H6 | `common` 行の `absent: ["**/*.jinja"]` と `predicates` 割当 | 未レンダ Jinja の残存禁止はレンダ機構全体への不変条件であり、特定質問の関数ではない。`common` の ships（無条件レンダのファイル集合）は機械走査できるが、行の存在と `absent`・述語割当は手書き維持 |
| H7 | `layers.yml` の `why` 全文と `layers.yml:excluded`（include_sentry） | availability の理由（disjointness、executable host、raw-mirror の配置 guard 論）は設計散文であり、`when` 式からは出ない。`bases`・`extras`・`rides`・`revealed_by` の骨格は `when` から復元できる（§2.2）が、`why` と excluded 宣言は手書き維持 |

---

## 2. 生成器の設計

### 2.1 方針: 単一ファイルの完全生成ではなく「政策ファイル + 生成側車」の分離

`invariants.yml` を丸ごと生成すると H1–H6 の人間の主張の置き場所がなくなる。
逆に ships 列だけを手書きに残す現状が drift の温床である。よって分離する:

- 手書き政策ファイル: `tests/matrix/invariants.yml`（現行パス維持）。
  保有するのは `version`・`predicates`・`excluded`・`merges`（M4 まで）・
  各行の `id`・`select`・`markers`・`predicates`・`tier`・`why`。
  `ships`・`absent`（H6 の 1 件を除く）・`content` は削除し、代わりに
  その行の file-set 根拠となる internal 名（例 `origin: data_science_layout`、
  D3 エイリアス行は `alias-of: layout=data_science`）だけを持つ。
  `origin` の語彙は生成器が検査する（未知 internal・発火しない internal を拒否）。
- 生成側車: `tests/matrix/invariants.files.yml`（新設、生成物）。
  行 id → `{ships, absent, content}` のみ。質問票・template 条件・REGISTRY から
  機械復元した file-set 表明。手編集禁止（ヘッダに明記）。
- `tools/invariants.py` は両方を読み、行単位で結合して現行の `LeafClass` を
  再構成する。reader の公開 API（`rows_for`・`expect_for`・`markers_for`・
  `content_for`・`predicates_for`・`tiers_for`・`unclaimed`）は変えない。
  結合失敗（政策行に対応する生成行がない、生成行に対応する政策行がない）は
  `InvariantError` で落とす（現行の loud-failure 規約を継承）。

`layers.yml` は同型の分割をしない。行が 6 件で `bases` 以外の主張が `why` に
密着しているため、生成器 `tools/gen_layers.py`（仮称。`gen_invariants.py` の
サブコマンドでも可）は **骨格の再計算 + 差分報告** に留め、ファイル自体は
手書き維持とする（§2.2）。layers の完全生成はペイしない。

### 2.2 生成器インタフェース

前例（`gen_docs.py --check/--write`、`gen_ethics_appendix.py --check`）に従う:

```
uv run --locked python tools/gen_invariants.py --check   # drift 検証（CI の meta tier が呼ぶ）
uv run --locked python tools/gen_invariants.py --write   # invariants.files.yml を再生成
uv run --locked python tools/gen_invariants.py --check --layers  # layers.yml 骨格の再計算と差分報告（書き換えはしない）
```

入力モデル（すべて既存機械の再利用。新規パーサを作らない）:

1. 質問票形状: `tools/questionnaire.py`（唯一の `!include` resolver）。
   `select` 語彙・`project_type`/`bot_platform`/`domain_traits` の静的 choice 値・
   `oj_kind` の category 別 choice 展開は `tools/invariants.py` の現行実装を流用。
2. 条件意味論: `tools/when_model.py`（`when` 式の Z3 符号化）と
   `tools/predicates.py::collect_sites`（template ファイル名・本体・`_tasks.jinja`・
   質問 `when`・bool internal の全条件 site 収集）+ `evaluate`
  （copier 自身の pass で全 leaf コンテキストを評価）。file-set の真値は
   「条件 site の評価結果」から取り、Z3 モデルと copier 実評価の差異は
   `tests/test_when_model.py` の differential oracle に委ねる（新 oracle を作らない）。
3. ethics 割当: `_shared/ethics/REGISTRY.yml` の gate（`tools/ethics.py` 経由。
   `gen_ethics_appendix.py` と同入力）。domain/distribution 行の述語要否に使う。
4. tier 複写元: `support.yml:tier_policy`。生成器は政策行の `tier.why` が
   対応する `tier_policy` 行の文面と一致することを `--check` で検査する
   （値の決定ではなく複写の検査。H2 の二重管理の解消）。

出力:

- `tests/matrix/invariants.files.yml`: `{id: {ships: [...], absent: [...], content: [[path, substr], ...]}}`。
  順序は政策ファイルの行順（ordered union の意味論を保存するため）。
  D3 エイリアス行は空集合を明示記録（「空であることの表明」と「未生成」の区別）。
- `--layers` 報告: 各 layer の `include_*.when`（`questions/_combo.yml`）を
  copier 自身の questionnaire pass で評価し、`bases`（全 project_type ×
  非 base 節 off での admit 集合）と非 base 節の分類（`extras`=`kaggle` 様の
  ask-time trait / `rides`=`include_*` / `revealed_by`=`use_recommended_*`）を
  再計算。差分があれば非ゼロ exit + 表形式の報告（`test_layer_matrix.py` の
  `_table` 形式を流用）。ファイルは書き換えない（`why` と一体のため）。

`pkg_dir` のようなテンプレート化パス（`src/<pkg>/`・`app/`・`src/utils`・`.`
・flat）の解決は、生成器が `evaluate` の copier コンテキストから
`pkg_dir`・`import_pkg` の値を読むことで行う（文字列走査で `{{ pkg_dir }}`
を解決しようとしない。body 条件と filename 条件の両方を site として扱うのは
`predicates.py` が既にしている）。

### 2.3 検証・drift 検知ストーリー

| 層 | 内容 | 既存物の再利用 |
|---|---|---|
| 生成ゲート | `tools/gen_invariants.py --check` を CI meta tier と `task regen` に追加。`gen_docs.py --check`・`gen_ethics_appendix.py --check` と同列 | `tests/test_generated_docs_sync.py` と同型の sync テスト（`test_generated_invariants_sync.py` 新設。check が緑・drift を検出・write で復旧の 3 件） |
| 意味ゲート（byte-identical 移行期） | 移行完了まで、生成 file-set と現行手書き file-set の完全一致を `test_invariants.py` に追加の一時表明で固定。差分ゼロを確認してから手書き列を削除する（PLAN-improvements §1 共通規約の byte-identical 検証の流儀） | 一時表明は M3 完了で削除 |
| 意味ゲート（恒久） | `unclaimed`（分類漏れ拒否）、union == committed `expect`（`test_invariants.py` 現行）、leaf 双方向一致（`test_layer_matrix.py` 現行）、述語双方向一致（`test_render_invariants.py` 現行）、tier 複写検査（新規。`tier.why` vs `tier_policy`） | すべて現行検査の延長。新規検査は tier 複写の 1 件のみ |
| 実レンダ裏付け | 生成 file-set が実レンダと一致することは witness fast tier（272 leaf 全レンダ）が既に表明。生成器自体の正しさは「生成 file-set == 現行手書き file-set（移行期）」と「fast tier 緑（恒久）」の合成で保証し、生成器のための新規レンダ層は作らない | `task regen` の witness 工程が裏付けを兼ねる |
| layers | `--layers` 報告を meta tier で実行（非ゼロ exit で赤）。`test_layer_matrix.py` の双方向検査は残し、二重の網として維持する | 新規テストなし。Taskfile の regen 工程に 1 行追加 |

`origin` 宣言の検査（政策行が指す internal が実在し、leaf 空間を実際に分割する
こと）は `--check` の一部とする。分割しない internal を指した行は
`predicates.py` の flattening 候補検出と同義であり、腐った `origin` を即座に赤にする。

---

## 3. 移行手順（順序固定・各段の blast radius 付き）

前提: S1–S4 着地済み（TODO §36 記載の順序条件は充足）。各段は独立コミット
（Conventional Commits）し、各段で `test-fast` + 該当テストを緑にする。
横断 `task check` は全段完了後に 1 回だけ（PLAN-improvements §1 規約）。

| 段 | 作業 | blast radius |
|---|---|---|
| M0 | 生成器の読み取り専用プロトタイプ: `tools/gen_invariants.py` が D1–D5 行の file-set を再計算し、現行手書き値との差分表を stderr に出す（ファイルは書かない・検査も足さない）。差分が空でない行は H/P 側の誤記か生成器の誤読かを 1 行ずつ判定し、本メモ §1 の分類を修正する | ゼロ（新規ファイル 1 本。既存の読み書きなし） |
| M1 | D3 エイリアス 2 行 + D4 bot 派生 6 行の生成化。政策ファイルに `alias-of` / `origin: bot_platform` を導入し、`invariants.files.yml` を新設、loader に結合処理を追加。`test_invariants.py` に一時 byte-identical 表明を追加 | 小（loader + 8 行。witness `expect` は byte-identical のため下流テストへの波及なし。BOT_PLATFORM_VARIANTS との重複整理はここではせず、重複の存在を注記に留める） |
| M2 | D1・D2・D5（layout / oj_kind / prompts）の生成化。政策行に `origin` を付与し、手書き ships/absent/content を削除。`test_generated_invariants_sync.py` 新設（check 緑・drift 検出・write 復旧） | 中（13 行前後。`z3_witnesses.py` の鋳造 `expect` が生成経由に切替わるが、M0–M1 の手順で byte-identical を事前確認済みのため witness Troyes への波及は差分ゼロのはず。差分が出たら M2 を割らず原因行だけ戻す） |
| M3 | P1–P6（project_type / layer 実体 / gate_off / domain / distribution / no_src）の生成化と一時表明の削除。`tier.why` の `tier_policy` 複写検査を追加。`z3_witnesses.py` の `INCLUDE_LAYERS`・`DETAIL_VARIANTS`・`BOT_PLATFORM_VARIANTS`・`DOMAIN_TRAIT_*`・`DISTRIBUTION_VARIANTS` 定数群を生成器のモデルから import する形に一本化（または一本化しない決定を記録。二重管理の解消はここが唯一の機会） | 大（残り全行 + witness 生成定数。 reviewer は `expect` 差分ゼロと fast tier 緑で確認する。`task regen` 工程に `gen_invariants.py`（check/write）と `--layers` 報告の 2 行を追加するのもここ） |
| M4 | `merges:` の `tests/matrix/merges.yml` への分割（または現状維持の決定記録）。`tools/invariants.py` は後方互換の reader を残し、`tests/test_merge_contracts.py` の参照先を移す。`layers.yml` の `--layers` 報告を meta tier に配線 | 小〜中（merge 契約の読者は adopt 系のみ。witness 系への波及なし。維持決定の場合は本メモ §1 H5 を根拠に TODO §49.C に 1 行記録して閉じる） |

M3 の定数一本化だけは判断が要る。`z3_witnesses.py` の variant 定数は leaf 空間の
「宣言」であり、生成器のモデルは質問票の「読影」である。宣言と読影を同一モジュールに
すると「質問票を変えたら leaf 空間が黙って変わる」形になり、TODO §23.4 の
declared-not-discovered 規則と衝突する。推奨は「定数は `z3_witnesses.py` に残し、
生成器が両者の一致を `--check` で検査する」であり、import 一本化はしない。
（`gen_ethics_appendix.py` が REGISTRY を読んで鎖を「書く」のに対し、こちらは
leaf 空間の宣言を「検査する」に留める、という非対称が正しい。）

---

## 4. リスクと非目標

- R1 body 条件の見落とし: file-set はファイル名条件だけでなく本体 `{% if %}`
  分岐（pyproject 依存・AGENTS.md 節・README 分岐）にも依存する。生成器は
  `collect_sites` の全 kind を入力にし、filename-only の簡易実装にしない。
  `content`（[path, substr]）は本体走査なしには復元できないため、本体 site の
  取込みは M0 の受入条件とする。
- R2 空集合の曖昧さ: P5・D3 の空 ships は「主張としての空」と「未生成の空」の
  区別が必要。生成側車に空集合を明示記録し、loader の結合検査で欠落と区別する。
- R3 gate_off=other の 11 gate 列挙: 新 gate 追加時に列挙が陳腐化する。
  `--check` で「GATE_PREFIX 質問の全数 == 列挙数 + 個別行が担う gate 数」を検査し、
  陳腐化を赤にする（`_check_includes` と同型の全体会計）。
- R4 テンプレート化パスの解決: `{{ pkg_dir }}` を含むファイル名は文字列比較
  できない。copier コンテキストの評価値で解決する（§2.2）。評価不能 site は
  unevaluable として報告し、黙って落とさない（`predicates.py::evaluate` の規約継承）。
- R5 移行期の二重真値: 手書き列と生成列が併存する M1–M2 期間はどちらが真か
  不明になる。loader は政策ファイルの `origin` がある行は生成値を真とし、
  手書き値が残っていたら即座に `InvariantError`（二重定義の拒否）とする。
- 非目標: `why`・`markers`・`tier` 値・述語実装・merge 条件の生成はしない（H1–H5）。
  witness leaf 空間そのもの（272 葉の宣言）の生成化もしない（M3 末尾の決定通り検査に留める）。
  `layers.yml` ファイル自体の生成化もしない（骨格報告まで）。
- 非目標: 本メモは計画であり、M0–M4 の実装・`invariants.files.yml` の新設・
  TODO.md の更新はいずれも含まない。着手は TODO §49.C のチェックを付ける人間判断を待つ。
