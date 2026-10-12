# TODO アーカイブ: 完了セクション §28–§44(2026-10-12 移動)

> 移動元: `TODO.md`（daimonion 直下）。行番号は移動時点の TODO.md の
> 行番号を節見出しに記した(例: `## 28.` は旧 L137、`## §30` は旧 L545)。
> 本文・コード・docs の「TODO.md §xx」参照は番号で追える。
> §1–27 は別ファイル `TODO-sections-01-27.md`。
>
> 収録節(全て完了/着地済み):
> - §28 設計監査(旧 L137–437、41 項目すべて着地)
> - §30–§34(旧 L545–798、完了記録)
> - §38–§39(旧 L1067–1175、法務エコシステム分離 + daimonion 改名、着地)
> - §41–§42(旧 L1211–1325、レビュー改善点 + ライフサイクル構想、全項目着地)
> - §44(旧 L1377–1434、エコシステム横断改善 wave)
>
> TODO.md に残すのは設計原則・索引・条件付き保留(§29/§35–§37)・
> 人間作業待ち(§40)・維持判断基準(§43)のみ。

---

<!-- 旧 TODO.md L137–L437 -->
## 28. 設計監査: 4 領域レビューと、リファクタリング・設計変更の候補（2026-09-17）

質問票 / template payload / tools / テスト検証の 4 領域を並行で監査した。主要な主張は
記載前に実ファイルで再検証済み（行番号・数値はその時点の実物）。見つかったものは
「文書が実装に追いついていない」「単一源がコメント同期に逆戻りした」「自分の定めた
予算を強制していない」の 3 クラスに集約され、構造の作り直しは一件も無い。28.5 は
振る舞いを保つリファクタリング候補、28.6 は決め事が必要な設計変更候補。各項目は
作業時に個別 PR へ分割してよい。

### 28.0 総評 — 維持すべき構造（以下の指摘はここを壊さない範囲で処理する）

- **3 層検証モデルと、その単一源**: invariants.yml / witnesses.jsonl / witnesses.json /
  tiers.json / answers.BASE の全レジストリにガードテストがあり、双方向（行が葉に到達 /
  葉が行を再現）で閉じている。未ガードのレジストリは今回 1 つも見つからなかった。
- **tools の宣言済みレイヤー表** (`tests/test_tool_layers.py`): 未宣言モジュール・上向き
  import・腐った例外で落ちる。import graph に循環・神モジュールは無い。
- **use_recommended_* の正準順序**のピン (`tests/test_copier_structure.py:55-66`) と
  include 順前方参照の機械強制。AGENTS.md は宣言どおり内蔵初期構成（個別 ON/OFF 質問なし）。
- **when_model の Z3 エンコーダ**（typo literal を unsat にする）と predicates の
  DECLARED_EQUIVALENCES（未宣言同値の拒否と、宣言の陳腐化の両方で落ちる）。
- `_internal.yml` の派生層と effective 家族、データファイル強制回答への 3 層防御
  （when / `combinable` / `has_*`。`_combo.yml:147-158`）。

### 28.1 原則と実装の乖離（決着は「文書か実装か、どちらかを直す」）

- [x] **1a. raw/effective ルールの文書乖離（実装が正。文書を直す）**:
  `docs/explanations/template-dev.md:130-132` は「質問の `when:` は raw 回答のみを使い、
  派生 internal を決して読まない」と宣言するが、実態は `questions/data_science.yml:9`
  (`has_data_science`)、`questions/web_api.yml:8` (`has_web_api`)、
  `questions/_common_b.yml:220` (`not oj_bare`)、`:228` (`not online_judge`)、
  `questions/online_judge.yml:110`、`questions/_combo.yml:29` 等 ~10 箇所が internal を
  読む。運用上の本当のルールは「**include 順で前方参照なら internal も読める**」で、
  これを機械強制しているのは `test_question_references_are_forward_only`。
  ルールを信じた貢献者が `has_web_api` を「修正」して質問を沈黙させる事故が起きるので、
  文書を include 順ルールとして書き直す（include_mcp の手動同期注記はその例外節に吸収）。
  → **完了（2026-09-17）**: template-dev.md を「ask time は include chain の prefix まで読める / render time は全部」の実態ルールに書き直し（内部変数参照 ~10 箇所を真正化）。include_mcp の手同期注記は例外節へ吸収し、test_predicate_classifier と question_graph --where のヘルプ文言も追随
- [x] **1b. include_bot ゲートの穴**: `questions/_common_b.yml:284` の include_mcp は
  `or include_web_api` まで手書きで同期しているが、姉妹の `include_bot`
  (`questions/_combo.yml:94`) は `project_type in ['cli', 'web_api']` のみ。
  結果、`library` + include_web_api の同一実効構成で MCP は聞かれ bot は聞かれない
  （`bot_effective` `questions/_internal.yml:90` は実効 web_api を使うので実装側の非対称）。
  ゲートを揃えるか、28.6 D1 の行列化に吸収させる。ピンテストを足す。
  → **完了（2026-09-17）**: include_bot.when を `or include_web_api` まで include_mcp と揃え（手同期コメント付き）、`test_include_bot_and_include_mcp_gates_stay_in_sync` で固定。葉空間は 228 のまま不変
- **1c. レイヤー可用性行列が未宣言**: 6 レイヤーの base 集合（scraping={cli}、
  ctf={library,cli}、bot={cli,web_api}、mcp={cli,web_api,+include_web_api}、
  data_science={library,cli,web_api}、web_api={library,cli,data_science,+kaggle}）は
  どこにも宣言されておらず、理由が書けない非対称がある（kaggle は web_api 層可・
  data_science 層不可、data_science に bot/mcp/scraping は出ない等）。
  → 28.6 D1。
- [x] **1d. 無音の回答破棄 3 件**:
  - `layout` は `script` でも聞かれる（`questions/_common_b.yml:22` の除外リストに
    script 無し。help は src 推奨）が、`use_src_layout` (`questions/_internal.yml:148`)
    が script を除外するため src と答えても捨てられる。定義箇所のコメントは自認済み
    (`:149-155`)。「聞かない」に直す（D3 の第一適用例）。
  - GitLab ユーザーには `security_policy` / `scorecard` を聞いておいて
    `security_policy_effective` / `scorecard_effective` (`questions/_internal.yml:14-21`)
    が `git_platform == 'github.com'` でゼロ化する。micropython の sphinx→zensical
    書き換えは `_tasks` が警告するのに（`copier.yml:102-113` は「無音 override 2 件」と
    宣言）、これは警告なし。同種の失敗なのに扱いが非対称。3 件目として警告タスクに加える。
  - micropython / online_judge / ros2 でも `include_sentry` が聞こえ
    （`use_recommended_integrations` `questions/_common_b.yml:207` に when 無し）、
    Yes だと **参照するコードが一切ない** sentry-sdk 依存（`_shared/pyproject-deps.toml.jinja:1`）
    と `.env.example` だけが生成される（init site は pkg 木の `__main__.py` のみで、
    pkg 木は micropython/oj/web_api では存在しない、ros2 では `!= 'ros2'` ゲート）。
    when に型ガードを足す。

  → **完了（2026-09-17）**: (i) layout は script で聞かない（除外リストへ追加、ピンテスト更新）。(ii) GitLab × security_policy / scorecard は copier.yml `_tasks` の第 3 の WARNING で可視化（既存ピンは substring のため無傷）。(iii) include_sentry は `library / cli / script / data_science かつ not include_web_api` のときだけ聞く（pkg 木の親ゲートの手同期鏡。実レンダで根拠確認）。副次で when_model の `not in` トークナイズバグを修正
### 28.2 検証アーキテクチャ — 自分の定めた予算の未強制（節24 の実装漏れ）

- [x] **2a. 30s 予算が散文のまま。台帳はすでに超過している**:
  `pyproject.toml:67-70` が fast tier の予算 30s を宣言し、`tests/matrix/tiers.json` の
  test-fast 実測は **30.7s**（2026-09-16 測定）で既に超過。`tests/test_marker_drift.py`
  は鮮度 (`test_no_recorded_cost_is_stale` :935) と収集集合の一致しか見ず、
  `wall_seconds <= budget` の比較がどこにも無い（機械強制は葉数の `LEAF_BUDGET`
  :1010 のみ）。tier モデルが守るために存在する唯一の数字が、唯一何も落とさない数字。
  tiers.json に budget を載せ、超過で fail させる。
  → **完了（2026-09-17）**: tiers.json に `budget_seconds`（optional。test-fast = 30）を導入し、`test_no_recorded_cost_exceeds_its_budget` が超過で fail。UPDATE_TIERS が budget を保存する往復も実証。現行実測 27.5s（warm 22s）で予算内
- [x] **2b. 超過の原因は example 10 モジュールが render cache を経由しないこと**:
  `.cache/renders/` を使うのは 6 モジュールのみ。example 系は `copy_project` を直接叩き、
  `tests/test_example_web_api.py` は同一組合せ (`web_api`, `docker=True`) を同一モジュール内
  で 2 回 render (`:110`, `:213`)、`tests/test_example_docs_ci.py` は copy_project 言及
  41 行。**編集ループごとに ~140 回のフル copier render が発生しており、これが 30.7s の
  正体。** cache 経由化すれば予算は実際に買って戻せる（→ D5）。
  → **完了（2026-09-17）**: example 10 モジュール + test_recommended_path を render cache 経由に。タスクは copier 本家 `Worker._execute_tasks` のリプレイで、stderr 警告ピンは warm hit でも毎回成立（LICENSES コピーも再現、byte-identical 実証）。単発比較: 直レンダ 1.27s vs cache+replay 0.08s。test-fast 30.7s → 27.5s
- [x] **2c. Taskfile test-fast の式に `not network` が無い**: `Taskfile.yml:31-35` は
  `not heavy and not slow and not meta`。network 単独のテスト（uvx プローブ等。
  現状は全て heavy との組合せなので latent）が marker ガードをすり抜けて編集ループに
  混入し得る。desc の「network に触れない」と式を一致させ、test_marker_drift の
  タスク式検査で固定する。
  → **完了（2026-09-17）**: test-fast / test-randomly の式に `and not network`。Taskfile・pyproject コメント・ci.yml コメント・docs の式引用も追随し、台帳の式 / command / 収集集合を再記録
- [x] **2d. render cache の指紋に copier / jinja2 の版が無い**: `tests/render_cache.py`
  の invalidation は copier.yml + questions/*.yml + template パス集合 + 消費 template
  バイトのみ。renovate が copier を bump しても template バイトが変わらない限り
  昇級前の render を提供し続ける。実行環境の版を指紋に加える。
  → **完了（2026-09-17）**: ネームスペース指紋に CACHE_SCHEME タグ + copier / jinja2 のインストール版を追加（`_dist_version` 経由で monkeypatch 可能）。版差でネームスペースが変わるテスト付き
- [x] **2e. 動的 include が消費集合に入らない**: `_include_graph` は静的 quoted
  ターゲットのみ追跡（曖昧・動的は `_resolve_include_target` が None）。動的 include や
  変数経由の macro は編集しても stale hit の可能性。文書化された限界にするか、
  動的 include を禁止する構造検査を足す。
  → **完了（2026-09-17）**: test_machine_gate に Jinja-AST の動的 include 検出 + PROBE テスト + 実木ゼロ件検査を追加。副次発見: cache の INCLUDE_TAG は `{% from "x" import y %}` も追跡できない（ピン済み。cache が追跡を学んだら緩める）
- [x] **2f. 「1 render」の意味論が 2 つ**: cache 経路は `skip_tasks=True`
  (`tests/render_cache.py:347`)、`tests/support.py` の `copy_project` は tasks を実行
  （`_tasks_pre` 警告のピン用に `copy_project_capturing_stderr` が意図的に分離）。
  `tests/test_example_ros2.py:44` は task 生成物（uv.lock）に依存するので違いは現在
  意味を持つが、assert 側がどちらの意味論か宣言していない。経路を移すと無音に意味が
  変わる。→ D5 で単一入口に寄せる。

  → **完了（2026-09-17）**: render の意味論は copy_project 系の `run_tasks: bool`（既定 True = タスク付き）で明示。cache は純粋レンダのみ保存しタスク生成物はキャッシュしない方針を support.py の docstring に明記
### 28.3 tools 層 — 単一源の「コメント同期」の再発

- **3a. 質問票ローダーが 2 つ・非互換**: `tools/questionnaire.py:153`（`!include` を
  自己解決する `Question` dataclass 版）と `tools/when_model.py:63`（copier 本家
  `load_template_config` + dict/order）の両方が「唯一のローダー」を名乗り、
  `tools/predicates.py` は同一関数内で両方を呼んで和解（`_questionnaire_records` :143 と
  `when_model.load_questions` :268）。→ 28.6 D2。
- [x] **3b. 「唯一の render 呼び出し規約」(`tools/batch.py:423` の `render`) が 2 箇所で
  迂回**: `tools/cli.py:105` と `tools/update_rehearsal.py` (`:179` run_copy / `:260`
  run_update / `:302` run_copy) は batch.render に `defaults` / `skip_tasks` のノブが
  無いから直接 copier を叩く。ノブを足せば統合できる。update_rehearsal が git
  init+commit を自作 (`:246-257`) している点も `batch._git_snapshot` (`:406`) と重複。
  → **完了（2026-09-17）**: batch.render に defaults / skip_tasks ノブを追加し、cli._render と update_rehearsal の copier 直呼び 3 箇所を統合（run_update は別動詞として 2 箇所公認）。git init+commit は batch.git_snapshot に一本化。tests/test_render_convention.py（AST 走査 + 公認レジストリ、双方向 stale-proof）で恒久化
- [x] **3c. コメントで同期しているだけのペア**: context キー (`tools/answers_for.py:217`
  vs `tools/render_delta.py:136`。既に scheme タグの有無で乖離) / witnesses.jsonl の
  手パース (`render_delta.py:124` と `update_rehearsal.py:91` は schema 検証なし。
  `batch.load_requests` は key・重複 id・dest を検証) / answers スタンプ正規化 3 実装
  (`render_delta.py:353` / `update_rehearsal.py:124` / `mcp_server.py:372`。正規化の
  挙動も不一致。第 4 のスタンプは 3 箇所編集)。`tools/render_inputs.py` は「digest の
  drift 防止」のために存在するのに `render_delta.py:78-79` はそれを import せず
  同名定数を再宣言。
  → **完了（2026-09-18、R3）**: context キーは render_inputs.context_fingerprint に 1 実装（scheme タグ込み。answers_for.context_key は委譲）。witnesses.jsonl は render_delta / update_rehearsal とも batch.load_requests 経由（schema 検証付き）。スタンプは batch.RENDER_STAMPS + strip_render_stamps（比較用）/ mask_render_stamps（diff 表示用）に一本化（第 4 のスタンプは 1 行編集）。watched パス一覧・include グラフ・出力名規則も render_inputs に集約し render_delta と tests/render_cache.py の再宣言を撤去。副次で dir-symlink 中身（template/.vscode 等のリンク先バイト）が cache の消費集合に入っていなかった穴を塞ぎ（CACHE_SCHEME v3 に bvm、一度だけ全再レンダ）、build_state の _read_leaves 二重呼びも解消
- [x] **3d. 条件式の第 3 の綴り**: `tools/gen_docs.py:72` の `CONDITION_PROSE` は `when`
  を文字列テーブルとして第三箇所に再実装（docstring は「条件が変わったら loud
  failure」と言うが、意味による照合は無い）。マッチャも生 substring (`_mentions` :116)
  と word-boundary regex (`_mentions_project_type` :122) が混在。
  `tools/question_graph.py:170-172` の `when_model.jinja_identifiers` 再利用が正解。
  predicates の分類器は「既存 internal と同値」だけを指摘し、同じ述語の無名反復は
  report-only なので、この類（28.4-2 の agent scaffold 述語等）は Z3 側から見えない。
  → **完了（2026-09-18、R5）**: condition() は when_model.tokenize_when で解析してから prose を機械生成する方式に書き換え（project_type 比較は選択肢列、他比較は `var` = value、bool は BOOL_PROSE 4 件 + has_* パターン、or は ` / `、and は ` + `）。表は綴りではなく識別子（意味）でキーし、同値書き換えは同じ文を吐き、未対応の形だけ loud failure。_mentions / _mentions_project_type も when_model.jinja_identifiers 経由に統一（生 substring マッチャ廃止）。docs は ros2+pixi 行の文言がより正確に変化（生成 block を再生成）。
- [x] **3e. mcp_server の ~130 行重複**: `run_witness` (`tools/mcp_server.py:683`) と
  `run_tests` (`:758`) は同一 ~60 行 ×2（pytest argv 組立・timeout 付き subprocess・
  key-for-key で同一の payload・junit 判定・tail）。`_junit_verdicts` (`:648`) と ruff
  呼び出し (`:499`) は batch の領域 (`Check`/`LineResult`) の生成が frontend に住んで
  いる。`run_batch` (`:308`) は `batch.run_requests` の `--jobs` 機構を使わず serial。
  → **完了（2026-09-18、R4）**: 共通本体を mcp_server._run_pytest_tier に統合（run_witness / run_tests は各 ~10 行の委譲に）。_junit_verdicts は batch.junit_verdicts、ruff 機構は batch.ruff_bin / batch.ruff_checks に移設（Check/LineResult の生成が drivers 層に住む）。run_batch は batch.run_requests に jobs 引数で直結。
- [x] **3f. 小物の重複**: 質問名スキャン regex (`tools/adopt.py:94` vs
  `tools/detect.py:508`) / tolerant YAML loader (`tools/detect.py:517` の
  `TolerantLoader` vs `tools/questionnaire.py:63` の `_Loader`) / `_JINJA_OPERATORS`
  (`tools/predicates.py:99` vs `tools/question_graph.py:86`) / git wrapper 5 種
  （batch.git・detect._git・update_rehearsal._git・check_questionnaire_diff._git・
  check_upstream_fork.run。`GIT = shutil.which("git") or "git"` も 3 箇所）/
  sys.path bootstrap 11 箇所（`when_model.py:59` だけ `.absolute()` で他は `.resolve()`）。

  → **完了（2026-09-17）**: 質問名 regex → detect.QUESTION_LINE / tolerant loader → questionnaire.TolerantLoader / _JINJA_OPERATORS → when_model.JINJA_OPERATORS（question_graph は if/else 加算の派生を理由付き保持）/ git wrapper → tools/git.py 新設（test_tool_layers と template-dev.md の層表に宣言。check_questionnaire_diff・check_upstream_fork は standalone 層ゆえ分離を文書化）/ sys.path bootstrap の .absolute() 逸脱を .resolve() に統一（grep 0 件）
### 28.4 template payload — 派生フラグに載せ替えると消えるもの

- [x] **4a. ros2 の排除が 3 機械**: pkg 木の親ゲートは oj/micropython/web_api のみ除外し、
  木の中の 3 ファイル（`__init__.py` / `logging_setup.py` / `__main__.py`）が個別に
  `{% if project_type != 'ros2' %}` を持ち、ros2 本体は別専用木から来る。pkg 木
  14 ファイルは ros2 で全歩き・零出力。親に `pkg_scaffold` 派生（ros2 も除外）を 1 本
  足して内側のゲートを撤去する。
  → **完了（2026-09-17、R1）**: pkg_scaffold 派生を親ゲートに 1 本、内側の `{% if project_type != 'ros2' %}` 3 件を撤去（byte-identical）
- [x] **4b. 名前のない述語が 6+ 箇所に反復**: `not use_recommended_agent and
  project_type in ['library', 'cli']` が、pkg 木内 `agent.py` ゲート、`tools/` 2 パス、
  `prompts/`、`_shared/pyproject-deps.toml.jinja:1`、`README.md.jinja:656`、
  `pyproject.toml.jinja:168` に散在。§18 が `oj_bare` / `no_pkg` で排除したはずの
  パターンの再発で、`agent_scaffold` 相当の派生が無いことが原因（→ R1）。
  → **完了（2026-09-17、R1）**: agent_scaffold 派生で 9 サイト（path 7 + 本文 2）を統一
- [x] **4c. mega-OR のバイト等価重複と raw/effective 混在**:
  `{% if web_api or mcp_effective or scraping_effective or include_sentry or bot_effective
  or (not use_recommended_agent and project_type in ['library', 'cli']) %}`
  （~130 字）が `.env.example` のファイル名と `README.md.jinja:656` の本文で重複し、
  raw (`include_sentry`) と effective（他 5 つ）が混在。`needs_env_example` 派生に（→ R1）。
  → **完了（2026-09-17、R1）**: needs_env_example 派生に統合（.env.example のファイル名 + README 本文）。include_sentry は leaf 規則どおり raw のまま参照
- [x] **4d. 同一比較の 3 綴り**: `git_platform=="github.com"`（スペースなし、~21 パス）vs
  `git_platform == 'gitlab.com'` vs `ci_provider == 'github_actions'`。`is_github` /
  `is_gitlab` 派生で統一する（`security_policy_effective` の github ガードと同型）。
  → **完了（2026-09-17、R1）**: is_github / is_gitlab 派生で統一（security_policy_effective / scorecard_effective も is_github に載せ替え）。`ci_provider == 'github_actions'` は別述語（github + CI none で分裂する自由空間がある）として残置を決定
- [x] **4e. 長い親条件が子パスに埋め込まれる**: docs 木 13 パス / tests 木 14 パスが
  同一の親条件を path に繰り返す（copier の命名規約上、子が親条件を path に含むのは
  不可避。派生フラグ `render_docs` / `tests_scaffold` にすれば各パスが短くなり、
  ポリシー変更点が 1 箇所になる。tests 木と pkg 木の除外リストが黙って異なる
  （oj/web_api vs ros2_pkg）ことも、名前が付くと review 可能になる）。
  → **完了（2026-09-17、R1）**: tests_scaffold / render_docs 派生で tests 木 15 パス・docs 木 17 パスの親条件を 1 行に集約（子の葉条件は不変）
- [x] **4f. 親子の二重書き**: pkg 木内 `bot_*_effective and not web_api` ×3 /
  `mcp_effective and not web_api` は親が保証済み、app 木側 `and web_api` ×4 も同様。
  `data/queries/example.sql.jinja` は同一フラグ 3 連続。`prompts/` は親の
  adopt-protect 節を再掲し `tools/` は省略（意味的に同じ状況で慣習が 2 つ）。
  → **完了（2026-09-18）**: copier は path セグメントごとに独立 Jinja で親セグメントが空なら部分木ごと skip するため「最初のセグメントが条件を所有・子は素」で統一。pkg 木 4 + app 木 4 ファイルの親保証済み句を撤去、example.sql + queries/README の同一フラグ 3 連を最初のセグメント 1 つに集約（slash 越え単一 if は不可を copier 実装で確認）、prompts_scaffold 派生を新設して prompts/ と tools/ の慣習を一本化、micropython freeze.py も同慣習に。228 葉レンダでバイト同一を 2 回実証。
- [x] **4g. Dockerfile.jinja が無条件**: micropython でも uv 前提の Dockerfile が生成、
  ros2+docker では uv 版と `Dockerfile.ros2` の両方が落ちる。devcontainer 用スタブ等の
  意図をヘッダで宣言するか、条件化する。
  → **完了（2026-09-18）**: 判定は「意図ヘッダ」（バイト同一）。根拠: (1) devcontainer は全型で ../Dockerfile をビルドするので micropython でも load-bearing、(2) 監査時の「micropython に uv 版が落ちる」前提は既に不成立（uv/pixi ステージは {% if docker %} 内で docker は micropython に聞かれない。実レンダは 8 行の developer ステージのみ）、(3) ros2+docker の両落ちきは test_example_ros2 がピンする意図的構成。template/Dockerfile.jinja 冒頭に render で剥がれる {#- -#} コメントで宣言。
- [x] **4h. kaggle src 木が data_science src 木と重複**: `data/.gitkeep` /
  `features/.gitkeep` / `models/.gitkeep` がバイト等価（kaggle は
  configs/input/logs/notebook/output/scripts を追加）。一元化の方針を決める。
  → **完了（2026-09-18）**: 方針「派生フラグに統合」。`ds_stack = data_science_layout or kaggle` を新設し、3 つの .gitkeep は `{% if ds_stack %}src{% endif %}/` 配下の 1 箇所に。Z3 分類器が指摘した同述語の本文 7 箇所（pyproject.toml + _shared/pyproject-deps/deptry）も `{% if ds_stack %}` 参照に置換（R1 の「全同値を実参照に」の再適用）。228 葉レンダでバイト同一。
- [x] **4i. symlink 慣習が docs に無い**: template 内 13 symlink（workflows 8、
  devcontainer、vscode、pages、gitleaks、tests/conftest）は「ルートに実体・生成物へ
  symlink」の dogfooding だが、説明は TODO.md:871/:1332 と `.python-version` symlink
  撤退の経緯（TODO.md:834-835、ros2 pin 破壊）のみ。`docs/explanations/structure.md` に
  慣習と一覧を書く。
  → **完了（2026-09-17）**: docs/explanations/structure.md に symlink 慣習（ルートに実体・生成物へリンクの 13 件一覧表）と「content-identical なファイルだけ link できる」の .python-version 撤退経緯を記載
- [x] **4j. 本文での配置再導出**: `_shared/pyproject-deps.toml.jinja:1` の
  `{% if not web_api %}"fastapi"...{% endif %}` は、配置側（`app/bot_line.py` vs
  `<pkg>/bot_line.py`）が既に表現した web_api 分岐の再導出。
  → **完了（2026-09-18）**: 3 箇所（deps の fastapi/uvicorn と httpx、pyproject 本文の httpx）とも `pkg_scaffold`（pkg 木配置フラグ）参照に置換。fresh 葉空間では同値（witness fast 全走査で確認）で、adopt-protect で pkg 木が保護された場合に旧綴りが依存だけ残す不具合が偶発的に解消。

### 28.5 リファクタリング候補（振る舞いを保つ。各 1 PR を想定）

- [x] **R1 派生フラグの新設**: `agent_scaffold`（4b） / `needs_env_example`（4c） /
  `is_github` / `is_gitlab`（4d） / `pkg_scaffold` / `tests_scaffold` / `render_docs`
  （4a/4e）。各 1 本で複数パスが短くなり、ポリシーの変更点が `_internal.yml` の 1 行に
  集まる。追従は `test_predicate_classifier` の DECLARED_EQUIVALENCES 更新と
  ファイル名条件の置換のみ。
  → **完了（2026-09-17）**: 7 派生（is_github / is_gitlab / agent_scaffold / needs_env_example / pkg_scaffold / tests_scaffold / render_docs）を _internal.yml に新設し ~44 サイトを置換。DECLARED_EQUIVALENCES は変更ゼロ（全同値が実参照になった）。228 葉全走査でコンテンツ差分ゼロ（残差は ask-surface 変更による .copier-answers.yml の記録キーのみ）。初手の極性ミス（not agent_scaffold）は render twin が ros2 / script 葉で検出し修正済み
- [x] **R2 batch.render にノブ**: `defaults` / `skip_tasks` を足し、`cli._render` と
  `update_rehearsal` の 3 直呼びを統合（3b）。「1 つの render 規約」を物理的に唯一にする。
  → **完了（2026-09-17）**: 3b と同一作業として着地（上記参照）
- [x] **R3 単一源の復帰**: context キーの tools 化（scheme タグ込みで 1 実装） /
  witnesses.jsonl は `batch.load_requests` に統一 / answers スタンプ正規化を 1 実装に /
  `render_delta` を `render_inputs` 経由に（3c）。
  → **完了（2026-09-18）**: 3c と同一作業として着地（上記参照）。合わせて 2f の「全テスト render」最終確認も決着: 残っていた直 render 7 モジュールのうち、machine_gate の render matrix / data_science / micropython_maintenance / generated_typecheck / witness_matrix._render_leaf を cache 経由に寄せ（witness_matrix 用に support.render_answers を新設）、例外 5 モジュール（render_cache 本体 / test_detect の skip_if_exists / test_example_adopt の git clone / test_example_docs_ci の validator 拒否 / test_generation_docs と test_update_path の vcs_ref・update が主題）は test_render_convention.py の SANCTIONED_TEST_MODULES に理由付きで宣言し、両方向 stale-proof で恒久化
- [x] **R4 mcp_server の整理**: `run_pytest_tier()` で witness/tests を統合、verdict 機構
  （junit・ruff）を batch へ、support.yml 読み込みを foundations へ、`run_batch` に
  `--jobs`（3e）。
  → **完了（2026-09-18）**: 3e と同一作業で着地（上記参照）。support.yml 読み込みは新設の tools/support_ledger.py（foundations 層、test_tool_layers と template-dev.md の層表に宣言）に集約し、gen_docs はその上のブロック結合に専念。
- [x] **R5 gen_docs の分離**: support.yml 半分の独立モジュール化、`CONDITION_PROSE` の
  照合を `when_model.jinja_identifiers` 経由に（3d）、mermaid レイアウトの
  `gates[:2]` ハードコード（`gen_docs.py:818` 位置）の一般化。
  → **完了（2026-09-18）**: support.yml 半分は tools/support_ledger.py に分離（load_support / matrix_rows / cell / render_support_table / render_support_doc。gen_docs と mcp_server の template://support と test_support_matrix が使う）。3d は上記のとおり。gates[:2] は _head_split() に一般化（「最初の project_type 分岐が gate の後ろに来る境界」を ask 順から導出。現行質問票では gates[:2] と同一出力を docs --check で実証）。
- [x] **R6 adopt.py の詰め**: merge サブシステム（plan/merge/prompt 系 ~350 行）の
  分離候補、`_confirm_merges` 経由の 2 回目の fresh render（1 実行で最大 3 render）を
  1 キャッシュに、merge summary 2 実装（`_merge_summary_from` :1221 /
  `_merge_summary` :1243）の統合。
  → **完了（2026-09-18）**: merge summary は _merge_summary_from に統合（_merge_summary は plan 形へ詰め替える 4 行アダプタ、ピンテスト付き）。fresh render は _finish_with_merges で 1 度だけレンダして _confirm_merges と merge_generated_files に回す（対話実行 3→2 render、batch.render 呼び数を数えるピンテスト付き、自動/dry-run は不変）。merge サブシステムの分離は「採用しない」と決着: トランザクションの書き込み相（_Run.backup 記録と _undo_run ロールバック引き金）と不可分で、切り出すと循環 import 必至。理由を adopt.py のセクションコメントに記録。
- [x] **R7 render_cache の掃除**: `render()` の lock 前の死んだ hit 評価
  （`tests/render_cache.py:332` vs `:336`。同一式の 2 度評価で warm hit でも
  `_inputs_current` の全再ハッシュが 1 回余分に走る）の除去、fixture 再 import
  ボイラープレート（6 モジュール × 5 行）の「conftest に移してはいけない」制約を
  テスト化。
  → **完了（2026-09-17）**: render() の lock 前の死んだ hit 評価を除去（warm hit の全再ハッシュ 1 回分を削減）。「conftest に置けない」制約を AST import 走査テスト（test_render_helpers_stay_out_of_conftest）で機械化
- [x] **R8 leaf 表現の Protocol 化**: `batch.Request` / `z3_witnesses.Leaf` / raw dict
  （render_delta・update_rehearsal の手パース） / `answers_for._Recorded` の 4 表現に
  `id`/`answers` の Protocol を定義し、`predicates.leaf_contexts(leaves: list[Any])`
  を型で閉じる（3c の手パース統合と同時にやると相性が良い）。
  → **完了（2026-09-18）**: predicates.LeafLike Protocol（読み取り専用 property の id/answers。frozen dataclass も受理させるため read-only）を定義し、leaf_contexts / evaluate / _classification_tree / _shortcut_suggestions / report / json_report を Sequence[LeafLike] で閉じた。z3_witnesses.Leaf と batch.Request は構造的に適合（zero change）、raw dict は R3 で消滅、_Recorded は docstring で契約を明記。
- [x] **R9 answers の迂回解消**: `test_recommended_path.py:40` の `BASE = answers.BASE`
  再 export を 15 モジュールが読んでいる（support.py は直 import 済み）。直 import へ。
  インライン answers dict（`tests/test_example_adopt.py:116` の
  `author_email: kasi-x@example.com` 等）は `test_answer_fixtures` の未知質問・
  未知 choice 検査の対象外なので、検査に乗せるか `BASE` 派生に寄せる。

  → **完了（2026-09-17）**: BASE 再 export を 12 モジュールの直 import 化（test_recommended_path はローカル使用のみで re-export 廃止）。インライン answers 8 箇所を宣言レジストリ方式で test_answer_fixtures の検査に編入（未知質問・選択肢外はゼロ件を実証）
### 28.6 設計変更候補（決め事。節10 の原則に照らして判断する）

- [x] **D1 レイヤー可用性行列の宣言**: 「どのレイヤーがどの base に載れるか」を
  tests/matrix/（または support.yml の拡張）に機械可読で宣言し、when ガードと双方向
  照合する。節10 の「増やしたい要求は必ず『既存の何の上に載るか』を答えてから設計」の
  自然な完成形で、1c（未宣言の非対称）と 1b（include_bot の穴）の恒久対策。
  理由が書けない行は「理由を書ける形に直す」か「撤去」に決着させる。
  → **完了（2026-09-18）**: tests/matrix/layers.yml を新設（include / bases / extras / rides / revealed_by / 必須の why。excluded セクションで include_sentry も会計に編入し、include_* の増減が宣言なしで起きない両方向 stale-proof）。tests/test_layer_matrix.py の 4 テストで双方向照合（matrix→when は copier 本体の Worker._ask で実評価、when→matrix は when_model.jinja_identifiers の識別子集合一致）。監査の説明不能な非対称 3 件は when 変更なしで理由を書いて決着（kaggle×web_api 可・data_science 層不可 = 「ジャンルではなく非重複」、data_science に bot/mcp/scraping が出ない = 常駐ホスト前提、scraping の cli 専用 = プロジェクト全体の ruff banned-api という whole-program 政策）。
- [x] **D2 質問票ドメインモデルの一本化**: `when_model`（copier 本家 loader）を唯一の
  パーサにし、`questionnaire.py` をその上の dataclass ラッパに寄せる（or 逆）。
  predicates の二重呼びと 2 表現問題を消す。影響は tools 全体なので D1/R 群より後で
  単独 PR。
  → **完了（2026-09-18）**: 判定は「or 逆」— questionnaire.py を唯一のパーサにする（Question.source 来歴は copier の merge では失われるため、dataclass 版がより豊か）。questionnaire は _read_entries に 1 パス化して load_questions（dataclass API・シグネチャ不変）と新規 load_raw_questions（when_model の旧契約そのまま）の 2 射影を提供、when_model.load_questions は委譲のみに（copier の load_template_config は tests の差分オラクル専用に降格、機械ゲートのピンは存置）。predicates の二重呼びは「1 パーサ・2 射影」として正当化をコメントに記録して保持（source が必要なサイト表と生 details が必要な internals は片方からは作れない）。等価ピン test_raw_view_agrees_with_copiers_loader を追加。
- [x] **D3 無音破棄の方針**: 「render 時に捨てる回答は必ず警告（`_tasks` stderr）するか、
  そもそも聞かない」をルール化し、1d の 3 件に適用する。layout は when に script を足す
  （聞かない）、sentry は when に型ガード、security_policy / scorecard は警告タスク
  追加、がそれぞれ素直な帰結。
  → **完了（2026-09-17）**: 「render 時に捨てる回答は警告するか、そもそも聞かない」を template-dev.md に規約化し、1d の 3 件に適用済み
- [x] **D4 予算の機械化と台帳駆動 docs**: tiers.json に budget を載せ、
  test_marker_drift が超過で fail、docs の tier 表は gen_docs が台帳から生成する
  （T5 の延長線上）。30.7s 超過の決着は「予算を上げる」ではなく 2b の cache 経由化で
  30s に戻すのが筋（節24 の「拡大は L2 に寄せる」の再適用）。
  → **完了（2026-09-18）**: 前半（budget_seconds + 超過 fail）は 2a として 2026-09-17 着地済み。後半: verification.md に tier-ledger 生成 block を新設（gen_docs が tests/matrix/tiers.json から selector / collected / budget / measured を生成。数字は台帳が唯一の源、役割の散文は手書きのまま）。
- [x] **D5 render の単一入口**: 全テスト render を render_cache 経由にし、tasks 実行の
  有無を引数で明示する。`support.py` は「tasks を実行する render」の名前を持つラッパに
  なり、2f の意味論問題と 2b の予算超過を同時に決着させる。
  → **完了（2026-09-17、第一適用）**: テスト側の全 render を render_cache 経由の単一入口に寄せ、タスク実行は `run_tasks` 引数で明示（2f の意味論問題と 2b の予算超過を同時決着）。tools 側の呼び出しも batch.render に統一（R2）
- [x] **D6 ファイル名条件の所有権ルール**: 「分岐は親ディレクトリ名が所有。子は親の
  述語を言い直さない。path に埋め込む場合は派生フラグで書く」を template-dev.md に
  明文化し、4f の二重書きを整流する。

  → **完了（2026-09-17、文書）**: 「分岐は親ディレクトリ名が所有。子は親の述語を言い直さない。path に埋め込む場合は派生フラグで書く」を template-dev.md に明文化。R1 の 7 派生がその実践
### 28.7 着手順（提案）

1. **予算回りの一日セット**: 2a（budget 強制）+ 2c（`not network`）+ 2d（指紋に版）を
   先に fixed にしてから、2b（example の cache 経由化 = D5 の第一適用）で 30.7s を
   30s 未満に戻し、台帳を再収集する。
2. **乖離の決着**: 1a（文書を include 順ルールに書き直す）+ 1b（include_bot）+
   1d（無音破棄 3 件）。ここで D1/D3 の方針を確定する。
3. **R1 派生フラグ**（4b/4c/4d/4a/4e を一掃）→ 1a と同じ PR に載せられる。
4. **R2/R3/R4（単一源の回帰）** → D2 は R 群の実測を見てから着手する。
   → **2026-09-17**: 手順 1〜3 に加えて手順 4 の R2 も着地（2a/2b/2c/2d → 1a/1b/1d + 1b ピン → R1 → R2/R7/R9/3f）。
     検証は全ゲート緑（lint / type-check 5種 / test-fast 27.5s < 予算30s / test 963 passed / 台帳10検査）。
   → **2026-09-18**: R3 + 3c 着地、2f の「全テスト render」最終確認も決着（R3 の完了注記参照）。
   → **2026-09-18（続き）**: 手順 4 の残り（R4/R5 + 3d/3e）と R6/R8、payload の 4f/4g/4h/4j、D4 の台帳駆動 docs を一括着地。新規 foundations モジュール tools/support_ledger.py と派生 2 本（prompts_scaffold / ds_stack）、ピンテスト複数（merge summary / render 回数 / test 側 render 規約）。
     検証は各項目ごとに lint / type-check 5種 / 関連 pytest（R6: adopt 系 106 passed、4f-4h: 228 葉バイト同一 2 回 + test-fast 907 passed、R8: basedpyright 0、D4: docs sync 14 passed）。
   → **2026-09-18（最終）**: D1 / D2 を着地し §28 は完結。新規レジストリ tests/matrix/layers.yml（D1）と tests/test_layer_matrix.py、questionnaire 一本化の等価ピン（D2）。監査 §28 はこれで全 41 項目（1a-1d / 2a-2f / 3a-3f / 4a-4j / R1-R9 / D1-D6）が決着。


---

<!-- 旧 TODO.md L545–L596 -->
## §30 完了: `.gitignore` 末尾改行と root `.gitignore` 同期の修正（2026-09-23）

> **2026-09-23 着地**。サブエージェント `FixGitignoreTrailingNewline` が Jinja 空白制御のみで解決。

### 30.1 発見

`task test-fast` で 23 件の失敗が出ていた。すべて `.gitignore` 関連:
- `tests/test_generated_lint.py::test_generated_files_end_with_single_newline[...]` が
  `.gitignore: trailing blank line(s)` で失敗。
- `tests/test_example_library_cli.py::test_gitignore_same` が root `.gitignore` に
  `test/` / `.kattisrc` が欠けていると失敗。
- `tests/test_update_rehearsal.py::test_the_rehearsal_of_head_replays_cleanly` が
  `.gitignore:117: new blank line at EOF` で失敗。

### 30.2 原因

1. `template/.gitignore.jinja` の最後で `_shared/gitignore-{ctf,oj,scraping,gmail}.jinja`
   を `{% include %}` していたが、include ファイルの `{% endif %}` の後の改行が
   累積し、条件が true の組合せで末尾に余分な改行が生じていた。
2. `_shared/gitignore-oj.jinja` は `oj_code` 条件で `test/` / `.kattisrc` を
   レンダーするが、root `.gitignore` には同じエントリが欠けていた。

### 30.3 既に適用した変更

- `.gitignore`: OJ エントリ `test/` / `.kattisrc` を追加（`test_gitignore_same` を緑化）。
- `template/{% if not existing_project or 'gitignore' not in adopt_protect %}.gitignore{% endif %}.jinja`:
  `.test.db` の後の改行を削除し、コメント・include 行を 1 行にまとめ、
  ファイル末尾の改行も削除。これにより条件 false の組合せでは末尾が `\n` になった。
- `_shared/gitignore-oj.jinja`: ネストされた `.kattisrc` 分岐の改行を整理。

### 30.4 着地内容

サブエージェント `FixGitignoreTrailingNewline` が Jinja 空白制御だけで解決。
Copier 9.18.1 は `keep_trailing_newline=True` なので、Jinja ソースが出す改行が
そのまま生成ファイルの末尾になる。

- `_shared/gitignore-{ctf,oj,scraping,gmail}.jinja` の最終 `{% endif %}` を
  `{%- endif %}` に変更し、条件 false のとき include 自身が空改行を出さないように。
- `_shared/gitignore-oj.jinja` のネストされた `.kattisrc` 分岐も
  `{%- if oj_kind == 'kattis' %}` / `{%- endif %}` にし、EOF 改行を除去。
- `template/.gitignore.jinja` は既存の変更（`.test.db` 後改行削除・include 行 1 行化・
  末尾改行削除）を維持。
- root `.gitignore` は `test/` / `.kattisrc` 追加済みのまま。
- `CHANGELOG.md` [Unreleased] → Bug Fixes に 1 行追加。

### 30.5 検証結果

- `rm -rf .cache/renders && uv run --locked pytest -q tests/test_generated_lint.py::test_generated_files_end_with_single_newline tests/test_example_library_cli.py::test_gitignore_same tests/test_update_rehearsal.py::test_the_rehearsal_of_head_replays_cleanly` → 28 passed。
- `rm -rf .cache/renders && uv run --locked pytest -q -m 'not heavy and not slow and not meta and not network'` → 1023 passed, 5 skipped, 1 xfailed, 0 failed。
- すべての条件分岐（all-false / ctf / oj-atcoder / oj-kattis / scraping / gmail / ctf+oj）で
  `.gitignore` の末尾がちょうど 1 つの `\n` で終わることを直接確認済み。


---

<!-- 旧 TODO.md L597–L708 -->
## §31 完了: CI 赤 2 件の解消と upstream drift レビュー（2026-09-23）

### 31.1 Scheduled full check の startup_failure（3 週連続）

- 症状: 2026-09-08 / 09-15 / 09-22 の週次 run がすべて `startup_failure`
  （ジョブ 0 個で即死）。actionlint は clean、YAML も valid。
- 原因: `scheduled-check.yml` が `_docs.yml` を呼ぶ際に caller 側の
  `permissions` を付けていなかった。`_docs.yml` の build ジョブは
  `contents: write`（gh-pages publish 用）を宣言しており、reusable
  workflow の permissions は caller の grant を超えられない
  （GitHub 仕様: downgrade のみ可）ため、run 作成時点で全体が拒否される。
  `ci.yml` の docs 呼び出しは `contents: write` を渡しているので緑だった。
- 修正: `scheduled-check.yml` の docs ジョブに `permissions: contents: write`
  を追加（`publish: false` は維持 — grant は天井を満たすだけで publish は
  しない）。workflow_dispatch で実走確認: lint/test/docs の 3 ジョブが
  起動し startup_failure を脱した（run 35812055877）。

### 31.2 Check upstream fork の failure = 設計どおりの drift 通知

- upstream (DiamondLightSource) に未レビュー 5 コミット。exit 1 + issue
  自動起票は仕様。レビュー結果を issue #2 に記録して close:
  - a0cc77c / 9de143b / 4e8d917: upstream uv.lock 保守 — こちらの lockfile は
    独立（renovate 管理）。対応不要。
  - 18db87c: setup-uv v10.0.1→v10.1.0 — こちらは SHA pin + renovate が
    digest 追随するので対応不要。
  - 72da24d: 生成 ci.yml に `merge_group:` 追加 — **採用**。生成物が
    merge queue を後から有効化しても CI が発火するようになる
    （queue 未使用なら no-op。tag-gated release 系は queue ref が branch
    なので発火しない）。template ci.yml.jinja に適用済み。

### 31.3 付随作業

- `.zcode/`（エージェント plan キャッシュ）を root + template の
  `.gitignore` に追加（test_gitignore_same の parity 規則で両側必須）。
- 5 コミットを push（e60b45f8..928d6810）。§B の「生成物 CI 初回実走確認」
  は push 後 run 観察が条件 — 今回の push run がその観察対象。

### 31.4 週次チェック復活後に表面化した実バグ 2 件（同 2026-09-23 着地）

startup_failure を直した途端、週次チェックが本来の仕事（ドリフト検出）をした:

- **`test_update_from_the_released_ref_to_head`**: vendored `clean.scss` の
  4 行に行末空白があり、update 差分が `git diff --check` に引っかかった。
  行末空白を除去（同ファイルは EOF 改行ですでに vendored-modified 済み）。
- **`test_the_full_rehearsal_passes_on_every_leaf`**: リハーサルは各葉を
  **リリース時点の質問票**で描画するが、葉の回答は HEAD 由来 —
  `oj_kind=codeforces` 等（6.0.0 後に追加）の葉が `Invalid choice` で
  プール全体を crash させていた。base ref で描画不能な葉は「その葉を持つ
  ユーザーは存在しない」ので `[SKIP]` として報告し、coverage には数える
  （`rehearsed + skipped >= ledger total` の assertion に更新）。
- 検証: `--only codeforces` で 8 葉すべて SKIP、rehearsal suite 4 件 pass、
  update-path 該当テスト pass、fast tier 1023 pass。


### 31.5 検証完了（2026-09-23）

- 復活させた週次チェックがさらに 2 件の潜伏バグを表面化し、すべて解消:
  - `test_each_tier_collects_what_the_ledger_records`: 新設した
    trailing-whitespace パラメタ化が fast tier に 26 件追加 →
    `UPDATE_TIERS=1` で tiers.json 再記録 + gen_docs で
    verification.md / test-loop.md の件数同期。
  - rehearsal の `OSError: Directory not empty: '.git'`: copier の
    run_update が TemporaryDirectory cleanup で git の .git 書き込みと
    競合する一過性レース（並列 worker 下）。`_rehearse_job` に 1 回の
    リトライを追加。
  - ついでに `ruff format` の 2-blank-line 違反 1 件（lint ジョブが捕捉）。
- 最終 run 35817016824: **lint / test / docs 全緑**（test は heavy 込みの
  全 tier、23 分）。drift-issue ジョブは正しく skipped。
- 新設テスト `test_generated_files_have_no_trailing_whitespace` が
  pyproject.toml.jinja / README.md.jinja / .gitleaks.toml / shortcodes.lua
  の行末空白を一掃（.scss を suffix 集合に追加 — vendored clean.scss は
  従来の EOF チェックの盲点だった）。

### 31.6 Periodic linkcheck の赤も解消（2026-09-24）

週次 linkcheck（Periodic、水曜 08:00）も 6 件の死リンクで赤だった:

- `duty.readthedocs.io` → `pawamoy.github.io/duty`（docs が RTD から移転。
  生成ブロックなので tools/gen_docs.py の RUNNER_URLS を修正）
- `zens.python.dev` → `zensical.org`（改名）
- `mikemahoney218/arxiv` → `quarto-arxiv`（リポジトリ改名。
  docs + 生成 README の両方）
- `kasi-x/python3-pip-skeleton`（削除済み）と `kasi-x/dotfiles`
  （private）→ リンクを外し、名前だけ残す
- `prefix.dev/robostack-{{ ros_distro }}`: Jinja プレースホルダが生成 docs
  にそのまま出て 404。prose はチャネル名パターン表記に、ros2 how-to は
  具体の `robostack-jazzy` に。pixi.toml.jinja のプレースホルダは生成物で
  正しく展開されるので無関係。
- 検証: workflow_dispatch で Periodic 緑（run 35892182109）。
  update-rehearsal も dispatch で緑（run 35892333419: 248 葉 rehearsed、
  新 oj_kind 24 葉は [SKIP] 報告どおり）。これで全スケジュール
  workflow が健全: scheduled-check / periodic / rehearsal / witness /
  dependency-audit / check-upstream すべて緑。

### 31.7 upstream-fork チェックの恒久赤を構造修正（2026-09-24）

- 症状: `check-upstream-fork` が 3 週連続で赤。原因は設計: 比較が
  `HEAD..FETCH_HEAD` で、fork は意図的に分岐しているため upstream コミットは
  永遠にマージされず、レビュー済みコミットが毎週再発火していた
  （アラートの習慣的無視 = 最悪の状態）。
- 修正: `.upstream-fork-reviewed`（最後にレビューした upstream SHA の
  1 行ファイル）を導入し、checker は marker..FETCH_HEAD の差分だけを報告。
  marker が upstream/main の祖先でない場合（force-push / 誤記）も明示的に
  失敗。レビュー後は `echo <sha> > .upstream-fork-reviewed && git commit`。
- marker は 4e8d9171 で seed（5 件は issue #2 でレビュー・採用済み）。
  dispatch で緑確認（run 35899201430）。
- 併せて issue #1 の mcp floor drift を解消: `mcp[cli]>=2.0` → `>=2.0.1`
  （PyPI に 2.0.0 final が存在せず floor が空集合を指していた）。
- これで全スケジュール workflow が緑: scheduled-check / periodic /
  update-rehearsal / witness / dependency-audit / check-upstream /
  check-upstream-fork。


---

<!-- 旧 TODO.md L709–L739 -->
## §32 完了: preset 実レンダ検証・list_presets・notes 整理・_tasks.yml timeout（2026-10-01）

- **preset の render 検証**: presets/*.yml は従来 `tools/cli.py` のロード
  経路（`test_cli.py`）だけで検証され、生成時の `Invalid choice` や
  `when` による family drop は未検知だった。`tests/test_presets.py` を
  新設し、`cli.available_presets()` で列挙した全 preset を
  `copy_project_recommended`（= `cli.new --preset` と同じ answers 構成:
  BASE + preset + copier 既定）で実レンダし、family sentinel
  （web-api→app/main.py、ros2→package.xml、micropython→firmware/main.py、
  data-science→src/<pkg>、oj 3 件は bare workspace なので README 内の
  judge ドメイン）を assert。センチネル未登録の新 preset は
  `pytest.fail` で即検出（test_every_preset_has_a_sentinel）。
- **`list_presets` MCP ツール**: `tools/mcp_server.py` に追加
  （`cli.available_presets()`/`preset_answers()` の再利用、filesystem
  only）。`docs/how-to/mcp-tools.md` のツール表に行を追加。
  TOOL_NAMES + 内容ピンテスト（test_mcp_server.py）。
- **notes/ 整理**: 全項目解決済みのバグ台帳 3 件（BUG.md /
  BUGS_AND_IMPROVEMENTS.md / bugs.md）を `notes/archive/` へ移動。
  生存ドキュメント（SPEC-adoption / PLAN-improvements / Strategy /
  COPIER_UPSTREAM / upstream-drafts）は notes/ 直下に残す。
  docs/ からの notes/ 参照は生存ファイルのみで切れ目なし。
- **`_tasks.yml` に `timeout-minutes: 15`**: 全 workflow で唯一 timeout
  未設定だった reusable workflow。root と生成物側は symlink 同一ファイル
  のため 1 箇所の編集で両方に効く（_test.yml は input 化、_dist/_docs
  /_example は 15-20min 固定、という既存のばらつきは据え置き — _tasks は
  lint 実行のみなので固定 15 で十分）。
- 検証: test_presets 10件・test_mcp_server 関連3件・test_workflow_security
  + test_cli + test_marker_drift 36件パス。UPDATE_TIERS で台帳再記録
  （test-fast 1069→1080, test 1147, test-randomly 1080）と
  docs/how-to/test-loop.md の tier 表が再生成済み。


---

<!-- 旧 TODO.md L740–L773 -->
## §33 完了: region セクションの distribution チャネル — `ethics/regions.yml`（2026-10-01）

§29-B の「質問を増やさず地域ルールを届ける」合意を実装。

- **判定**: `region-jp-external-transmission` / `region-eu-eaa` はともに
  `web` audience だが、昇格ルール（同条件 3 件 or 独自ゲート必須の 1 件）
  を満たさず、裸の `web_api` include は過剰配布（内部 API にフロントエンド
  法務を届ける）。よってセクション昇格ではなく**参照テーブル方式**:
  `template/{% if web_api %}ethics{% endif %}/regions.yml` を新設し、
  各ルールの `serves:` が registry draft のセクションファイルを指す
  （要約 + duties + 一次ソースのみ同梱、本文は配布しない）。
- **AGENTS.md ポインタ**: `web_api` ゲート付きの段落を ethics appendix
  末尾に追加し `ethics/regions.yml` を指す。draft 隔離
  （test_draft_sections_are_not_distributed）は `serves:` 参照を
  exempt として維持 — 配布（本文取り込み）と参照（パス指名）を
  字句で区別。
- **ピン**: invariants.yml — `layout=web_api` に `ships: ethics/regions.yml`
  と `[AGENTS.md, regions.yml]` content ペア、非 web 行
  （library/cli/script/ros2/micropython/oj_kind=code/ctf）に absent。
  `project_type=online_judge` 行への absent は kaggle+include_web_api
  葉と衝突するため oj_kind 行に限定。witnesses.jsonl は
  `task witness`（z3_witnesses.py --jsonl）で再生成済み。
- **契約テスト**: test_ethics_registry.py に
  `test_regions_table_serves_registered_drafts` — serves が登録済み
  region セクションを指すこと、review_by が対象行の最早日に一致する
  こと、AGENTS.md がテーブルを指すことを固定。
- **runbook**: docs/how-to/ethics-section.md に「Market-triggered rules:
  the regions table」節を追加（§29-B の方式文書化）。
- 検証: web_api 実レンダで ethics/regions.yml + AGENTS ポインタあり、
  library/online_judge はなし。ethics_registry 11件・invariants/レイヤ
  行列・witness 不変条件・example 系 346件パス。UPDATE_TIERS + gen_docs
  再記録済み（test-fast 1080→1081）。



---

<!-- 旧 TODO.md L774–L798 -->
## §34 完了: ethics appendix の生成化 + gate 単一綴り（2026-10-01）

- **`_shared/ethics-appendix.jinja` をコミット済み生成物化**:
  `tools/gen_ethics_appendix.py` が REGISTRY.yml の `status`+`gate` から
  include チェーンを生成。AGENTS.md.jinja は include 1 行のみ。
  `gate` が「どの葉が節を持つか」の唯一の綴り — テスト側述語は
  `tools/ethics.py` の制限 AST eval（`gate_holds`）で同じ文字列を評価。
  test_render_invariants.py の手書き λ 表と私的 `_OJ_CODE_KINDS` を解消。
- **invariants.yml の per-row AGENTS.md content pin 23 件除去** —
  述語が同一主張をするので重複だった。
- **FLAGS.yml の `gate:` 列を削除** — registry への重複スペルで
  未検査だった列。外部契約は `audience` 写像のみに一本化。
- **contract ガード追加**（test_ethics_registry.py）: 配布行の `gate` 必須、
  全 gate の AST-lint + 配布 gate の leaf-context 束縛チェック、生成物の
  `--check` 鮮度ピン。prose 形状アサート（本文の scale/audience 記述）は
  codex 側 content QA に移す方針で本ファイルから除去
  （notes/upstream-drafts/11 参照）。
- **batch runner に `expect.agents_md`** — registry id で節の有無をピン。
  smoke.jsonl 7 リクエストに適用済み。
- **upstream-drafts 追加**: 11（codex content QA suite）、
  12（codex regions-table spec）。CONTRIBUTING に ethics 境界節を追加。
- 検証: 対象 pytest 551 件 + smoke batch 8/8（update 行含む）・
  ruff/basedpyright/typos クリーン。UPDATE_TIERS で台帳再記録
  （test-fast 1081→1082）。


---

<!-- 旧 TODO.md L1067–L1109 -->
## §38 展開: 法務エコシステムの ConstitutiveTemplates 組織への分離（2026-10-04）

§37 の拡大戦略に基づき、法律・コンプライアンス層をこのリポジトリから組織レベルの
専門リポジトリへ分離した。法律自体の「整理（オントロジー化）」は追従不能な
規模になるため、単独のリポジトリとして育てる。

- **`open-law`（公開済み）**: 世界中の公式立法ソース（uk, jp, eu, kr, bd,
  np, la）の Polite スクレイパー。`kasi-x/open-law` から
  `ConstitutiveTemplates/open-law` へ移管・初期公開。Akoma Ntoso 対応の
  統一 Law モデル + トピック対応表（correspond）。
- **`law-map`（新規作成）**: 機能的等価（Zweigert & Kötz）に基づく
  機械可読の「義務グラフ」。条文・判例・ガイダンスを 1 つの義務ノードに
  束ね、`review_by` による鮮度管理と `law-map check` によるドリフト監視。
  3 つのシード: PIIログ禁止・SBOM義務・AI学習データ利用。
- **`good-future-codex`**: 人間・AI向け散文セクション。`law-map` の
  `related_sections` が逆リンクし、「義務 → 散文 → vendored スナップショット」
  の上流を形成。
- **このリポジトリ**: `docs/explanations/ethics-external.md` を更新し、
  外部リポジトリが「設計メモ」から「実在のパイプライン」になったことを記録。
  `_shared/ethics/` は引き続き vendored スナップショットとして残る。

### 残作業（このリポジトリ側）— 2026-10-04 全項目着地
- [x] `_shared/ethics/` → `good-future-codex` への vendor sync ワークフロー:
  `tools/check_ethics_drift.py` + `.ethics-vendored` marker + 週次
  `.github/workflows/ethics-sync.yml`（drift で issue 起票）が既に実装済みだった
- [x] `law-map` の `related_sections` ↔ codex `sections/` 命名規則の一致検査:
  `<tier>-<slug>` → `sections/<tier>/<slug>.md.jinja` の解約規則を
  law-map 側に実装（`law-map validate|check --codex <checkout>`、未解決は error。
  law-map の ci.yml で codex を checkout して検査。law-map README に規則を明記）
- [x] `law-map check` の `scheduled-check.yml` 組み込み: 週次 job
  `law-map-review-by` を追加（law-map + good-future-codex を checkout し
  `uv run law-map check --codex` を実行、期限切れで赤＋issue 起票）。
  ethics-sync.yml との重複なし — 対象 corpus が異なる（散文 SHA ドリフト vs
  義務ノードの review_by 鮮度）。`docs/explanations/ethics-external.md` に
  2 つの契約（vendored SHA / `<tier>-<slug>` 命名規則）を記録
- [x] **初回 drift report の解消（2026-10-06）**: law-map#2（8 URL フラグ）と
  good-future-codex#1（ilga.gov exit 60）を修正・close。ilga.gov はデータセンター
  egress を TLS reset するため Wayback スナップショットへ、soumu 外部送信規律・
  CISA CVD・cryptrec・dsgvo-gesetz（TTDSG→TDDDG 改称）・PCI・RFC 9116 は
  移転先/正規 URL へ、fsfe.org の Sitecom 判決ページ（404）は ifrOSS の英訳 PDF へ。
  `law-map check --sources` 34 probes / 0 flagged、codex `--drift` all live。
  codex @42008c58 の vendor sync は PR #20（ヘッダのみ・本文 byte 同一）


---

<!-- 旧 TODO.md L1110–L1175 -->
## §39 実行: `foundry` → `daimonion` への改名（2026-10-05 決定）

**決定**: プロジェクト名を `daimonion` に変更する。`foundry` は PyPI で取得済み
（`uvx foundry` 不可）、かつ Ethereum の Foundry / Palantir Foundry と検索衝突するため。
org 名 `ConstitutiveTemplates` は変えない。

**由来（README / vision.md に書く物語）**: ソクラテスの daimonion は「何をせよ」とは
言わず、過ちの手前で「やめよ」とだけ告げる内なる声。ethics セクションの警告・
対象外構成の abort・Z3 検証による不正状態の拒否・AGENTS.md の禁止事項と対応する。
Unix の *daemon*（常駐して見張る CI）の語源でもある。
キャッチコピー案: *Like Socrates' daimonion, it never tells you what to build — only when to stop.*

**空き状況（2026-10-05 実測）**: PyPI `daimonion` 空き、npm 空き、GitHub 同名は
★0 の無関係リポのみ（約 10 件）、`daimonion.dev` は DNS 応答なし（未取得の可能性）。
`.com` / `.io` / `.org` は取得済み。商標調査は未実施。

却下した候補と理由（再検討を防ぐため）: `underpin`（PyPI 取得済み・2023 で放置、
PEP 541 要）、`uphold`（同名の暗号資産企業 Uphold が GitHub org で SDK 公開・商標）、
`halo`（PyPI のスピナー lib ★3k・halo-dev ★40k・Microsoft 商標）、`monty`
（PyPI 取得済み・pydantic/monty ★8.5k）、`monthy`（monthly/monty の誤字に見える）、
`trueup`（同思想の TS ツールあり）、`buttress` / `preshaved` / `gloriole`（空きだが不採用）。

### 39.1 エージェント作業（リポジトリ内。push 前に `task check` 緑を確認）

- [x] 識別子の改名: `pyproject.toml` の `name` / `[project.scripts]` のコマンド名
      （`daimonion = "tools.cli:main"`）/ deptry の `DEP003=foundry`、
      `tools/cli.py` の `prog=` と docstring、`uv.lock` 再生成（`uv lock`）
- [x] CLI キャッシュディレクトリ `~/.cache/foundry` → `~/.cache/daimonion`
      （旧ディレクトリは読まずに放置でよい。再 clone で済む。決定を cli.py の
      コメントに残す）
- [x] URL の置換: `ConstitutiveTemplates/foundry` → `ConstitutiveTemplates/daimonion`、
      `constitutivetemplates.github.io/foundry` → `.../daimonion`、
      `foundry-example` → `daimonion-example`。対象（`git grep -il foundry` で
      74 ファイル / 266 箇所、2026-10-05 時点）: README.md, zensical.toml,
      CITATION.cff, codemeta.json, NOTICE, SECURITY.md, REUSE.toml, support.yml,
      renovate.json, .mcp.json, example-answers.yml, copier.yml, questions/,
      .github/（ISSUE_TEMPLATE / workflows）, template/（生成物に入る URL・
      バッジ — **生成プロジェクトに出る文字列なので render テストの期待値も更新**）,
      docs/, tools/, tests/, copier-fork/scripts/
- [x] 残すもの（置換しない）: CHANGELOG.md・`notes/archive/`・`notes/upstream-drafts/`
      ・TODO.md の過去節など**履歴記録**の `foundry` / `python-copier-template`。
      README と NOTICE に "formerly *foundry*, originally *python-copier-template*" を明記
- [x] `notes/outreach/` の下書き（記事・ニュースレター・demo.tape・awesome リスト文面）
      を新名称で書き直し、由来の一文を足す
- [x] `docs/explanations/vision.md` に名前の由来節を追加（上の物語）
- [x] 検証: `task check`、`task regen`（生成 docs / 葉に名前が入る場合）、
      `git grep -i foundry` の残りがすべて「残すもの」に該当することを目視確認

### 39.2 人間作業（HUMAN_TODO.md に転記済み）

- PyPI `daimonion` の確保（0.0.0 プレースホルダ。`PYPI_API_TOKEN` 未設定）
- GitHub リポ名変更 `foundry` → `daimonion`、`foundry-example` → `daimonion-example`
  （GitHub が旧 URL をリダイレクトするので既存 copier プロジェクトは即死しないが、
  39.1 の URL 置換は 39.2 のリネームと同じ日に merge する）
- Pages の URL 変更確認、`daimonion.dev` 取得判断

### 39.3 リリース番号の注意（改名リリースと同時に処理）

copier は **PEP 440 で最大のタグ**を採用する。既存タグ `6.1.0` が残る限り
`v1.0.0` は永久に選ばれない（HUMAN_TODO の「v1.0.0 リリース」はこの点で破綻）。
旧タグ削除は既存プロジェクトの `copier update`（`_commit`）を壊すので不可。
→ 改名後の最初のリリースは **`7.0.0`**（"first release as daimonion"）とし、
GitHub の "Latest" 表示も 7.0.0 にする（2026-10-05 時点で Latest は 6.0.0、
6.1.0 は現行質問票を含まず `uvx copier copy` が古い内容を展開している）。
`docs/explanations/vision.md` の「pre-1.0」表記も 7.x と矛盾しないよう直す。


---

<!-- 旧 TODO.md L1211–L1273 -->
## §41 検討: ConstitutiveTemplates エコシステム横断の改善点（2026-10-09 レビュー）

4 リポ（open-law → law-map → good-future-codex → daimonion）を横断で見た指摘。
§38（分離）/ §40（メンテ体制）と重複しないもののみ。優先順。人間作業の
PyPI 確保・`GITLEAKS_LICENSE`・push protection は `HUMAN_TODO.md` 側で追跡する。

### A. エコシステム設計

- [x] **open-law → law-map の実連携**: ✅ 2026-10-11 着地。
      `schemas/obligation.schema.yml` + model/check/cli に任意フィールド
      `open_law: {source, id}` を追加（source は open-law の source_id、
      id は source ネイティブの law_id — 実 API のみ経由、発明 API なし）。
      6 grounding に seed（JP APPI/著作権法、EU GDPR/DSM、UK CDPA）。
      drift-watch は `--sources` 内で `probe_open_law()` を併走
      （amended/unavailable/unreachable/skipped、sha256 で本文 pin、
      open-law 未導入なら skip）。workflow は best-effort install。
- [x] **4 リポ通しの E2E nightly**: ✅ 2026-10-11 着地。
      `.github/workflows/e2e-ecosystem.yml`（週次 + dispatch）:
      law-map export + `validate --codex` → codex `tools/validate.py` →
      daimonion `new --preset web-api --ref HEAD` → AGENTS.md に active
      ethics 節を assert。失敗時 drift-issue。全 action SHA pin、
      `contents: read` + job `issues: write`、timeout 30。
- [x] **ethics vendoring の遅延確認**: ✅ 2026-10-11 確認+同期。
      機制は正常（drift は issue #27 起票済み）。codex 側で
      `domain/prompt-injection` の Python 例を ruff 両幅対応に修正
      （codex 1ecbcd9、push 済み）→ vendor を 1ecbcd98ac に更新。
      drift CLEAN、contract 18/10/18、registry 12 passed、draft 隔離維持。
- [x] **ライセンス不統一の扱いを決める**: ✅ 2026-10-11 統一。
      open-law を Apache-2.0 に統一（LICENSE 差替・pyproject `license`・
      README バッジ/節・CHARTER/justfile の MIT 言及を更新）。
- [x] **組織の入口を作る**: ✅ 2026-10-11。org profile README は
      エコシステム図+役割表を既に持つが旧名 `foundry` のままだった →
      `daimonion` に全置換（図・表・pipeline 記述）。

### B. リポ別

- [x] **daimonion: support 降格基準**: ✅ 2026-10-11。`support.yml` に
      `demotion:` 節（3 つの機械的トリガー: オーナー不在 / 実行実績なし /
      rehearsal 対象外 — 各に証拠源・降格方向・復帰経路）を追加。
      prose-only 追加で gen_docs --check と MCP/template 読みは無傷。
- [x] **daimonion: ローカル残骸の掃除**: ✅ 2026-10-11。
      `o.log` / `e.log` / `cov.xml` / 両 egg-info を削除。`.gitignore` は
      既存エントリで既に覆われていたため変更不要（test_gitignore_same 緑）。
- [x] **open-law: README のテンプレ残り**: ✅ 2026-10-11。
      copier 由来の NOTE ブロック（starting point / placeholder）を除去。
- [x] **open-law: law-map が引用する法域を優先対応**: 2026-10-11 調査の上
      **adapter 不採用**と決着。CA leginfo は Cloudflare 403・bulk zip は
      セッション単位 1.1G、TX は SPA（robots が SPA シェル）、IL は
      タイムアウト、govinfo は key-gated。セカンダリソース（LII 等）は
      charter の official-source 規約に反するため見送り。連邦 eCFR は
      既存 `us` adapter で網羅済み。CA/CCPA grounding は URL のまま維持し、
      leginfo に key-free API が出たら再検討。
- [x] **law-map: codex との逆方向カバレッジ**: ✅ 2026-10-11。
      `validate --codex` が「obligation に参照されない codex 節」を
      warning 出力（error ではない）。実走: 9 obligations vs 18 節で
      6 warning（domain-contest-rules / ml-bias / prompt-injection /
      region-eu-eaa / region-kyushu-ntp / sector-samd-regulatory）。
- [x] **good-future-codex: sources の死活監視**: ✅ 2026-10-11。
      `tools/validate.py --sources` で全 sources URL（MANIFEST + 節 header
      + body links + lang/*.yml）を curl probe（10s、retry 2、命名 UA、
      HEAD→405 時 GET、301 終端は報告のみ）。drift-watch.yml に組込み、
      ci/justfile/README/CONTRIBUTING 追随。tests 11 passed。


---

<!-- 旧 TODO.md L1274–L1325 -->
## §42 構想: 生成後のライフサイクルまで支える「信頼できる足場」（2026-10-11）

§28–41 の検証基盤・普及策・組織横断連携とは別に、利用者が生成した後の
体験を伸ばす候補。いずれも未決定の構想で、現行の「推奨1本 + No でカスタム」
原則や Python テンプレートの守備範囲を崩さずに価値を広げる。

### A. 利用者プロジェクトの更新を安全な継続運用へ

- [x] **利用者側の自動更新 PR**: ✅ 2026-10-11 着地。
  `template/{% if is_github %}.github{% endif %}/{% if ci_provider ==
  'github_actions' %}workflows{% endif %}/template-update.yml.jinja` を新設
  （週次 + dispatch）。opt-in は repo variable `TEMPLATE_UPDATE=1`（未設定なら
  早期成功終了）— 質問追加ゼロで葉空間 272 不変。`daimonion/update-<ref>`
  ブランチで `copier update` を試行し gh CLI で PR 作成（contents:write +
  pull-requests:write の最小権限、conflict はブランチ保持+PR 本文記載で
  緑のまま、自動 merge なし）。invariants の common ships + witnesses
  再生成 + README.jinja の update 節追記。
- [x] **生成物の「構成契約」マニフェスト**: ✅ 2026-10-11 着地。
  `.daimonion-manifest.yml`（無条件生成、schema 1）: template_ref（=
  .copier-answers.yml の _commit と一致検査）+ answers_file ポインタ +
  active ethics 節の id+version 一覧（`_shared/contract-manifest-sections.
  yml.jinja` — gen_ethics_appendix の gate と同じ源、active のみ）。
  回答値は一切含まない公開契約。`daimonion verify <dir> [--against <dir>]`
  で schema/ref/差分を検査（tools/verify.py）。stamp 正規化は batch/
  render_delta/update_rehearsal/mcp の 4 経路に編入。tests 8 件。
  272 葉不変（manifest のみ expect 追加）。

### B. 質問票を「要件から構成を導く」体験へ

- [x] **制約付き構成アシスタント**: ✅ 2026-10-11 着地。
  `tools/suggest.py`（questionnaire_schema / validate_answers /
  suggest_presets）+ CLI `daimonion suggest "…" [--validate file] [--json]`
  + MCP `suggest_config` / `validate_answers`。モデル非依存の決定的
  スコアリング（requirements → preset マッチ）と、提案回答を既存機械検証
  （未知質問・選択肢外・未到達 when）で拒否する受け口。LLM は MCP
  クライアント側に委ね、通常 CLI/質問票は不変。tests 15 件。
- [x] **回答理由と代替案の説明**: ✅ 2026-10-11 着地。
  `tools/explain.py` + CLI `daimonion explain [--preset X | question value
  | --deviate question value]` + MCP `explain_choice`。説明は support.yml・
  質問票 help/choices/when・preset description を単一源として導出
  （新しい選択肢・別サポート表なし）。deviate は when 依存と derived
  defaults・support tier を列挙。tests 19 件、docs how-to 新設。

### C. 適用対象を拡張する際の境界

- [x] **テンプレートを越える「構成的信頼」方式の再利用可能性を評価**: ✅
  2026-10-11 着地（評価として）。`docs/explanations/cross-language-contract.md`
  に 3 機構（Z3 構成検証 / registry 配布 / drift 検知）を Python 結合と
  言語非依存契約に分解し、共通カーネル（葉代数・列挙・配布・監査証跡）と
  小さな独立プロトタイプの成功条件（3 件）を記録。別言語テンプレートの
  提案は成功条件を満たした場合のみという境界を明文化。


---

<!-- 旧 TODO.md L1377–L1434 -->
## §44 完了: エコシステム横断の改善 wave（2026-10-12、8 エージェント並列実装）

scout 4 本による現行コード調査で特定した改善を、リポ別 8 エージェントに分割して実装。
完了確認は各エージェントの報告 + 親による統合検証(lint/type/test/validate/test-fast/regen)で実施。

### daimonion
- template: `installation.md.jinja` を `package_manager` 分岐(uv/poetry/pixi)に、
  `README.md.jinja` runner 表を strictness 対応 + First-run ブロック追加、
  `_internal.yml` に `is_uv/is_poetry/is_pixi/runner_just/runner_task/strictness_minimal`
  派生を新設し反復リテラル 52 箇所(uv x16, poetry x9, pixi x6, runner x14, strictness x7)
  を置換 — 10 構成で byte-identical を確認。
- workflow: `audit.yml.jinja` 新規(週次 SUN 04:00 + dispatch、task_runner_effective 経由)。
- `_hygiene.yml`: gitleaks self-skip 時に `::notice::` を明示。
- `ci.yml.jinja`: required-checks 失敗時に CONTRIBUTING blast-radius へのポインタを出力。
- Taskfile: `pipeline` タスク追加(upstream→downstream 最小検証)。
- `.github/workflows/org-profile-links.yml` 新設(週次 lychee、.github 公開 org profile)。
- `periodic.yml`: `patch-rot` job で copier-fork/patches の `git apply --check` を週次化。
- `tools/check_ethics_drift.py`: `vendored=<sha8> upstream=<sha8> age_days=<n>` サマリ行を追加。

### law-map
- workflow: ci/drift-watch を SHA pin + persist-credentials:false 化、
  drift-watch の top-level permissions を job へ移動、新規 security.yml+zizmor.yml。
- drift-watch grep を `skipped|amended|unreachable` に拡張。
- `check.py`/`cli.py`: open-law 未導入時の probe を `[skipped]` 行 + `skipped: N` サマリで可視化。
- `model.py`: `--warnings` に (a) `status:scheduled` かつ `effective` 過去、(b) `check_refs` 未接続、
  の 2 種を追加 — 実データの status 不整合 3 件(llm-appsec-baseline/ml-bias/ai-training-data-use
  の EU AI Act grounding)を `in_force` に修正。
- `export.py`: codex skeleton に `## Directives`(human/agent bullets + enforcement wiring)を出力。
- `justfile`: `pipeline` recipe。
- `obligations/`: L2 昇格 3 件(crypto/no-deprecated-algorithms、privacy/no-cleartext-pii-logging、
  ai/llm-appsec-baseline)に新規 spec 3 本(checks/{crypto,privacy,ai}/)、残り 6 件は明示 `L0`。
- dead source 2 件を修復(whitehouse.gov→bidenwhitehouse.archives.gov、nic.ad.jp→APRICOT 2017 PDF)。

### good-future-codex
- workflow: pin 確認 + persist-credentials 追加、drift-watch permissions を job 化、
  security.yml + zizmor.yml 新設。

### open-law
- adapters: `de`(gesetze-im-internet)と `us-tx`(Texas capitol/TCAS)を新規実装、
  `jp` を v1 lawdata(キー不要)で full-text 化。us-ca(Cloudflare 403)と ilga.gov(timeout)は
  憲章上ブロックとして `docs/explanations/jurisdiction-coverage.md` に記録。
  kr は `LAW_KR_OC` 登録必須を use-sources.md に明文化。ADAPTERS 10→12。
- core: `text_extract` に `preserve_structure`、fetcher に opt-in `wayback_fallback`
  (4xx 迂回禁止)、`--wayback` CLI フラグ、PDF opt-in(pypdf extra)、
  `tests/test_live.py`(`-m live`, `OPEN_LAW_LIVE=1` でのみ実行)、`fetch-budgets.md`。
- `.github/workflows/adapter-health.yml` 新設(週次、全 adapter の代表 probe → 1 issue 集約)。
- `_hygiene.yml`: gitleaks tarball に sha256 pin+検証。
- CONTRIBUTING/README: kasi-x 残骸を全除去 + blast-radius 表。

### .github-org
- org profile は公開済み(repo=ConstitutiveTemplates/.github)が判明、daimonion 側で週次 lychee 監視に接続。

### 検証
- law-map: validate 0 errors、`--warnings` は L0/spec-less の宣言的警告のみ、check --sources 0 flagged、84 passed。
- good-future-codex: validate 18 sections 0 warnings、12 passed、zizmor clean。
- open-law: 178 passed/12 skipped(live 層のみ)、ruff clean、YAML 全 parse、`sources` で 12 adapter 列挙。
- daimonion: test-fast 1153 passed(25.4s/30s 予算)、test-meta 10 passed、
  ruff/basedpyright clean、regen+gen_docs --check in sync。

---

