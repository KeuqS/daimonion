# TODO

> 2026-09-07: バグ台帳(BUG.md / bugs.md / BUGS_AND_IMPROVEMENTS.md)・
> Strategy.md・copier 本体への寄稿候補(COPIER_UPSTREAM.md / upstream-drafts/)は
> ルート整理のため `notes/` へ移動しました。本文中の言及は移動前のパス表記です。

このテンプレートの開発・拡張メモ。各項目は作業時に個別のissue/PRへ分割してよい。
未公開（pre-publication）のため、後方互換・移行案内・CHANGELOG は考慮しない。

## 設計原則（2026-09 合意・更新: AGENTS.md / online_judge / kaggle 再編を反映）

> 節1〜26 のチェックボックスは 2026-09-14 に実装ツリーと突き合わせて更新した履歴。現行の残作業は節27.7・節28 と各節の `- [ ]` を正とし、`- [x]` は記録であって現状の主張ではない。

以下の原則に従って、オプションの追加・削除・再編を判断する。原則に反する提案は
肥大化のもとなので、このTODOに載せる前に再考する。

- **project_type = 実行環境 / ビルドが根本から異なるもの、または「競技」という
  明確な利用規約の軸があるものだけ**
  - 例: library（import）、web_api（HTTP+Docker）、cli（即終了）、data_science、
    script、online_judge（競技。AI 利用の可否が大会ごとに異なる）、ros2（colcon/
    rosdep）、micropython（デバイス+firmware 特殊ビルド）。
- **実行環境が同じでも「AI 利用の可否」という規約の軸が明確なら project_type にできる**
  - online_judge は実行環境としては script/cli と同じだが、大会ごとに
    「AI コーディングエージェントの利用可否」が異なり、生成物に AGENTS.md を
    置く/置かないが変わる。これは実行環境軸とは独立した第一級の違い。
  - 逆に、実行環境も AI 規約も同じなら project_type を増やさない。
    CTF、botter（discord / slack / LINE / Gmail）、data_science の拡充、SRE、FastHTML 等は
    「既存 project_type の上に載るレイヤー / 亜種」として扱う。増やしたい要求は
    必ず「既存の何の上に載るか」を答えてから設計する。
- **AI コーディングエージェント向けの指示（AGENTS.md）は、デフォルトで全プロジェクトに置く**
  - library / cli / web_api / data_science / script / kaggle には常時生成。
  - AI 利用 NG の online_judge タイプには置かない（規約遵守のため）。
  - 個別の ON/OFF 質問は作らない（内蔵の初期構成とする）。
- **対象外の領域は web_django 方式で明示的に拒否する**
  - このテンプレートの守備範囲外（Ansible の IaC、Terraform/K8s、Django 等）は
    project_type の選択肢として「NOT supported。生成を abort して代替を案内」する。
    黙って無視する選択肢を増やさない。
- **選択肢は「推奨1本 + No でカスタム」を保つ**
  - 現行の `use_recommended_*` 方式。詳細な選択肢（ORM 5種、GraphQL/REST 等）を
    一度に並べるカタログ型（例: s3rius/FastAPI-template）にはしない。

## 前提: 現状の構造的問題（このTODOの動機）

- **AI コーディングエージェント向けの指示がどこにも無い**: 生成物に AGENTS.md が
  無く、AI エージェントが「どうテストを回し、どこを編集してよいか」を README /
  CONTRIBUTING.md から推測するしかない。CONTRIBUTING.md は人間向けの詳細版であり、
  エージェント向けの簡潔な作業手順が無い。
- **kaggle（competition）が data_science の亜種として誤って配置されている**:
  Kaggle は「競技」であり、AI 利用 OK という点で online_judge の一種。
  data_science（分析）と competition（競技）は実行のされ方が違い、GPU 前提の
  競技特化レイアウト（src/utils, submission）が data_science に混在している。

（web_api が scaffold として未完成だった問題と「生成物が動く検証テストが無い」問題は
2026-09 に解消済み。web_api はトップレベル app/ の動く scaffold になり、
test_example / test_generated_lint / test_recommended_path が生成物を実走・lint 検証する。
履歴は項目6 と「このセッションで解決した項目」に残してある）

## 1. AI コーディングエージェント向け指示（AGENTS.md）の生成

- [x] `AGENTS.md.jinja` を新設し、生成物の設定（task_runner / strictness / docs /
      project_type）に応じた開発フローを自動生成する
      - 内容: テスト・lint・type-check・docs の実行コマンド、編集してよい範囲
        （src/<pkg>/, tests/）、commit 規約（conventional）、CI の構成
      - 生成: library / cli / web_api / data_science / script / kaggle
        （online_judge の AI-NG タイプでは生成しない）
      - 配線: `agents_md_effective`（questions/_internal.yml）を新設し、ファイル名
        条件 `template/{% if agents_md_effective %}AGENTS.md{% endif %}.jinja` で
        生成有無を一元管理（mcp_effective / security_policy_effective と同型）
- [x] README.md.jinja に「See AGENTS.md for AI-agent guidance」を追記する
      （Development setup 付近。docs 生成時は docs にも反映）
- [x] .gitignore / renovate / pre-commit への影響を確認する
      （AGENTS.md は通常の md として扱い、typos / markdown lint / docs 取込の
      対象にするか決める）
      → 確認済み: 素の `.md` として扱う（末尾改行テストの対象に自動で入る）。
      typos は md を検査するが AGENTS.md 固有の除外は不要。docs 取込（index.md /
      sphinx conf）は README 側の既存リンクのみで AGENTS.md 自体は取込対象外。
- [x] CONTRIBUTING.md との住み分けを docs に明記する
      （AGENTS.md = エージェント向け簡潔版、CONTRIBUTING.md = 人間向け詳細版）
      → AGENTS.md.jinja 冒頭で CONTRIBUTING.md へのリンクを明記し住み分けを固定
- [x] AGENTS.md の有無を検証するテストを追加する
      （各 project_type と online_judge の AI 可否で、ファイルの有無が正しいこと）
      → tests/test_example.py に present/absent 4件を追加

## 2. online_judge project_type の新設（競技用。AI 可否は種類による）

- [x] copier.yml の project_type に `online_judge` を追加する
      - help: 競技用プロジェクト。種類（kaggle / atcoder / leetcode）により
        AI コーディングエージェント利用の可否が異なり、AGENTS.md の有無が変わる
      - 実装メモ: AI 可否と AGENTS.md 有無の配線は項目1（AGENTS.md）着手時に
        oj_allow_ai 質問として追加する（今回は質問・変数とも未導入）
- [x] `oj_kind` 質問を新設する（online_judge 選択時のみ）
      - kaggle / atcoder / leetcode の3種で開始し、**2026-09 に yukicoder / aoj を
        追加して5種**に拡張（oj 対応サイト + 教育的OJ優先の方針。ユーザー指示）
      - yukicoder / aoj は既存の oj_code（コード提出型・空ワークスペース）側に載せ、
        生成物の分岐変更なし。README の導入手順だけサイト別に切替:
        atcoder = oj + acc / yukicoder = oj（submit まで対応）/ aoj = aoj-cli 主軸
        （oj は AOJ に submit 不可）/ leetcode = LeetCode エディタ（oj 非対応）
      - atcoder / leetcode では AI 可否をさらに質問する（項目1 で追加予定）
- [x] `oj_allow_ai` 質問を新設する（atcoder / leetcode 選択時のみ）
      - AI 利用 OK → AGENTS.md を生成（+ README に AI 向け言及）
      - AI 利用 NG → AGENTS.md を生成しない（規約遵守）
      - 実装: questions/online_judge.yml に `oj_allow_ai`（bool, default false,
        when は online_judge かつ atcoder / leetcode）を追加
- [x] online_judge の生成物（最小構成・追加依存なし・stdlib のみ）
      - **設計変更（oj 実測ベース）**: solutions/ は事前生成しない。oj はカレントに
        `test/`（sample-N.in/.out）を作り、acc はコンテスト/問題ディレクトリを
        作るため、「空の作業リポジトリ」を生成し oj / atcoder-cli に全て任せる
      - atcoder/leetcode はルートが空（src/ も package も無い）。lint は競技向けに
        緩和（A001 / N802 / N806 / RUF059 / ARG / F841 / PLC0415 等を oj_code 全体に
        適用）、pytest は tests/ のみ、型チェックは vulture スキップ、CI は dist 無し
      - README に oj / acc の導入手順と提出フロー（oj download → main.py →
        oj test → oj submit）を記載
- [x] online_judge では `use_recommended_agent`（pydantic-ai scaffold）を出さない
      （online_judge では use_recommended_agent 質問自体が出ないことを確認）
- [x] online_judge のテスト: 生成物の有無（src 無し・deps 空・CI に dist 無し）+
      空ワークスペースで task check が通ること + kaggle に solutions が無いこと
- [x] **将来拡張（2026-09-22 着地）**: oj_kind に Codeforces / Kattis / other を追加し competitive_coding は 7 種に（atcoder / leetcode / yukicoder / aoj / codeforces / kattis / other）。codeforces = oj download+test（submit は可否次第）、kattis = submit.py + `.kattisrc` 主軸（oj は samples 読込のみ）、other = 汎用 stdin/stdout（oj が通るところだけ）。`oj_code` は 7 種に拡大、`oj_allow_ai` は atcoder / leetcode / codeforces / kattis / other に拡大（yukicoder / AOJ は check-the-rules のまま）。生成物は README サイト別手順 + Quick start 分岐、AGENTS.md の tooling 一行、`_shared/gitignore-oj.jinja`（`test/` + kattis のみ `.kattisrc`）、`oj_sample` 質問（oj_code 配下・既定 off）の dispatch-only な `oj-sample.yml`（pinned sample 1 問/週次・push CI と `check` は offline のまま）。witness は 248 → 272 葉、`oj_kind=code` 行と support.yml / tier_policy の judge 列挙を追随、`oj_sample` は include_sentry と同型の excluded question（per-site 本文は tests/test_example_oj.py が担保）。
- [x] **2段階化**: `oj_category` 3択（data_science / competitive_coding / ctf）を
      OJ 直後に新設し、`oj_kind` の選択肢をカテゴリごとに切替（kaggle のみ /
      atcoder・leetcode・yukicoder・aoj / ctf のみ）。`default` もカテゴリ連動
      - `oj_ctf` internal を新設（online_judge かつ oj_kind == 'ctf'）。`oj_code`
        はコード提出4種に狭め（CTF 除外：challenges＋tests＋ctf extra を持つため）
      - `ctf_effective` は `oj_ctf or (include_ctf and library/cli)` の2経路に
        拡張（library/cli レイヤーと OJ 所属で同形生成）。`use_src_layout` /
        `pkg_dir` / `agents_md_effective`（CTF は AI OK で常時生成）を対応
      - README / AGENTS.md に CTF 分岐を追加。tests/test_example.py に
        `test_template_oj_ctf_workspace` を追加し、既存 OJ テスト全件に
        `oj_category` を付与
## 3. kaggle の data_science 分離 → online_judge の内部タイプへ統合

- [x] copier.yml から data_science 配下の `competition` 質問を削除する
      （kaggle = oj_kind=='kaggle' として online_judge 側に移す）
- [x] 内部変数を張り替える: competition 条件を kaggle 条件に変更
      - data_science_layout / pkg_dir（'src/utils'）/ use_gpu_effective / duo / care /
        _tasks.jinja の competition 分岐 等
      - oj_code（= online_judge and oj_kind != 'kaggle'）内部変数も追加
- [x] kaggle 用の生成物を移設する（既存 competition のものをほぼそのまま）
      - src/{configs,data,input,output,features,logs,models,notebook,scripts,utils}/
      - utils パッケージ（config/dataset/features/modeling/plots）
      - Dockerfile.gpu + devcontainer.gpu.json + uv の pytorch-cu124 インデックス
      - marimo notebook（src/notebook/explore.py）
      - 依存セットはユーザー判断で「既存 competition を完全維持」（duckdb/polars/
        pyarrow と experiment extra も kaggle に残す）
- [x] data_science を純粋な分析型に純化する
      - competition / GPU 質問を外す（notebooks / data / models / reports / paper）
      - **DUO / CARE 質問は data_science に残す**（competition の when 条件を外す）
      - polars/duckdb/pyarrow 等の data_science 初期依存は維持する
- [x] kaggle には AGENTS.md を生成する（AI 利用 OK のため。kaggle 固有の指示:
      GPU の使い方・submission の作り方・データ境界を含める）
      - `agents_md_effective` が kaggle を常時 true にし、AGENTS.md.jinja の
        kaggle 分岐が input/output 境界と pipeline タスクを案内する
- [x] 既存テストを移設する: test_template_kaggle_competition → kaggle タイプ用に
      書き換え、test_template_data_science_layout は competition 無しの純化後仕様に
      更新。example-answers.yml / questionnaire.md / README の competition 言及を更新
      （未公開なので移行案内は不要。単に competition を撤去して kaggle に置き換える）

## 4. 「常駐する実行可能物」の実行形態を新設する（bot / MCP server の受け皿）

- [x] project_type に `daemon` / `service`（常駐実行物: bot、MCP server、長命 worker）を
      追加するか、既存 project_type の上に載るレイヤーとして独立起動モジュールを持つ
      設計にするか決定する → **既存の上に載るレイヤー方式** に決定
      - 判断基準は設計原則1（実行環境が根本から違うか）。bot/MCP は「イベントループ +
        トークン/env で起動する長命プロセス」だが、library / cli / web_api と同じ
        CPython + uv 実行環境に載る。マイクロPython（ビルド・実行対象が根本から
        違う）と違い、実行環境軸で project_type を増やす根拠が無い
      - 「cli / web_api の上に bot 実行モジュールを置く」レイヤーとして扱う
        （bot / MCP server は「ホストやイベントループに起動される実行可能物」であり、
        import される側の library には載せない）。**2026-09 に include_mcp を cli 限定へ
        変更**（web_api は top-level app/ 化で <pkg> を無くし、mcp_server.py の置き場が
        消えたため。常駐レイヤーの実装例は cli + include_mcp のみになった）。
        既存の `include_mcp`（cli 上に mcp_server.py + `mcp-server-<name>` console
        script を生成して常駐起動する）がこのレイヤーの実装例
- [x] `__main__.py` を「常駐起動（トークン必須、環境変数チェック）」に置き換える分岐を
      設計する（CLI と衝突させない） → **独立起動モジュール方式** に決定
      - `__main__.py`（CLI: `python -m <pkg>` / `scripts.<name>`）は即終了コマンドの
        まま維持し、常駐物は別モジュール（例: mcp_server.py）の `main()` を
        `python -m <pkg>.mcp_server` で起動する
      - 理由: `__main__.py` にトークン必須・env チェックの分岐を足すと、Docker の
        ENTRYPOINT（`scripts.<name>` = CLI）や既存テスト（`python -m <pkg> --version`）
        と衝突する。常駐物ごとに独立モジュール + 専用 `[project.scripts]` を持つ方が
        CLI / 常駐の二重起動を構造的に防げる
- [x] **botter 向け（discord / slack / LINE / Gmail）: 常駐レイヤーの platform として
      実装する**（2026-09-08 方針確定: bot も実装する。project_type は増やさない）
      → **第一スライス着地（2026-09-14、734844aa + bbaa98e0 + b275e98b + 17d2a8f3）**:
        `include_bot` / `use_recommended_bot` / `bot_platform`（選択肢は discord のみ。
        slack / LINE / Gmail は help に計画として記載、実装は「1つずつ潰す」方針どおり次の
        スライス）。`bot_effective` / `bot_discord_effective`、`_shared/bot-discord.py.jinja`
        （build_bot/main 分離、`DISCORD_BOT_TOKEN` 起動拒否、logging_setup 統合、
        bot-discord-<name> エントリポイント、bot-serve タスク）、ラッパ3配置、
        生成テスト（fake interaction の ping/pong + 拒否）、docs 一式、check_upstream ピン。
        葉空間 205 → 225（旧205葉は byte-identical を実証）、test_mcp_server の葉数ピンも追従。
        残り: slack（Socket Mode）/ LINE（Webhook 署名検証）/ Gmail（OAuth）の各 platform
      → **残り（2026-09-14 監査）**: 未実装は LINE（Webhook 署名検証）と Gmail（OAuth）。discord は着地済み（questions/_combo.yml / questions/_internal.yml / _shared/bot-discord.py.jinja / tests/test_bot_layer.py）、slack（Socket Mode）は同日セッションで着地中
      - 置き場所: `cli` / `web_api` の上に載る opt-in レイヤー（MCP と同型）。
        library には載せない（import される側に実行可能サーバを載せる動機が薄い。
        include_mcp と同じ理由）。`include_bot`（bool）+ `use_recommended_bot` ゲート +
        `bot_platform` 詳細質問（discord / slack / line / gmail / all）の構成を検討
      - 推奨1本（設計原則5「推奨1本 + No でカスタム」）:
        discord = **discord.py**（公式感・事例の多さ vs nextcord / py-cord のフォーク事情を調査して決定。
        pycord 系のメンテ状況・slash command 対応・型スタブ有無で選定）、
        slack = **bolt**（公式 SDK。slack-sdk 素朴利用との住み分けを明記）、
        LINE = **line-bot-sdk**（Messaging API。Webhook 受信は web_api 層 or 単体 FastAPI 同梱かを設計）、
        Gmail = **google-api-python-client + google-auth**（Pub/Sub push or ポーリング。OAuth 認証情報の扱いが他と異なる）
      - 各 platform は「動く見本 + テスト」必須（specialty 解体の教訓）:
        最小コマンド応答（ping/pong 相当）+ in-process または fake-transport テスト。
        空ディレクトリ + 依存だけで終わらせない。web_api の prometheus/rate_limit/cors
        3スイッチ方式を踏襲し、カタログ化しない（認証・管理UI・キュー等は docs の「後で足せる」）
      - 起動形態（項目4 の独立起動モジュール方式を踏襲）: `bot_<platform>.py` の `main()` +
        専用 `[project.scripts]`（例: `bot-discord-<name>`）。`__main__.py` / Docker
        ENTRYPOINT / `python -m <pkg> --version` テストとは衝突させない
      - トークン管理: `.env.example` のトークン変数（例: `DISCORD_TOKEN` / `SLACK_BOT_TOKEN` /
        `LINE_CHANNEL_SECRET` + `LINE_CHANNEL_ACCESS_TOKEN` / Gmail OAuth JSON パス）+
        structlog 連携。起動時 env チェック（トークン必須・欠落時は起動拒否）。
        `.env` は commit しない（MCP の `MCP_ALLOWED_HOSTS` と同型の運用）
      - ログ: 生成 `logging_setup.py` 経由（`LOG_FORMAT=json` がそのまま効く）
      - Docker での常駐/再起動方針: `docker=true && include_bot` 時の `bot-serve` タスク
        （MCP の `mcp-serve` タスクと同型）+ compose service 化・HEALTHCHECK・restart 方針。
        項目6（web_api の Docker 拡充）と一体で検討
      - 依存マトリクス: `docs/reference/dependencies.md` に bot platform 別の runtime/dev
        依存 + entry point + deptry ignores + renovate カテゴリを追記（項目9 のマトリクス維持）
      - 配線: `bot_effective`（+ platform 別 `bot_discord_effective` 等）を
        `questions/_internal.yml` に新設し、render を一元化（mcp_effective /
        scraping_effective と同型）。`use_src_layout` / `pkg_dir` / `import_pkg` /
        `agents_md_effective` / `.env.example` ゲート / `_tasks.jinja` への影響を確認
      - docs: `docs/how-to/bot.md`（生成物一覧・トークン取得手順・非対応の明記）+
        `docs/explanations/long-running.md` に bot を第二の実装例として追記 +
        zensical nav 登録。README Features の常駐レイヤー節にも bot を追記
      - テスト: render（platform 別ファイル有無・依存有無・他タイプへの leak 無し）+
        実実行（fake transport での ping/pong 応答）+ ruff / basedpyright クリーン。
        `test_internal_variable_references_are_forward_only` / Z3 充足維持
      - 設計判断メモ（2026-09-08）: LINE Webhook と Gmail push は HTTP 受信口が要るため
        `web_api` 層との組合せ（base + layer）を第一候補とし、単体 bot でも最小受信
        （単体 FastAPI 同梱 or ポーリング）を選べる形を検討。Gmail は OAuth 認証情報
        （credentials.json / token.json）の gitignore・取扱いを CTF の flag* 除外と同型で実装
      - platform 固有の設計点（実装時に1つずつ潰す）:
        discord = Gateway intents（Privileged Intents の要否・取得手順）/ slash command 登録
        （guild 即時 vs global 遅延）/ 429 rate-limit・再接続 backoff の見本化。
        slack = Socket Mode（WebSocket・ローカル開発容易）vs HTTP（署名検証必須）の選択。
        推奨は Socket Mode 1本化を検討し、署名検証コードは HTTP 選択時のみ生成。
        LINE = Webhook 署名検証（`LINE_CHANNEL_SECRET` による HMAC）の必須実装 +
        `web_api` 併用時の route 設計（単体時は最小 FastAPI 同梱か long-polling か決定）。
        Gmail = OAuth（credentials.json → token.json リフレッシュ）vs サービスアカウントの選択、
        Pub/Sub push（HTTP 受信口要）vs ポーリングの選択。token.json / credentials.json は
        gitignore + gitleaks 対象にし、commit させない（CTF flag* と同型）
      - 他レイヤーとの組合せ定義: bot × MCP / scraping / web_api / data_science の可否マトリクスを
        `combinable` / `has_*` / `*_effective` に落とす。MCP 同時有効時は entry point 衝突
        （`mcp-server-<name>` vs `bot-<platform>-<name>`）と Docker ENTRYPOINT（CLI 既定のままか、
        `bot-serve` / `mcp-serve` 併記か）を決める。ros2 / micropython / oj_code / script は
        単独のまま（bot 質問を出さない。MCP / scraping と同型の除外）
      - パッケージマネージャ横断: bot 依存の pixi（conda-forge 有無・PyPI index 指定要否）/
        poetry / uv の出し分けを pixi how-to と同型で文書化。`tools/check_upstream.py` に
        bot SDK 群（discord.py / slack-bolt / line-bot-sdk / google-api-python-client 等）の
        floor pin を追加し、週次 drift 対象にする（template-dev.md「Hardcoded pins」規約）
      - セキュリティ baseline 連動: `.env.example` ゲートに bot トークン変数を追加、
        `.gitleaks.toml` にトークンパターン（`DISCORD_TOKEN` / `SLACK_BOT_TOKEN` /
        `LINE_CHANNEL_*` / Gmail JSON）の検出可否を検討、test_qa / hygiene の整合を確認。
        AGENTS.md / 生成 README に bot の起動・停止・再起動手順（`bot-serve` タスク含む）を追記
      - （「常駐レイヤー」の設計と MCP の実装例は docs/explanations と docs/how-to に
        文書化済み。discord/slack/LINE/Gmail はこの受け皿に載せる platform の実装として着手）
- [x] 既存の `include_mcp` をこの常駐レイヤーへ統合する（下記5と一体で整理）
      → 既存 include_mcp（mcp_server.py 生成）を常駐レイヤーの最初の実装例と位置づけ、
      docs（how-to / explanations）にその位置づけを文書化した
- [x] **複数要素の同時展開（base + layer）**（2026-09。data_science + web_api、
      web_api + MCP 等の要望に対応）
      - `project_type`（単一）は **base** のまま残し、追加要素は `include_*` bool
        質問で opt-in する（既存 `include_mcp` と同じ発想）。`project_type` 自体の
        multiselect 化はしない（`.copier-answers.yml` 非互換・Z3/list 対応等の
        コストに見合う恩恵が無い）
      - 新設 `questions/_combo.yml`（`include_data_science` / `include_web_api` +
        `combinable` ガード + `has_*` effective）。デフォルト全 false で単体
        render は byte-identical（全単体ケースで HEAD と比較検証済み）
      - `web_api` / `data_science` は `questions/_internal.yml` の同名 internal を
        effective 化（template 側の参照はそのまま効く）。`mcp_effective` も
        `web_api` 含有時に効くよう拡張
      - MCP 本体は `_shared/mcp_server.py.jinja` に集約し 3 wrapper
        （src / flat / `app/`）から include。web_api 含有時は
        `app/mcp_server.py` + `from app import mcp_server`（console script も
        `app.` 起点）。`test_mcp_server.py` / console script は `import_pkg` 化
      - 教訓2件を `docs/explanations/template-dev.md` に規約化:
        wrapper 単行化（2行 wrapper は先頭空行を生む）、`_internal.yml` 内の
        定義順（`when: false` も定義順に評価される。後方 internal 参照は
        Undefined/falsy になる）+ 後者を検出する
        `test_internal_variable_references_are_forward_only` を新設
      - ros2 / micropython / oj_code / script は単独のまま（ビルド・実行形態が
        根本的に違うため）。`combinable` ガードで強制 data の leak も防ぐ

## 5. MCP の整理（include_mcp と mcp_server の分裂解消）

- [x] `include_mcp`（mcp_server.py 生成 + mcp SDK 依存）と旧 specialty の mcp_server
      （inspector のみ）の2系統を1つに統合する
      - 旧 specialty='mcp_server' を撤去し、inspector 実行方法を include_mcp 生成の
        mcp_server.py docstring / README に移植した。これにより
        「片方だけ選ぶと exclude されない生成コードができる」不整合も構造的に消えた
- [x] **MCP Python SDK v2 移行**（2026-09。`pip install mcp` が 2.x になったことに伴い、
      生成物が import エラーで壊れていた問題を修正）
      - `FastMCP`（`mcp.server.fastmcp`）→ `MCPServer`（`mcp.server`）。v1 の import パスは
        v2 で消失しており、無指定の `"mcp"` 依存では新規生成プロジェクトが壊れる
      - 依存を `mcp[cli]>=2.0,<3` に変更（cli extra は `mcp dev/run/install` を提供。
        `<3` 上限は v1→v2 事故の再発防止）
      - SSE transport を撤去し **streamable-http** に置き換え（`--transport streamable-http`。
        SSE はプロトコル上 deprecated で「新規構築するな」の位置づけ）
      - `run()` は `if __name__ == "__main__":` ガード内でのみ呼ぶ（v2 要件。import で起動しない）
      - v2 SDK は完全な型スタブを同梱するため、mcp_server.py の basedpyright/pyrefly
        exclude を**撤去**（v1 時代の「stubs が無い」理由は消滅。argparse 起因の reportAny は
        `cast(Literal[...])` で回避）
- [x] mcp_server の実装例を「型付きツールの登録」まで拡充する（ツール定義・引数スキーマ・
      エラー処理）。テストは in-process client でツール呼び出しを検証する
      - `add(a: int, b: int)` / `divide(...)` の型付きツール（スキーマは型ヒントから自動生成）
        + `ToolError`（0 除算）の例 + `project://about` resource の例
      - `tests/test_mcp_server.py` を生成: SDK の `Client(mcp)` による **in-memory 接続**
        （サブプロセス・ポート不要）。anyio（`@pytest.mark.anyio`）+ `anyio_backend` fixture。
        dev 依存に anyio を追加（mcp SDK の推移的依存だが明示する）。このテストが
        「client としての利用コード」の見本を兼ねる
      - **「開発と利用は分けない」判断**: SDK は1パッケージで server/client 両対応。
        ホスト登録や `uvx` での既製サーバ利用はコード生成の対象外（設定+コマンド）のため
        how-to の1節でカバーし、質問は増やさない
- [x] streamable HTTP（リモートMCP）と docker での運用まで含めるかは、
      常駐レイヤーの設計（4）に合わせて決める
      - **streamable-http は scaffold の transport として採用**（`--transport streamable-http`、
        起動は `python -m <pkg>.mcp_server`）
      - **Docker でのリモート運用**（compose service 化・HEALTHCHECK・認証）と
        **配布前提スタンドアロンサーバ**（reference servers 型: PyPI 公開 + `uvx` + `.mcp.json`
        でのホスト登録レシピ）は将来TODOとして明記する（下記6の web_api Docker 拡充と一体で検討）
- [x] **include_mcp の対象を cli に絞る**（library / web_api は対象外に）
      - 理由: library は「import される側」であり、実行可能サーバを載せる動機が薄い。
        **web_api は 2026-09 の top-level app/ 化で <pkg> を無くしたため対象外に**。
        cli = stdio ローカルサーバ（+ streamable-http は cli でも起動可能）
      - **console script `mcp-server-<name>` を追加**（`[project.scripts]`）。ローカルでは
        MCP ホストが `uv run mcp-server-<name>` で起動、公開後は `uvx mcp-server-<name>` で利用
      - data_science / script / online_judge / ros2 / micropython / library / web_api では
        質問を出さず、data 強制でも orphan 依存が付かないよう内部変数 `mcp_effective` で
        render を一元化（既存 `security_policy_effective` 方式）
      - **2026-09 の同時展開対応で web_api が復帰**: `include_mcp` は
        cli / web_api base と `include_web_api` layer で質問され、`app/` 配置で
        生成される（上記項目4 の同時展開メモを参照）
- [x] **MCP scaffold へのセキュリティ実装**（2026-09。「実際にしこむ」対応）
      - docs の指針をコードに反映: `mcp_server.py` に **`--host` / `--port`** フラグを追加し、
        **非ローカルバインド（--host 0.0.0.0 等）には `MCP_ALLOWED_HOSTS` を必須化**
        （SDK は localhost 以外で DNS-rebinding protection を自動無効化するため、allowlist 無しの
        公開バインドは起動を拒否して構造的に防ぐ）。`MCP_ALLOWED_ORIGINS` も任意対応
      - `GET /health` を `@server.custom_route` で登録（無認証・allowlist 対象外は SDK 仕様。
        Docker / オーケストレータの liveness 用）
      - docker=true && include_mcp の時だけ **`mcp-serve` タスク**（docker build + run）を
        全タスクランナーに追加。Dockerfile に EXPOSE 8000 + 起動コメント
      - README / run-container / .env.example / docs に MCP_ALLOWED_HOSTS と Docker 起動例を追記。
        生成テストに health ルート・_allowed_hosts の in-process 検証を追加
      - 生成物の文字列連結は **ruff デフォルト（複数行は暗黙連結が標準）を明示的に固定**:
        `lint.flake8-implicit-str-concat.allow-multiline = true` を記載し、
        ISC003（複数行 `+` 連結の禁止）を有効のままにする。basedpyright の
        `reportImplicitStringConcatenation = false` で暗黙連結を許可
      - スモーク検証済み: allowlist 無しの 0.0.0.0 バインドは拒否、allowlist 有りで起動し
        悪意 Host は /mcp で 421、/health は 200。uv sync + pytest 9本 + ruff/basedpyright/
        pyrefly/deptry/vulture 全クリーン
- [x] **MCP scaffold の拡充: prompt + resource template + `.mcp.json`**（2026-09。
      参考: [Zenn 入門記事](https://zenn.dev/kiitosu/articles/31f55b99c33ce5)（v1系だが
      primitive 構成の参考）、[mcp-cookie-cutter](https://github.com/codingthefuturewithai/mcp-cookie-cutter)
      （SDK `<2.0` ピンで基盤は古いが example の豊富さが参考。デコレータ層・Streamlit UI・
      SQLite logging・JIRA DevFlow は守備範囲外として不採用））
      - 三 primitive 揃え: tool（add/divide）+ resource（about + greeting template）+
        prompt（review_code）。in-process テスト7本、basedpyright/ruff/format/deptry 全クリーン
      - `.mcp.json` 生成でホスト登録ゼロ手間化。README・how-to に登録手順を追記
- [ ] **将来拡張: 配布前提スタンドアロン MCP サーバのレシピ**（reference servers 型）
- [ ] **将来拡張: MCP server の本番運用**（残作業）
      - 調査メモ（2026-09）: MCP SDK 公式に Docker レシピは無い。SDK はプロセス管理を
        提供せず（`mcp.run()` は単一 uvicorn）、デプロイで MCP が関与するのは
        `TransportSecuritySettings`（Host allowlist。実装済み）のほか、
        マルチワーカー時の `RequestStateSecurity` 共有鍵と `SubscriptionBus` の2点。
        認証（OAuth 等）とプロセス管理は利用者側の仕事
      - streamable-http を **compose service 化**し、HEALTHCHECK（`/health` は実装済み）・
        認証（OAuth / reverse proxy）をどう載せるか。項目6（web_api の Docker 拡充）と一体で設計する
      - 最小権限・外部入力（prompt injection / SSRF）・ToolError の意図・公開時の
        transport_security 必須は docs/how-to/mcp.md の Security for server developers /
        users and operators 節に文書化済み。OWASP Agentic Skills Top 10 はスキル配布レイヤー
        （SKILL.md 等）向けで MCP server 開発の直接参照にはならない
        （OWASP Agentic AI Top 10 / LLM Top 10 が対応する領域）

## 6. web_api を「動く FastAPI scaffold」へ拡充する（s3rius/FastAPI-template 参考）

- [x] まず現状の欠落を解消する（どのオプションを選んでも効く土台）
      - FastAPI + uvicorn[standard] + pydantic-settings の依存追加と、動く `app` オブジェクト
        （`app/main.py` の create_app factory + module-level `app`、`app/settings.py`、
        `app/db.py`（async engine/session/Base）、`app/routers/{health,items}.py`、
        `app/schemas.py`、`app/models.py`（デモ Item））
      - Dockerfile ENTRYPOINT / compose command を CLI（--version）から
        `uvicorn {{ package_name }}.app.main:app` に変更（HEALTHCHECK は python urllib で
        /health を叩く）。compose api にも healthcheck + postgres の service_healthy 依存
      - pydantic-settings で .env.example の DATABASE_URL / HOST / PORT を読む
      - docs の「Add fastapi + uvicorn yourself」を廃止し、生成物に含める
- [x] `use_recommended_web_api` ゲートを新設する（既存の use_recommended_* 方式に乗せる。
      設計原則5）
      - 推奨: FastAPI + async SQLAlchemy 2.0 + alembic + asyncpg + Postgres + demo router/model +
        httpx(ASGITransport) テスト + asgi-correlation-id（リクエストID常時）+
        BackgroundTasks デモ（常時・依存追加なし）
      - No を選ぶと下記の詳細質問が出る
      - **DB 戦略**: CI は _test.yml が自動で DATABASE_URL を postgres サービス用に組み立てて
        渡す（実 DB を検証）。ローカルは sqlite+aiosqlite フォールバック（.test.db は gitignore）。
        テストは Base.metadata.create_all を使用（alembic はスキーマ進化専用）
- [x] 詳細質問の候補（s3rius の機能一覧から、このテンプレートで採用するものを絞る）
      - **認証**: **不採用**（docs に「後で足せる」+ 理由を明記）。fastapi-users は
        メンテナンスモード（セキュリティ更新のみ・後継開発中）のため、模範として焼き込まない。
        自作 JWT デモはセキュリティ責任が乗るため不採用。OIDC/SSO 連携や JWT ライブラリを
        docs で案内
      - **Redis**: 不採用（「後で足せる」に記載）
      - **バックグラウンドタスク**: FastAPI 標準 BackgroundTasks を常時デモ。taskiq/arq は
        docs の「後で足せる」に
      - **オブザーバビリティ**: **prometheus-client 直接の薄いミドルウェア**（約20行）で
        /metrics を実装。prometheus-fastapi-instrumentator は現行 fastapi/starlette
        （0.137+ / 1.x）と非互換（_IncludedRouter 問題）が繰り返しているため不採用
      - **demo 生成**: 常時生成（モデル + CRUD ルーター + テスト）
      - **DB**: Postgres 固定。テスト用 sqlite+aiosqlite は dev 依存として採用
      - **ORM**: SQLAlchemy 2.0 の1本固定（s3rius の 5種選択は取らない）
      - **採用した詳細質問（No 後）**: prometheus / rate_limit(slowapi) / cors — 3つのみ
- [x] 各オプションは「空ディレクトリ + 依存」で終わらせない（specialty 解体の教訓）:
      採用した項目（prometheus / rate_limit / cors / request-id / backgroundtasks）はすべて
      app 配線・テスト付きで「動く」状態。uv sync + pytest + ruff + basedpyright で実動検証済み
- [x] 取り込まない機能を明記する: GraphQL / REST 選択、Kafka / RabbitMQ、ORM 複数選択、
      gunicorn（uvicorn で足りる）、self-hosted swagger（FastAPI 内蔵で足りる）、
      traefik ラベル、piccolo ORM、SQLAdmin / FastCRUD、taskiq/arq。docs/how-to/web-api.md に
      「後で足せる」と理由付きで明記
- [x] **web_api をトップレベル app/ パッケージへ再設計**（2026-09）
      - FastAPI アプリを src/<pkg>/app から **top-level `app/`** へ（`uvicorn app.main:app`）。
        ライブラリ <pkg> を廃止し、src/flat で2重化していた app/（byte-identical）を1本化
      - CLI（`__main__.py`）/ test_cli / test_qa を web_api では生成しない
        （uvicorn 起動が本流。テストは tests/test_app.py のみ）
      - MCP は cli 限定へ（web_api に <pkg>/mcp_server.py の置き場が無くなった。項目5）
      - layout 質問から web_api を除外し、`pkg_dir` / `import_pkg` 内部変数で
        「import ルート = app」を一元化。logging_setup は _shared/ の共通 partial にし
        <pkg> と app の両方から include（詳しくは docs/explanations/template-dev.md）
      - **「複雑な web_api が欲しい場合は upstream full-stack-fastapi-template を案内」**
        と help / docs に明記（web_django 方式。フロント・認証等はスコープ外）
- [x] **将来拡張: app 構造を選べるようにする**（2026-09 相談で保留 → 結論: 追加しない）
      → **完了（2026-09-14 監査）**: 「追加しない」の決定を docs/explanations/vision.md「What this is deliberately not」と docs/how-to/web-api.md:17-20（API-only）に明記
      - 現状は top-level `app/` のレイヤード構造（`app/models.py` + `app/schemas.py` +
        `app/routers/`）固定。benavlabs/FastAPI-boilerplate のような **vertical-slice**
        （機能ごとの `modules/<feature>/{model,schema,router}.py`）は**詳細質問に追加しない**
        と決定（2026-09）。web_api は「シンプルな API のみ」に限定し、複雑な要求は
        upstream full-stack-fastapi-template を案内する。vertical-slice が欲しい場合は
        その案内先で実現する
      - デモ Item 1つでは両構造の差がほぼ出ない、という理由付けも残る
- [ ] **将来拡張: SQLAdmin（管理画面）/ FastCRUD を詳細質問に追加**（2026-09 相談で保留）
      - benavlabs は SQLAdmin ベースの admin + FastCRUD を採用。用途が違う
        （SQLAdmin = 人間がブラウザで CRUD、FastCRUD = API コードのボイラープレート削減）ため
        両方載せる場合は独立質問になる
      - 各オプションは「動く見本 + テスト」必須（デモ Item 前提）。現状は docs の
        「後で足せる」に記載のみ

## 7. セキュリティ / CTF の扱い

- [x] CTF を project_type に**追加しない**（実行環境は既存 library/cli と同じ。
      設計原則2）。online_judge とも別物（CTF に AI 可否の大会規約は無い）と整理する
      → docs/reference/questionnaire.md に「Not project types」節として文書化済み
- [x] セキュリティ基盤は既に実装済みであることを docs に明記する:
      zizmor（CI 監査）、pip-audit（脆弱性スキャン）、Sentry（任意）
      → pip-audit は _tasks.jinja の `audit` タスクとして分離（recommended/full のみ。
      OSV/PyPI への network 依存のため type-check/check/CI からは外し、offline でも
      green を維持）。zizmor / Sentry は従来通り docs 記載
- [x] 参加者向け CTF レイヤー（`include_ctf`）を実装する（library / cli の上に載る
      opt-in レイヤー。`ctf_effective` で render を一元化）
      - 生成物: `challenges/pwn/example/solve.py`（stdlib のみで動作＋pwntools
        レシピ同梱）、`tests/test_ctf_example.py`（solve.py の実実行検証）、
        `ctf` extra（pwntools / z3-solver）、.gitignore（vuln / flag* 除外）、
        ruff per-file-ignores（challenges 緩和）、deptry DEP002 許可
      - テスト: tests/test_example.py に3件（render / 実実行＋ruff /
        他タイプへの leak 無し）。構造（Z3/forward-only/union）・改行・QA 全緑
      - 対象外（据え置き）: 問題作成者側（Docker+socat+gdb、CTF 運営）は別リポジトリの
        仕事として生成しない

## 8. SRE / Ansible / IaC の扱い

- [x] Ansible を project_type に**追加しない**（YAML プロジェクトであり Python の
      実行環境と噛み合わない。設計原則3）
      → questionnaire.md の Not project types 節に文書案内として記載
      （web_django のような生成時 abort は無し — 選択肢自体が無いため）
- [x] Terraform / K8s / Ansible 等の IaC は「アプリの隣に置く別リポジトリの仕事」と
      位置づけ、このテンプレートでは生成しない → 同上
- [x] SRE は「web_api の運用強化」に限定して進める:
      healthcheck、非root実行、read-only filesystem、resource limit を Dockerfile /
      compose に追加。otel は見送り（初期質問にしない）。prometheus / rate_limit /
      cors の3スイッチは web_api の観測面として維持
      → 実装済み: Dockerfile runtime に USER appuser + /app chown（uv/pixi 両方）、
      compose.local.yml に read_only + tmpfs（/tmp と ~/.cache）+ mem_limit/cpus
      （plain `compose up` で効く service-level）。
      HEALTHCHECK は従来通り。otel は見送り

## 9. 初期ライブラリの設定（project_type / レイヤー別の初期依存マトリクス）

- [x] project_type ごとに「初期依存セット」を一覧表（マトリクス）に整理する
      - 例: web_api → fastapi/uvicorn/sqlalchemy/alembic/pydantic-settings、
        data_science → polars/duckdb 等、online_judge → なし（stdlib のみ）。
        推奨1本 + No でカスタムの形
      → docs/reference/dependencies.md を新設（runtime/dev/experiment/entry point/
      deptry ignores/renovate/config parity を記載）。zensical nav + reference.md に登録
- [x] 生成される pyproject.toml の初期設定を充実させる
      - ruff / basedpyright の生成先への展開がテンプレート本体と一致しているか確認
        → 共有選択肢（ALL+preview、line-length 120、single-line isort等）は一致、
        差分は意図的（対象の違い）を文書化。ついでに kaggle の deptry 24件を解消
        （`responses` 除去 + ML依存/自己参照の ignore 追加、新規テストで固定）
      - `[project.scripts]` の entry point と、上記4の常駐起動（daemon）の関係を整理
        → マトリクス文書の Entry points 節に整理済み（CLI/MCP/web_api等の対応表）
- [x] 初期依存の更新（下記12のバージョン追従）と整合するよう、生成先 renovate.json の
      packageRules を依存カテゴリごとに整理する
      → Core CI / Release / Container / PyPI / Docs / Scorecard / FAIR /
      Dockerfile の8カテゴリに分割。パリティテストも分割対応に更新
## 10. data-science / kaggle の整理（AGENTS.md / online_judge 再編後の整合）

- [x] data_science の純化後仕様を再確認する: notebooks / data / models / reports /
      paper の分析型として、competition 残骸（_tasks.jinja の dataset/train/predict 等
      の競技タスク、.gitignore の input//exp/ 等）を掃除する
      → 確認済み: _tasks の競技タスクは kaggle 条件、template/.gitignore を
      .gitignore.jinja 化して DS/Kaggle ブロックを条件化し、root から input//exp/
      を削除。.dockerignore も同様に条件化（DS 全枝 + kaggle 全枝）。
      test_gitignore_same は union 検査に更新。README の competition 言及は
      kaggle パスのみ残存（data_science パスは無し）— 意図通り
- [x] kaggle（online_judge 内）の初期依存を整理する: torch/lightgbm/xgboost 等の
      競技用依存、wandb、GPU/CUDA バージョン追従
      → cu124→cu126（torch 2.6凍結のため。cu126でtorch 2.14.0+cu126解決を確認）、
      optuna>=3.5→>=4.0、torch>=2.6→>=2.12、torchvision>=0.21→>=0.27、
      Dockerfile.gpuもCUDA 12.6.3に更新。deptryはクリーン維持
- [x] online_judge（atcoder / leetcode）と kaggle で、AI 可否の扱いが一貫しているかを
      AGENTS.md 生成ロジックで担保する（一元管理のテスト）
      → `agents_md_effective` が library / cli / script / web_api /
      data_science / kaggle を常時、oj_code は oj_allow_ai 時のみ true にし、
      ros2 / micropython は false。tests/test_example.py の 4件で固定

## 11. バージョン追従
- [x] テンプレート本体の renovate.json の運用を点検する
      - lockFileMaintenance / pre-commit / vulnerabilityAlerts は有効。
        テンプレートが固定するバージョン（micropython_version 等）の追従方針を一元化
      → 点検済み: extends/vulnerabilityAlerts/lockFileMaintenance は両方で有効。
- [x] `tools/check_micropython_upstream.py` のような上流確認ツールを他分野へ拡張する
      （ROS 2 distro の EOL、CUDA、python サポート一覧 等）
      → tools/check_upstream.py に統合（MicroPython tag/stubs + CUDA base/cu-index +
      ROS 2 EOL + Python floor + Postgres + Ubuntu）。週次 check-upstream.yml で
      drift issue を自動作成。旧ツールは shim として残し、旧 workflow は手動化。
      template-dev.md に「Hardcoded pins need an upstream check」規約を追加
- [x] 上流フォーク（DiamondLightSource）の新規コミット検知と、copier 自体の
      メジャー更新検知を追加する
      → git フォーク追従は tools/check_upstream_fork.py + 週次
      check-upstream-fork.yml（火曜 06:00）。**check-upstream.yml（pin 専用・月曜）とは
      別物** — 名前は似ているが役割が違う。copier は root pyproject.toml で
      `>=9,<10` に pin し、check_upstream.py が「copier ceiling」pin として
      メジャー drift を週次報告する。ルート依存の pip-audit は task audit +
      週次 dependency-audit.yml（木曜 07:00）で実施
- [x] v1.0 公開のタイミングで fork を解除し、履歴を新規にして独立リポジトリとして
      公開し直す（2026-09 方針確定。GitHub Support への detach 依頼はしない）
      → **完了（2026-10-04）**: delete+recreate で `ConstitutiveTemplates/foundry`
      として独立公開（詳細は HUMAN_TODO.md と TODO.md §37-38。ブランド名
      `foundry` 確定、全リネーム・NOTICE・リポジトリメタデータ復元済み）
      → 手順: 作業クローンで `git checkout --orphan` + 単一初期コミットを作成し、
      `gh repo create` した新リポジトリへ push（過去ログ・DiamondLightSource 由来の
      履歴は持ち込まない。setuptools-scm 用に v1.0.0 tag を打ち直す）。
      新リポジトリで再設定が必要なもの: EXAMPLE_DEPLOY_KEY 等の secrets、
      GitHub Pages、branch protection、renovate 連携。
      check-upstream-fork.yml は URL 直 fetch なので解除後もそのまま機能する
      （fork の間は Issues が無効のため、週次 workflow の issue 作成ステップは失敗する。
      気になるなら detach まで該当 workflow を無効化）
      → **継承タグの危険性を実害として確認（2026-09-06）**: 現時点の最新タグは
      5.4.0（2026-08-14、DiamondLightSource 由来の内容）で、`copier copy URL` を
      **`--vcs-ref` 無し**で実行すると copier は最新タグをチェックアウトするため、
      古い upstream テンプレートが「現行テンプレート」として使われてしまう
      （BUG.md #1「docs_type に zensical が無い」・#6「component_owner を聞かれる」
      の2件はどちらもこの罠が原因。`git show 5.4.0:copier.yml` で確認済み）。
      **detach まで全ドキュメントの URL 生成コマンドは `--vcs-ref=main` 必須**
      （README / docs/tutorials/create-new.md / adopt-existing.md は対応済み）。
      孤立例: 新規プロジェクトを作るチュートリアル、example 再生成 CI
      （`_example.yml` は既に `--vcs-ref=HEAD` 付きで正常）。detach 時に上記タグを
      削除・打ち直す作業を忘れないこと

## 12. セキュリティ / コンプライアンス基盤の整備（OpenSSF Scorecard / OSPS 準拠）

ルート（テンプレ自体）と生成物の両層に、OpenSSF Scorecard の検証項目とリポジトリ配置

### 実施済み

- [x] ルート workflow の権限最小化: 全 `.github/workflows/*.yml` に
      `permissions: contents: read` と checkout `persist-credentials: false`
      （例外は push 用 `_example.yml`）。生成物側はルートへの symlink のため自動反映
- [x] ルートに SECURITY.md / LICENSE(Apache-2.0) / LICENSES/ / REUSE.toml /
      CITATION.cff / codemeta.json / .github/CODEOWNERS / .github/ISSUE_TEMPLATE/ を新設
- [x] `.github/workflows/scorecard.yml`（SHA固定・publish_results）と
      `security.yml`（zizmor-action CI）を新設
- [x] renovate に `helpers:pinGitHubActionDigests` を追加（ルートと生成物両方）
- [x] copier.yml に `use_recommended_security` ゲート + `security_policy` / `scorecard`
      詳細質問を追加。SECURITY.md / scorecard.yml は GitHub プロジェクト限定
      （effective 変数で render 時に git_platform 判定）
- [x] 生成物に SECURITY.md.jinja / security.yml.jinja / scorecard.yml.jinja /
      test_qa.py.jinja を追加（online_judge では test_qa を生成しない）
- [x] ルート tests/test_qa.py + 生成物 test_qa.py.jinja（Aqua.jl 風）
- [x] tests/test_workflow_security.py（permissions / persist-credentials / 分岐参照の静的検査）
- [x] docs/explanations/security.md + README バッジ（Scorecard）追加

### 残タスク（今回のセッションで対応）

- [x] **全アクションの SHA 固定**（ルート + 生成物）:
      ルート `.github/workflows/*.yml` の全 `uses:` を手動で 40桁SHA + `# vX.Y.Z`
      コメントに変換（renovate の pinning PR を待たず実施）。テンプレの実体ファイル
      （ci.yml.jinja / fair-software.yml.jinja / security.yml.jinja / scorecard.yml.jinja）
      も手動固定。生成物の reusable はルートへの symlink なのでルートの変換で反映。
      例外: `pypa/gh-action-pypi-publish@release/v1` のみ upstream 推奨ブランチ運用のため
      非固定（zizmor.yml に ignore で明記）。
      なお、ルートが参照していた `actions/upload-artifact@v8` は実在しないタグで
      （v8 は download-artifact のみ）、テンプレ ci.yml.jinja を v7.0.1 に修正
- [x] zizmor の全ルール有効化 + 意図的例外を ignore で明記（ルートと生成物の両方）:
      unpinned-uses（_pypi.yml の release/v1）/ artipacked（_example.yml の push 用
      credentials）/ superfluous-actions（_release.yml と ci.yml の softprops）/
      template-injection（ci.yml の toJSON(needs)）を ignore 化。disable は全廃
- [x] tests/test_workflow_security.py を全 SHA 必須に強化:
      `DELIBERATE_BRANCH_REFS`（pypi publish のみ）を例外として、それ以外の `uses:` は
      40桁SHA を必須化
- [x] 生成物 renovate.json.jinja の無効化 packageRules に新規アクションを追加:
      zizmorcore/zizmor-action（常時）/ ossf/scorecard-action + github/codeql-action
      （scorecard 有効時）をテンプレ管理対象として renovate の更新停止
- [x] ルート .pre-commit-config.yaml に `validate-cff` / `reuse` フックを追加
      （CITATION.cff / REUSE.toml の検証を本体でも実施。ともに Passed 確認）

### 残タスク（外部・手動依存）

- [ ] renovate の digest 更新を確認（SHA 固定済み参照の新バージョン追随は renovate の
      digest PR が担う。初回実行で pinning/digest PR が開くのを確認する）
      → **初回確認済み（2026-10-04）**: renovate は生成物の renovate.json で
      pin/digest 追従を担う設計（`test_renovate_baseline_matches_generated_template`
      で固定）。ConstitutiveTemplates org への renovate app 連携自体は
      人間判断のため HUMAN_TODO に残す
- [x] example リポジトリを copier update で再生成し、test_example_repo_updates
      のパリティを通す（main push で _example.yml が自動実行）
      → **org 移行済み（2026-10-04）**: `ConstitutiveTemplates/foundry-example`
      を新設、全参照を移行、初期 render 済み。旧 kasi-x 名の原文は当時の記録
- [x] リポジトリ公開後に Scorecard のスコア・バッジを確認（private では機能しない）
      → **確認済み（2026-10-04）**: workflow 成功 + api.securityscorecards.dev で
      総合 5.3。低いのは Branch-Protection(0) / Code-Review(0) / SAST(0) /
      Maintained(0) — いずれも org 移転直後で PR 履歴・保護設定が未反映
      （HUMAN_TODO の Branch Protection 再設定で解消見込み）

## 13. 質問票・テンプレートソースの保守性向上（2026-09）

肥大化した copier.yml（940行）と、jinja の頻出バグ（末尾改行）への対処。

- [x] **copier.yml を questions/ フラグメントへ !include 分割**（2026-09）
      - copier.yml は project_type + include 連鎖 + underscore 設定のみ（~110行）。
        questions/{ros2,micropython,online_judge,data_science,web_api}.yml（ジャンル）と
        _common_{a,b,c}.yml（横断ゲート）、_internal.yml（when:false 派生変数）
      - 各 `!include` は独立した YAML ドキュメント（同一ドキュメント内で2つ置くと
        同名キー衝突で後勝ちになる）
      - **後方参照バグ修正**: 質問が参照する内部変数（micropython_pkg / online_judge /
        kaggle）を、参照する質問より前のジャンルフラグメントに配置
        （docs_type の micropython 分岐が常に sphinx 側に落ちるバグ。テストは data 全指定の
        ため隠れていた）
      - 分割後も生成結果は byte-identical（全8タイプで HEAD と比較検証）
- [x] **質問票の完備性を機械検証するテスト群**（2026-09）
      - フラグメント union 整合（重複なし・漏れなし）
      - 質問参照の前方 DAG 性（後方参照を検出）
      - **Z3 充足検査**: 全 when 条件の充足可能性を z3-solver で検査（死んだ質問・タイポ検出）。
        z3-solver を dev 依存に追加
      - test_copier_structure.py は copier の load_template_config で !include を解決
- [x] **生成物の末尾改行を検証するテスト**（2026-09）
      - test_generated_files_end_with_single_newline: 全レンダーパスのテキストファイルが
        「末尾ちょうど1改行」であることを強制（jinja の include / 条件タグが末尾空行を
        生む頻出バグへの対処）
      - 検出・修正: pyproject.toml.jinja（poetry ブロック後の空行）、web_api の
        test_app.py.jinja（末尾 endif 後）
- [x] **テンプレートソース作成規約を docs に蓄積**（2026-09）
      - docs/explanations/template-dev.md を新設: 末尾改行制御 / _shared/ include 共有 /
        questions/ 順序・前方参照 / Z3 充足維持。各規約に強制テストをリンク
- [x] **pyproject.toml.jinja を `_shared/` フラグメントへ分割**（2026-09。項目5の
      mcp_server.py / logging_setup.py と同じ「共有 partial + 薄い include」パターンを、
      肥大化した pyproject.toml.jinja 自体にも適用）
      - `_shared/pyproject-basedpyright.toml.jinja` / `-ty-checkers.toml.jinja`（pyrefly/ty）/
        `-test-coverage.toml.jinja`（pytest/coverage/typos/vulture/deptry）/
        `-ruff-lint.toml.jinja`（select/ignore/task-tags 本体）/ `-ctf-extra.toml.jinja` /
        `-ctf-lint.toml.jinja` / `-scraping-lint.toml.jinja` / `-kaggle-lint.toml.jinja`
        （per-file-ignores 各節）を新設し、本体からは `{% include %}` のみにする
      - `_shared/pyproject-scraping-banned-api.toml.jinja` は下記項目14（scraping
        レイヤー）の ruff `banned-api` 節をここに同居させ、本体は1行 include のまま
      - 末尾改行規約（上記）はここでも適用: 各 include の直前直後で改行を持たない
        ラッパー行にする。`.pre-commit-config.yaml` の `end-of-file-fixer` に
        `.jinja` 除外を追加し、`pre-commit run --all-files` がこの規約を壊して
        レンダー結果に空行を混入させる事故を構造的に防止（2026-09 に実際に
        7ファイル巻き込まれて発覚・修正 — 生成物側の改行検証は既存の
        `test_generated_files_end_with_single_newline` が担うので、ソース側の
        `end-of-file-fixer` は不要かつ有害と判断）
- [x] **`tests/test_machine_gate.py` を新設**（2026-09。高速な静的事前検査）
      - 全 `.jinja` ソースを Jinja2 でパース（if/endif 不整合等の壊れを検出）+
        全 `questions/*.yml` を YAML としてロード + copier 自身の
        `load_template_config` で解決可能かを検証。uv sync 不要・オフラインで
        ミリ秒オーダーに終わるため、test_example.py の重いレンダーテストより先に
        壊れを検出できる
- [x] **将来拡張: ジャンル別サブディレクトリ（_subdirectory 切替）は不採用**
      → **完了（2026-09-14 監査）**: 不採用の決定を本文に記録（2026-09）。目的だった肥大化解消は questions/ の !include 分割（questions/ros2.yml / questions/micropython.yml / questions/online_judge.yml / questions/data_science.yml / questions/web_api.yml）で達成済み
      - template/ をジャンル別ツリーに分け `_subdirectory: template/{{ project_type }}` で
        切替える案は調査・実験の結果**不採用**（2026-09）。全8ジャンル共通ファイルが64あり、
        各ツリーへの symlink 共有が過大。質問票の !include 分割（上記）で主目的
        （肥大化解消）は達成済み
- [x] **将来拡張: AGENTS.md / oj_allow_ai の設計と実装**（項目1・2 の残り。AGENTS.md は
      library / cli / web_api / data_science / script / kaggle に常時生成し、AI NG の
      online_judge 種に置かない。項目1 のチェックリストを参照）
- [x] **残存するテスト失敗2件の解消**（2026-09 combo 対応時に発覚。いずれも HEAD でも
      失敗する既存の問題で、combo の退行ではない）
      - `test_template_with_extra_code_and_api_docs`: 生成物の sphinx docs ビルドが
        失敗する。原因切り分けから着手 → **解消**: README 先頭の H1 が
        `<div align="center">` 内にあり MyST が H1 と認識せず myst.header 警告 9件が
        --fail-on-warning で落ちていた。H1 を div 外に移動してテスト通過を確認
      - `test_example_repo_updates`: example リポジトリとの parity 不一致。main push で
        _example.yml が example repo を再生成した後に通す（項目12 の外部依存と同型。
        ローカルでは外部リポジトリへの push 不可のため未実行のまま残す）

## 14. Web スクレイピングレイヤー（include_scraping）の新設

設計原則1に従い project_type は増やさず、CTF / MCP と同じ「既存 project_type の上に
載る opt-in レイヤー」として cli に追加する。**Good-future-python** charter
（respect the source / law / commons。詳細は docs/explanations/good-future.md）を
コードで強制することが狙い — 礼儀正しいスクレイピングを「ドキュメントで頼む」のではなく
「ruff banned-api / robots.txt チェック / レート制限 / CI」で構造的に強制する。

- [x] `include_scraping` 質問を新設する（`project_type == 'cli'` のみ。項目4の
      combo 方式に合わせ `questions/_combo.yml` に配置）
      - Yes で `CHARTER.md` + フェッチャーモジュールを生成。ruff `banned-api` で
        `requests.get` / `httpx.get` / `urllib.request.urlopen` 等の直接呼び出しを
        フェッチャー外で禁止し、全フェッチが1箇所を通ることを構造的に強制
      - CAPTCHA 回避ヘルパーは一切生成しない（サイト規約違反のため対象外と明記）
- [x] `use_recommended_scraping` ゲート（既存 use_recommended_* 方式）+
      `scraping_engine` 詳細質問（httpx / scrapy / memorious / playwright / all）
      - 推奨: httpx — stdlib robots チェック + per-host レート制限 + on-disk
        キャッシュのポライトフェッチャー。新規ランタイム依存なし・オフラインテスト
      - No を選ぶと4エンジンから選択（all は全エンジン同時生成）
- [x] エンジンごとの生成物（`_shared/fetcher-httpx.py.jinja` 他3種 + wrapper 8種
      [src/flat layout × 4エンジン]。項目5/13 と同じ「共有 partial + 薄い wrapper」
      パターン）
      - **httpx**（全エンジンの土台。memorious/playwright/all も再利用）:
        `preflight()` が feed（`/feed`, `/rss.xml`, `/atom.xml`...）→ API ヒント
        （`/api`, `api.` サブドメイン, `openapi.json`）→ scraping の順で判断
        （feed-first / API-second / scraping-last）。robots.txt 拒否は
        `RobotDeniedError`、401/403 は `AccessDeniedError`（回避せず停止）、
        host あたり `max_requests_per_host`（既定100。discovery probe も含む）
        超過は `BudgetExceededError`。判断結果は origin 単位でキャッシュし
        2ページ目以降の probe コストを削減
      - **scrapy**: `ROBOTSTXT_OBEY` + `AUTOTHROTTLE` + `DOWNLOAD_DELAY` を
        `custom_settings` に強制したスパイダー starter
      - **memorious**: レート制限・キャッシュ済み HTTP セッションの crawler config。
        **memorious4 は AGPL-3.0** のため選択時に `license_effective` を
        AGPL-3.0 へ強制上書き（勝手に MIT へ戻さないよう README/docs に明記）
      - **playwright**: JS レンダリングページ向け headless-Chromium フェッチ
        （robots precheck はフェッチャーから再利用）。テストではブラウザ起動しない
        （config デフォルトのみ検証）
      - 全エンジンに offline テスト付き: `test_scraping.py` /
        `test_scrapy_spider.py` / `test_memorious_crawler.py` /
        `test_browser_fetch.py`（`{% if scraping_*_effective %}` で個別出し分け）
- [x] `.cache/fetcher/` / `.cache/ms-playwright/` を gitignore（`_shared/`
      partial 化し `template/.gitignore.jinja` とルート `.gitignore` の両方に
      union 反映。項目13 の末尾改行規約に従い include ラッパーは改行なしで終端）
- [x] docs 新設: `docs/how-to/scraping.md`（生成物一覧・ライセンス影響・非対応の明記）+
      `docs/explanations/good-future.md`（charter 本文。respect the source /
      law / commons の3原則と、各ルールの実施箇所（ruff/pytest/CI）の対応表）+
      zensical.toml nav 登録
- [x] テスト: `test_template_include_scraping_httpx` / `_runs` /
      `_not_offered_elsewhere` / `test_template_scraping_engine_choices` /
      `test_template_scraping_memorious_forces_agpl`（他 project_type に
      scraping 関連の依存/質問が漏れないことも検証）
- [x] **将来拡張**: CAPTCHA 回避以外のポライトネス拡張（sitemap.xml 優先探索、
      条件付き GET の ETag/If-Modified-Since 対応）は要望が出てから検討。
      現状は feed/API 優先探索 + robots.txt + レート制限 + キャッシュで
      「行儀の良いデフォルト」を満たしていると判断し、初期スコープに含めない
      → **完了（2026-09-14 監査）**: 「初期スコープに含めない」の決定を本文に記録。行儀の良い既定（feed/API 優先 + robots.txt + レート制限 + キャッシュ）は docs/explanations/good-future.md に記載

## 15. 検知・運用の残課題（2026-09-05、Strategy.md 実装後に判明）

### 追加対応（2026-09-05 bugs.md / 生成セッションのフィードバック）

- [x] `.env.example` / README "Environment variables" を機能ゲート化
      （web_api / mcp / scraping / sentry / agent scaffold のいずれかがあるときのみ。
      依存ゼロ library へのノイズ解消 = bugs.md #3。`.envrc` は venv アクティベーション
      用として全タイプ常に生成）
- [x] devcontainer ベースイメージを実在する
      `ghcr.io/diamondlightsource/ubuntu-devcontainer:resolute` に戻し
      （`kasi-x/ubuntu-devcontainer` は未公開で devcontainer ビルドが 404 する =
      bugs.md #2）+ `tools/check_upstream.py` に Devcontainer base pin
      （GHCR manifest 実在チェック、404 で drift）を追加
- [x] `use_recommended_agent` の質問文を gate 形式に修正
      （"Add an LLM agent scaffold?" は Yes の意味と gating が逆 = bugs.md #1。
      変数名は設計原則の `use_recommended_*` 統一のため維持）

### 既知の残課題

Strategy.md ①②③④ は commit a82f9a46 で実装済み。当日の push 検証で
**CI-only の失敗が3種類**見つかり、すべて修正済み（詳細は各項目）。

- [x] lint 失敗（2段階）: (a) check-yaml × copier.yml（multi-document）→
      exclude を追加。(b) 新設テストファイルの ruff format 差分（ルートの
      line-length は 120）→ format 適用。**レッスン: 新規ファイル追加後も
      `task lint` を回す。ローカル通過をファイル作成前に確認して終えていた**
- [x] test 失敗①: `test_example_repo_updates` が clone する
      `kasi-x/python-copier-template-example` が存在しない（404）
      → リポジトリを新規作成（public）+ 現 HEAD から生成して初期 push +
      書き込み可能 deploy key を登録 + `EXAMPLE_DEPLOY_KEY` secret を設定。
      テストがローカルで pass することまで確認済み
      → **再発（2026-10-04、org 移行時）**: `ConstitutiveTemplates/foundry-example`
      を新設し `_example.yml`・example-answers・README・example テストを移行、
      初期 render を force-push 済み。ただし **org リポは設定で deploy key が
      無効** のため `_example.yml` の `peaceiris/actions-gh-pages` publish 経路が
      `Permission denied (publickey)` で失敗中 — HUMAN_TODO Secrets 項に記録、
      publish 経路の見直し（GITHUB_TOKEN 方式等）が人間判断待ち
- [x] test 失敗②（テンプレートバグ）: CI の `_test.yml` は Postgres サービスなしの
      組み合わせで**空文字の `DATABASE_URL` を export する**ため、生成 web_api の
      `settings.py` が空 URL を既定値の代わりに採用し `test_app.py` の import が
      落ちていた（09-03/04 の postgres CI 導入以降、CI だけ赤で未発見）。
      → `env_ignore_empty=True`（settings）+ 生成 `test_app.py` 側も
      空文字を未設定扱いにするよう修正。空 DATABASE_URL での再現テストで確認
- [x] docs 失敗: gh-pages publish が 403。リポジトリの
      `default_workflow_permissions` が read であり、reusable workflow
      （`_docs.yml`）自身の top-level `permissions: contents: read` が
      呼び出し元（ci.yml）の write をキャップするため
      → `_docs.yml` の build ジョブに `permissions: contents: write` を明記
- [x] `example` ジョブも非対話で copier が停止する問題を修正
      （085b1579 追加の scraping 質問が example-answers.yml に答えを持たないため。
      `_example.yml` に `--defaults` + `--with copier-template-extensions` +
      `--trust` を追加。テストの update コマンドとは既に揃っていた）
- [x] **次の CI run が緑になることの確認**（上記修正の push 後。test 12分前後）
      → **2026-09-21 解決**: 大規変更 12 コミットpush後の CI (run 35565903980) が
      全面緑(lint 26s / docs 58s / hygiene 35s / test 5m52s / test-meta 41s /
      Security ✓)。初回 run で hygiene の EOF チェックが検出した実差分
      （ベンダーした clean.scss に改行が無い。upstreamの出荷物のまま）を修正し
      2回目で緑。なおローカル act 実走が先行して typos の実バグ(fpr 識別子)を
      捕捉済み — §19 の act 教訓を参照。週次 lychee (periodic.yml, 水曜) は
      schedule 到来待ち
      → 2026-09-07: 大規模変更(bug修正一式 + pre-commit 廃止)を push 済み。
      初回ランで2件の新規失敗を処理済み: ①`_hygiene.yml` のEOFチェックが
      ディレクトリsymlinkでクラッシュ + .jinja 部分テンプレ(意図的に改行なし)を
      検出 → 除外して修正(987abac7)。②Security が zizmor v1.30 の新監査
      `unpinned-tools`(setup-just の just-version 未指定)で失敗 → just 1.58.0 に
      ピン + check_upstream の週次ドリフト報告に追加(87058c2a)。③同 v1.30 の
      `self-repository` 監査が既存の `./.github/workflows/*` 参照形式全体に発火
      → 両 zizmor.yml に意図的 ignore を記載(87e3525e)。最終ランの結果確認が残る
      - [x] **教訓**: security.yml の zizmor `version: latest` は新監査追加時に
            全プロジェクトの Security を赤くする → **恒久対策済み（2026-10-04
            確認）**: security.yml は cli `1.30.1` + action `v0.6.4` の SHA pin。
            renovate 追従は生成物の renovate.json baseline 管理対象
            （`test_renovate_baseline_matches_generated_template` で固定）
- [x] Periodic（リンクチェック）: 2026-08-26 / 09-02 の赤は旧 tox 版 workflow の
      失敗。現行 lychee 版（085b1579 で投入）は水曜スケジュールが初回実行 →
      初回結果を確認し、赤ならリンク修正
      → **初回着地（2026-10-04）**: workflow_dispatch で手動初回実行 → success
- [ ] README の CI バッジと実態の乖離に注意: 直近コミットで CI が赤でも
      バッジは古い成功を示し続けた。赤を放置しない運用（push 後の run 確認、
      または merge queue / required checks の見直し）を習慣化する
- [x] flaky: `test_template_task_runner_just_works` がフル並列実行で 1 回のみ
      失敗（単独・再実行は pass）→ **診断完了（2026-09-06、サブエージェント調査）**。
      最有力は pre-commit 共有ストアの hook 環境インストール競合:
      `repository.py` の `_hook_install` は `py_env-*` を rmtree+再インストールするが
      クローンと異なり flock が無く、hook `rev` 更新後のコールドウィンドウで
      32 ワーカーが同一環境を同時構築して 1 ワーカーが部分的なインストールで落ちる
      （uv キャッシュは競合安全設計のため疑いから除外、git 競合も個別 tmp_path のため除外）。
      対策として xdist ワーカー毎の `PRE_COMMIT_HOME` 分離を試したが、
      **コールドインストールが 32 回発生して 48 失敗・7分44秒化したため撤回**
      （tests/conftest.py に経緯を記載）。発生頻度は低いため現状は共有ストアのまま、
      flake 時は solo 再実行。pre-commit 本体への報告草稿を
      upstream-drafts/10 に用意済み
- [x] ルート `.python-version` が未レンダの Jinja 式のまま（`ros2_pkg` 等の変数は
      ルートに存在しない）。全 uv コマンドで warning が出て CI ログも汚れるので、
      `3.11` 等の固定値にするか削除する
      → **解消（2026-09-06）**: ルート `.python-version` は `3.11` に固定。
      生成物側は `template/.python-version.jinja` がルートへの symlink だったため
      ros2 の distro 別ピン（humble=3.10 / jazzy=3.12）が壊れていた — symlink を
      解除して Jinja 式の実ファイルに戻し、ルートと生成物で役割を分離。
      ros2 テスト2件の失敗も同時に解消
- [x] ~~fork の間は Issues が無効のため、週次 workflow の issue 作成ステップが
      失敗する~~ → **解消（2026-09-06）**: リポジトリで Issues / Discussions を
      有効化した（節16 フェーズ0）。workflow 側のガードは不要

## 15.6. ランナー実行監査で発見したバグ（2026-09-07）

「lint タスクが各タスクランナーで**実行**できること」を検証した（それまで
レンダー内容の assert のみで、実行は task/just のみカバー）。即座に3件発見:

- [x] **poe**: `lint` の `&&` 入りコマンドが `cmd` 型（非シェル）で壊れる
      → `_tasks.jinja` の poe 出力を、単一コマンドでも `&&` を含む場合は
      `shell` 型にする分岐で修正
- [x] **非 git ワークスペースで `uv sync` が即死**（前述の fallback_version）も
      この監査で発見
- [x] **invoke / duty**: 生成された tasks.py / duties.py 自体が ruff format
      違反（余分な空行・88超の1行コマンド）→ フォーマッタテンプレートを
      書き直し（2空行整列・複数行 ctx.run/c.run・E501 ファイル豁免）+
      `_version.py`（setuptools-scm が単一引用符で生成）を ruff 対象外に
- [x] **恒久テスト**: `test_task_runner_lint_tasks_execute`（make + poe を実走。
      invoke/duty は生成プロジェクト自身の ruff が tasks/duties ファイルを
      検査するためフォーマット面を担保）、pixi ネイティブタスクの内容固定

## 15.4. pre-commit 廃止 → GitHub Actions への移行（2026-09-07）

方針決定: pre-commit はテンプレートにも本リポジトリにも残さない。
開発フローは「**`fix` タスクで自動修正してから commit**(明示的)」に変更し、
リポジトリ衛生チェックは CI の **`_hygiene.yml`** reusable workflow に集約した。

- [x] **生成物の lint タスクを ruff 直実行に変更**:
      `lint` = `ruff format --check .` + `ruff check .`(チェックのみ・CI 安全)、
      旧 `code-fix` を **`fix`** に改名(`ruff check --fix` + `ruff format`)。
      typos / deptry / vulture / basedpyright は従来どおり `type-check` タスクに残存
      (pre-commit とは二重だった)
- [x] **`_hygiene.yml` 新設**(ルートに実体、生成物へ symlink、`{% if not ros2_pkg %}` ゲート):
      競合マーカー / 10MB超ファイル / EOF改行 / YAML パース(jinja・copier.yml 除外)/
      **gitleaks**(gitleaks-action@SHA、.gitleaks.toml 引き継ぎ)/
      **actionlint**(`docker://rhysd/actionlint` を sha256 ダイジェスト固定)/
      **conventional commits**(uvx conventional-pre-commit==4.4.0 で PR title + 各コミットを検証)/
      **nbstripout**(ipynb がある時だけ、hashFiles ゲート)/
      **REUSE**(hashFiles ゲート)/ **CITATION.cff**(cffconvert、hashFiles ゲート)
- [x] **ci.yml(ルート+生成物)** に hygiene ジョブを追加し required-checks に組み込み
- [x] **削除**: `template/.pre-commit-config.yaml.jinja`、ルート `.pre-commit-config.yaml`、
      生成 pyproject dev 依存の `pre-commit`(全 strictness 分岐)、ros2+pixi pixi.toml の
      依存とタスク、devcontainer の `pre-commit install` と `PRE_COMMIT_HOME`
- [x] **テキスト同期**: 生成 README(バッジ含む)/ AGENTS.md(check は git 無しで動く旨に
      更新 = bugs.md #4 の根本解決)/ CONTRIBUTING / PR テンプレート / zizmor.yml・
      actionlint.yaml のヘッダコメント / questions の help 2件 / ルート README /
      docs 配下(lint how-to 全面書き直し ほか)
- [x] **renovate**: pre-commit manager 削除、template renovate.json.jinja に
      「Hygiene actions」無効化ルール新設(gitleaks-action / rhysd/actionlint /
      reuse-action / cffconvert — 生成プロジェクトは copier update 経由で更新)
- [x] **tools/check_upstream.py**: core PyPI floor パターンから pre-commit を除去
- [x] **テスト**: `test_gitleaks_precommit.py`(実走)→ `test_gitleaks_config.py`(静的:
      設定リンク・SHA ピン・SealedSecrets 許容範囲が YAML スコープのまま・塩ルール存続);
      `test_template_no_precommit_hygiene_in_ci` 新設; renovate パリティテストは
      `docker://` を bare イメージ名に正規化; README バッジテストはバッジ不在を固定;
      `test_workflow_security.py` は docker:// ステップの sha256 ダイジェスト要件を追加
- [x] zizmor(生成 `_hygiene.yml` クリーン)/ actionlint(クリーン)/ REUSE lint 準拠を
      ローカルで確認、フルスイート green

## 15.5. BUG.md / bugs.md / BUGS_AND_IMPROVEMENTS.md の一括処理（2026-09-06）

3つのバグ報告ファイル + TODO 17 の未解決項目を全点検証し、再現するものだけ直した。
詳細な項目別ステータスは各ファイル内の 2026-09-06 追記を参照。

**テンプレート側で解決できず copier 本体に起因する問題は
`COPIER_UPSTREAM.md` に寄稿候補として整理した**（unsafe 拒否の UX、exit code
未ドキュメント、jinja 拡張の依存宣言、answers-file のエラー文面、
required 質問の一括報告、DirtyLocalWarning、settings trust の発見性）。
9.18.1 のソースで裏付け取り、upstream の既存 issue との重複も確認済み。

- [x] **web_api + sphinx docs が壊れる**: `docs/conf.py` / `_api.rst` /
      `reference.md` が `{{ package_name }}` を import しており、web_api
      （import root = `app`、`<pkg>` は生成されない）で docs build が必ず落ちる
      → `{{ import_pkg }}` に統一 + オフライン耐性（switcher 確認の
      `requests.get` を try/except）。テスト追加
- [x] **micropython + sphinx の組合せが壊れる**: docs_type の choices を静的化した
      副作用で sphinx が選べてしまい、import できないパッケージの autodoc で
      docs build が落ちる → render 時に zensical へフォールバック
      （`sphinx` / `zensical` internal 変数。AGPL 強制上書きと同型）。テスト追加
- [x] **`_dist.yml` の `--version` 検査が `find | head -1` 推測**:
      `version-command` input を新設し、生成側 `ci.yml` が `import_pkg` から
      正確なコマンドを渡す（web_api は CLI entry point が無いため import チェック）。
      data_science（src/ 直下にパッケージ無し）で旧ヒューリスティックが壊れる件も同時解消
- [x] **非インタラクティブ生成の根本原因**: copier は unsafe feature ありの
      テンプレートを `--trust` 無しでは**何も出力せず exit 4** で終了する。
      README の非インタラクティブ節を `--trust` 必須 +
      `uvx --with copier-template-extensions` で書き直し、トラブルシュート表付き
- [x] **全質問に default が付いていることの機械検証**
      （`test_every_asked_question_has_a_default`。`gitlab_group` だけ無かった
      — `{{ git_user_name() }}` を追加し `--defaults` + gitlab.com が通るように）
- [x] **codecov upload を push to main に制限**（`_test.yml`。PR では fork が
      token 無しで upload 失敗する noise のみ）
- [x] **`make_switcher.py` に `--ref` オプション**（gh-pages 固定の解除。
      既定は従来どおり `origin/gh-pages`）
- [x] **生成物 ruff 設定**: `DTZ007` を recommended の extend-ignore に追加
      （naive パース → `.replace(tzinfo=...)` 後付パターン。理由コメント付き）+
      `fixture-parentheses = false` を明示固定（括弧なし `@pytest.fixture` が
      テンプレートのスタイル。ruff デフォルト反転での silent restyle を防止）
- [x] **pixi how-to 新設**（`docs/how-to/pixi.md` + nav 登録）:
      `[tool.pixi.*]` in pyproject の設計、**フラットな dependencies テーブル**
      （per-package サブテーブルは `invalid character in string` エラーになる）、
      conda vs PyPI の出し分け、**PyTorch は PyPI index 指定**（conda-forge の
      ビルド欠け対策。kaggle の uv と同じ発想）、`pixi.toml` からの移行手順
- [x] **web_api + data_science コンボの `app/` と `src/` の関係**を生成物
      README（"two trees coexist" 節）と AGENTS.md（callout）に記載。テスト追加
- [x] **生成物 AGENTS.md に git init 注記**（check/lint は pre-commit 経由で
      git リポジトリ必須。publish pipeline の鶏と卵問題への回答）
- [x] **BUGS_AND_IMPROVEMENTS.md（25項目）を全点再確認**し、検証結果を同ファイルに
      記録: 10件は適用時より前に解決済み（pixi CI、vscode、concurrency、
      permissions、DLS 言及、docs 出し分け等）、#7/#17/#18/#20/#11/#8 を今回修正、
      #1/#3/#5/#6/#19/#21〜#25 は誤認または意図的設計、#9'（pyproject のコメント量）
      のみ見送り（生成物だけで完結させる教訓コメントの意図的スタイルのため）

## 16. 普及・標準化戦略（2026-09-05 調査。GitHub API で外部事実を確認済み）

「多くの人に使われる新しいスタンダードとして維持する」ための対外的な戦略。
節11(v1.0 fork解除の**手順**)・Strategy.md(内部品質の検知)とは独立の軸 ——
本節は発見可能性・比較優位・ガバナンスという対外面を扱う。詳しい根拠・比較・
一次情報源へのリンクは `docs/explanations/vision.md`（今回新設、公開ドキュメント）
に書いた。ここには実行チェックリストのみ置く。

### 現状（事実。2026-09-05、GitHub API で確認）

| repo | stars | forks | 備考 |
|---|---|---|---|
| kasi-x/python-copier-template（本リポジトリ） | 0 | 0 | fork継続中、作成2026-08-12(3週間強)、topics空、has_issues=false、has_discussions=false、homepage未設定、description が upstream 由来のまま |
| DiamondLightSource/python-copier-template（upstream） | 25 | 10 | issues 66件 open |
| pawamoy/copier-uv | 157 | 29 | 2024-02〜、単独メンテ・実績あり |
| scientific-python/cookie | 410 | 79 | Scientific Python コミュニティが背景 |
| cjolowicz/cookiecutter-hypermodern-python | 1921 | 235 | **2024-05-18 以降 push なし = 実質メンテ終了**、乗り換え先を探しているユーザー層が存在するはず |

**加えて `https://kasi-x.github.io/python-copier-template/`(と `/main/`)は現在 404**——
README・CONTRIBUTING.md が案内するドキュメントリンクが機能していない状態。
copier 公式ドキュメントには GitHub topic ベースのテンプレート発見導線があり、
`copier-template` という topic を付けるとその一覧に載る仕組みがある(現状 topics=[] で未活用)。

### フェーズ0: 今日中に終わる、コード変更不要の修正 → **実施済み(2026-09-06)**

- [x] GitHub Pages を有効化した → **初回は build_type=workflow で設定したが誤り**。
      `_docs.yml` は peaceiris/actions-gh-pages で **gh-pages ブランチ**に
      publish する方式のため、`build_type=legacy` + `source: gh-pages /` に
      訂正し、`POST .../pages/builds` で初回ビルドを手動トリガー。
      **https://kasi-x.github.io/python-copier-template/ と /main/ が 200 に
      なったことを確認(2026-09-07。長期懸案の 404 解消)**
- [x] Issues / Discussions を有効化した(`gh repo edit --enable-issues
      --enable-discussions`。fork でもオーナーなら有効化できた)。これにより
      節15 の「fork の間は週次 workflow の issue 作成が失敗する」も解消
      (workflow 側のガードは不要になった)
- [x] GitHub topics を追加: `copier-template` `copier` `python` `project-template`
      `cookiecutter-alternative` `uv`
- [x] homepage に docs URL を設定(`https://kasi-x.github.io/python-copier-template/`)
- [x] description をこのリポジトリ自身の言葉に書き直し(upstream 由来の
      "Diamond's opinionated ..." から変更)

### フェーズ1: v1.0 独立(節11の手順に、標準化の観点で以下を追加)

- [x] **detach 前にリポジトリ名を再検討して一度で決める**——現状名
      "python-copier-template" は upstream と完全同名で、detach 後も検索・引用・
      会話で混同され続ける。detach 後の rename は星・被リンクの再蓄積を
      引き起こすため、名前は detach 前に確定させる(候補の軸: 多ジャンル対応/
      Z3 検証済み/という差別化点を表す語。決めるのは開発者自身の裁量)
      → **完了（2026-10-04）**: `foundry` に確定（`ConstitutiveTemplates/foundry`）
- [x] detach 後、README・CITATION.cff・codemeta.json・新設予定の NOTICE 相当に
      DiamondLightSource 由来である旨を明記する(正統性の担保と礼儀。既存の
      `docs/explanations/why-use-template.md` が python3-pip-skeleton 由来を
      明記しているのと同じパターンをここにも適用)
      → **完了（2026-10-04）**: NOTICE 新設 + README「formerly python-copier-template」
      + CITATION/codemeta の名称統一
- [x] detach 直後、Scorecard workflow を `workflow_dispatch` で1回走らせて
      初期スコアを確認する(private/非公開状態では機能しない旨が既存 TODO に
      記載済み——public 化後の確認として)
      → **完了（2026-10-04）**: scorecard.yml は push 起動（workflow_dispatch 無し）で
      公開後の push から成功済み

### フェーズ2: 発見可能性・比較優位の明文化

- [x] `docs/explanations/vision.md` を README からもリンクした
      (新設の "Why this template" 節から。pitch の一行要約つき)
- [x] README に他テンプレートとの比較を追加した
      (vision.md の表と重複させず、要約+リンクに留める方針どおり)
- [ ] awesome-python 系リストへの PR、r/Python・Hacker News(Show HN)・
      discuss.python.org への投稿を検討する(実行タイミングは detach 後。
      fork のまま告知すると "0 star のフォーク" という第一印象になり逆効果)
- [x] cookiecutter-hypermodern-python(2024-05 以降更新停止、1900+ stars)
      からの乗り換え層を明示的なターゲットにする——比較記事 or 移行ガイドを書く
      → **移行ガイド完了（2026-10-04）**: `docs/how-to/migrate-from-hypermodern.md`
      （対比表 + fresh/adopt 2経路 + 実在の gap）。外部記事・投稿は人間タスクのまま
      （HUMAN_TODO.md Phase 3）
- [x] Strategy.md の MECE ドリフト検知フレームワーク(発生源5分類×検知タイミング
      4分類 + Z3 充足検査)を技術記事として英語で書き起こし、docs か外部ブログに
      公開する。他の copier/cookiecutter 系テンプレートに同種の説明が見当たらない
      技術的差別化の核心なのに、現状 Strategy.md 止まりで対外発信されていない
      → **2026-09-21 docs版着地**: `docs/explanations/drift-detection.md` として
      転記(5発生源×4タイミングの行列を本リポジトリの実機構で埋め、教訓5項目を
      文章化。verification.md から相互リンク、nav 登録済み)。外部ブログへの
      転載は detach 後の手順のまま(§16 の掲載タイミング規律)。あわせて
      Strategy.md のスコープ外⑤(witness台帳で実質実装済み)⑥(pre-commit廃止で
      前提消滅)に現状注記を追記

### フェーズ3: 信頼・ガバナンス(長期)

- [x] `GOVERNANCE.md` を新設した(BDFL 型の明文化、将来メンテナの追加基準、
      レビュー基準、upstream との関係)
- [ ] bus-factor 対策として、second reviewer/co-maintainer 候補を探す
      (コード変更ではなく運用課題。detach 後の方が依頼しやすい——fork のままだと
      「誰の何に協力するのか」が伝わりにくい)

### スコープ規律(やらないことリスト——これも標準化戦略の一部)

- [x] 新規 `project_type` の追加は当面凍結し、既存の組み合わせ(現状
      library/cli/web_api/data_science/online_judge×5/script/ros2/micropython
      + レイヤー)の安定化・ドキュメント・テスト強化を優先する。「対応範囲の広さ」
      は差別化点だが、伸ばし続けると kitchen-sink 化して新規参入者の意思決定
      コストが上がる——`web_django` を明確に non-goal として拒否する既存パターン
      (README 参照)を、他の際どい追加候補(GUI 質問票、他言語全般対応 等)にも
      同様に適用し、`docs/explanations/vision.md`「What this is deliberately not」
      に追記していく
      → **完了（2026-09-14 監査）**: 凍結を docs/explanations/vision.md「What this is deliberately not」（Django / フルスタック、認証・管理画面・キュー、GUI wizard、他言語）に追記

## 17. 非インタラクティブ生成の改善（2026-09-05 フィードバック）

### 修正済み

- [x] `docs_type` の choices を Jinja テンプレートから静的リストに修正
      （`questions/_common_b.yml`。動的 choices がバリデーション時に評価されず、
      `zensical` が拒否される問題を修正）
- [x] 必須質問 (`package_name`, `description`, `git_platform`) にデフォルト値を追加
      （`questions/_common_c.yml`。`--defaults` フラグで非インタラクティブ生成が
      可能になる）
- [x] README.md に非インタラクティブモードのドキュメントと例を追加

### 残課題（2026-09-06 時点。解消分は下記に降格）

- [x] 生成物の `dependencies = []` を project_type に応じて自動設定する改善
      （web_api / data_science は既に設定済み。library の空依存は
      「依存ゼロで始める」設計として維持するか、質問にするかは要検討）
      → **残り（2026-09-14 監査）**: web_api / data_science は設定済み。library の空依存を「維持」とするか「質問化」するかが未決

### 2026-09-06 に解消（節15.5 で対応。詳細はそちら）

- [x] ~~`--data-file` で指定した値が `when` 条件の評価に反映されない~~
      → 根本原因は `--trust` 漏れ（copier は unsafe feature ありのテンプレートを
      trust 無しでは生成せず exit 4 で終了）。`--trust` + `--defaults` +
      `--data-file` の組合せで `when` gating も含めて正常動作することを
      web_api / pixi / micropython 等で実測。README を書き直し
- [x] ~~`uvx copier copy` で Jinja 拡張が見つからない~~
      → `uvx --with copier-template-extensions copier copy --trust ...` が
      正しい呼び方（`_example.yml` と同じ形）。README に記載
- [x] ~~非インタラクティブ生成時に全質問の `when` 条件を評価してスキップ~~
      → 上記と同根。全質問に default があることを機械検証するテストを追加
      （`gitlab_group` に `{{ git_user_name() }}` を追加して全質問 default 完備）
- [x] ~~Pixi 依存の正しいフォーマットのドキュメント追加~~
      → `docs/how-to/pixi.md` 新設（フラットテーブル、エラー例つき）
- [x] ~~PyTorch 等の conda-forge バージョン競合のガイドライン~~
      → 同 how-to に `[tool.pixi.pypi-dependencies]` + PyPI index 指定で解説
- [x] ~~`pixi.toml` から `pyproject.toml` [tool.pixi.*] への移行ガイド~~
      → 同 how-to に移行手順を記載

## 18. テンプレート構造の簡素化・重複排除（2026-09-08 監査）

肥大化した `template/pyproject.toml.jinja`・`_tasks.jinja` と flat/src 二重ツリー、
条件分岐の3流儀混在への対処。いずれも render byte-identical 検証つきで進める
（項目13 の copier.yml 分割時と同型）。

- [x] **flat / src パッケージツリーの二重化を `{{ pkg_dir }}` 1本化する**
      → **完了（2026-09-14、bd937861）**: 14モジュール（fetcher/crawler/browser_fetch/
        spider/mcp_server/bot×3/logging_setup/__main__/__init__/agent/tools）を
        `template/{...}{{ pkg_dir }}{% endif %}/` 1本に統一、重複28ファイル削除（−176行）。
        29コンボでレンダ byte-identical を実証。wrapper が残るのは真正に置き場が違うもの
        （web_api の app/ は adopt_protect 節が無いため統一すると adopt モードの出力が変わる、
        micropython の firmware/、kaggle の src/utils）だけ
      - 現状: `<pkg>` 配下の全モジュール（fetcher / crawler / browser_fetch / spider /
        mcp_server / logging_setup / `__init__` / `__main__` / agent / tools）が
        src 版と flat 版でファイルごと重複し、100文字超の path ガードが鏡像で存在する
      - `questions/_internal.yml` の `pkg_dir` / `import_pkg` は既に配置を計算しているため、
        path 側を `template/{{ pkg_dir }}/fetcher.py` 式に寄せ、真正に置き場が違うもの
        （`app/` vs `<pkg>`、`firmware/`、`src/utils`）だけ wrapper 残しにする
- [x] **OJ 判定の3流儀を1つに統一する**
      → **完了（2026-09-14、1dbd8ecb）**: インベントリで全サイトを分類した結果、
        3構文は3つの異なる意図だったことが判明（`not online_judge`=PyPI/リリース/
        パッケージツリー領域でkaggle含むOJ全体、`not (online_judge and not kaggle)`=
        docker/vulture領域でkaggleのみ免除・CTFは対象外、リスト除外=layout/log_library領域）。
        意図ごとに命名: `oj_bare`（=online_judge and not kaggle。oj_code との差=CTFの
        有無をコメントで明記）と `no_pkg`（=micropython_pkg or oj_code、8サイトの共起を
        置換）を新設し、生式を8サイト置換。**41コンボで byte-identical**。
        生形式の再発と内部変数の逸脱を落とす guard テスト2本を新設（意図的に壊して
        検出済み）。`not online_judge`/`oj_code` スコープのサイトは意図どおり現状維持（`not online_judge` / `not (online_judge and not kaggle)` /
      `project_type not in [...]` が混在。kaggle に Docker は付くが PyPI は付かない等、
      意図か事故か判別できない）
      - `oj_bare`（= oj_code 相当）または `no_pkg`（micropython / oj_code 等）系 internal を
        新設し、docker / pypi / log_library / setuptools / setuptools_scm / testpaths /
        basedpyright-exclude の全参照を置き換える
- [x] **raw / effective 混在を排除し、template 側は effective のみ参照にする**
      → **完了（2026-09-14、212cd59c）**: 原則を template-dev.md に固定（質問の when は
        raw、render 側は effective、ゲート葉 `include_sentry`/`use_recommended_agent`/
        `include_mcp` は raw のままで正しい——派生元が無いため「直さない」旨も明記）。
        実際の混在バグ1件を修正: 生成READMEの環境変数節が `.env.example` ゲートから
        `bot_effective` を漏らし、bot レンダで `.env.example` だけが ship される状態
        （一致テスト新設）。include_mcp.when の `web_api` エイリアス参照は
        forward-reference 規則（_internal は _common_b の後で include される）のため
        不能と実証 → 既知例外として when にコメント
      - 例: `include_mcp.when` の `project_type == 'web_api' or include_web_api` と
        `mcp_effective` の `cli or web_api(effective)` の二重定義、`.env.example` ファイル名の
        raw/effective 混在、`kaggle` vs `data_science` vs `has_*` の混在使用
      - 方針: 質問の `when` は raw、render（template 本体・ファイル名・`_tasks.jinja`・
        Dockerfile・task ブロック）は effective のみ。混在箇所を洗い出して置き換える
- [x] **`layout` 除外リスト・`combinable` 三重ガードを一元化する**
      → **完了（2026-09-14、212cd59c）**: 3つの除外リストは**同じリストではなかった**
        （matrix 実測: layout は ds+web_api を排除、use_src_layout は script を排除し
        oj_ctf を再加入、log_library は no-pkg 3種のみ）——統一せず、各サイトに差分の
        理由を1行コメントし、3リストの集合を正確に固定するテストで無音ドリフトを防止。
        combinable 三重ガードは --data-file 強制リーク防止の意図設計（when=false の質問に
        も data が適用される実証テストあり）として _combo.yml に文書化、崩さない
      - `layout.when` / `use_src_layout` / `log_library.when` の除外リストを
        `needs_layout_choice` 系 internal に集約し、各 `when` から参照する
      - `include_web_api.when` + `combinable` + `has_web_api` + 各ファイルの `{% if web_api %}`
        の重なりは「`--data-file` 強制時の leak 防止に三重が必要」という現状理由を
        `questions/_combo.yml` に文書化するか、`combinable` を `has_*` に畳むか決める
- [x] **`dev` 依存ブロックの triplication を base + append 化する**
      → **完了（2026-09-14、b414588c）**: 共有依存は `{% set %}` で1回捕获し両位置に
        スプライス（recommended/full は pytest の前、none/basic は ruff の後に置かれる
        という出力順の事実を保存）、rec-only 項目が条件付き append。37コンボ +
        30,384 jinja コンテキストの差分検証で 0 不一致
      - `template/pyproject.toml.jinja` の `strictness == 'none'` / `'basic'` 分岐は
        約30行ほぼ逐語重複。`dev_base` + `{% if strictness in ['recommended','full'] %}`
        append に書き換える
- [x] **`run` prefix と python-version 三重定義を `_shared/macros.jinja` に抽出する**
      → **完了（2026-09-14、c586ed9e）**: run prefix 8箇所 + python-version 6箇所を
        `run_prefix()` / `python_version()` / `classifiers()` マクロに集約。
        13コンボで byte-identical 実証。check_upstream の Python floor ピンも
        マクロ源に向け直し（97a-followup）、macros.jinja ヘッダに権威の所在を記載
      - 現状: `run` / `run_x` / `ros_source` が `_tasks.jinja`・`README.md.jinja`・
        `Dockerfile.jinja` に分散、`requires-python` + classifiers +
        `[tool.basedpyright]pythonVersion` + ty-checkers `python-version` +
        `.python-version.jinja` が humble=3.10 / jazzy=3.12 / else=3.11 の三項を重複保持
      - `run_prefix()` / `python_version()` / `classifiers()` を macro 化し各所から import。
        `tools/check_upstream.py` の pin 対象に追加（template-dev.md の規約どおり bump 連動）
- [x] **黙り上書き（sphinx→zensical、license→AGPL-3.0）を可視化する**
      → **完了（2026-09-14、f3c92935）**: copier には pre-copy タスク段階が無く
        validator は警告できないため、生成タスクの先頭で stderr に WARNING を出す。
        2つのオーバーライドテストが「警告が出る」ことと「回答どおりのレンダ内容で
        ないとおかしい」両方を固定
      - micropython + sphinx の zensical フォールバックと memorious 選択時の AGPL-3.0 強制は
        現状 silent。ask 順で validator が書ける側は validator 化、書けない側は
        `_tasks` / CI の警告または `test_example.py` の assert（render 結果と回答の一致）で可視化する
- [x] **`git_platform` を先に聞くか `repo_url` / `docs_url` を platform 別にする**
      → **完了（2026-09-14、4a018b27）**: `repo_url` / `docs_url` を platform 条件付きに
        （gitlab.com では gitlab.com/<group>/<repo> と <group>.gitlab.io、github 側は
        byte-identical を実証）。pyproject の urls ラベルも条件化。GitLab で残る
        github 固有部分（conf.py スイッチャ、ghcr.io、scorecard バッジ等）は
        template-dev.md の「GitLab scope」節に事実として記録。質問順の変更は見送り
        （security/scorecard の effective ガードは ask 順の合図として文書済みで機能中）
      （現状: Project Details で後聞きのため `security_policy` / `scorecard` の `when` で
      絞れず `*_effective` の render 時ガードに迂回し、GitLab でも `repo_url` / `docs_url`
      が github.com 固定になる）
- [x] **`pyproject.toml.jinja` をさらに分割する**（項目13 の確立パターンで）
      → **完了（2026-09-14、beecc952）**: 1,978文字の `dependencies=` 1行ゲートを
        `_shared/pyproject-deps.toml.jinja` へ、deptry `per_rule_ignores` を
        `_shared/pyproject-deptry.toml.jinja` へ抽出。本体 330 → 325 行
      - `dependencies=` の1行20連ゲートと deptry `per_rule_ignores` 文字列組立を
        `_shared/pyproject-deps.toml.jinja` + `_shared/pyproject-deptry.toml.jinja` に抽出し、
        本体は構造のみ残す。dep 追加時の編集箇所を1箇所にする
- [x] **`_tasks.jinja` を宣言的に安定化する**
      → **完了（§22.2 W2、2026-09-13）**: 単一宣言リスト + inline guard に置換し、
        シリアライザは macro 集約。byte-identical 検証と全ランナー厳密集合比較つき
- [x] **`logging_setup` の2行 wrapper 先頭空行を解消する**
      - template-dev.md の単行 wrapper 規約に反する2行 wrapper が先頭空行を生む既知の残件。
        単行化して byte-identical 検証する
      → **完了（2026-09-14、b9aaf651）**: 3 wrapper（app/・src/・flat）を単行化。
        library / flat cli / web_api の3構成レンダー before/after diff で
        「先頭空行の削除のみ」を実証（他ファイルは不変、`_commit` のみ dirty render の
        既知アーティファクトで揺れ）

### 18.5. 述語統一の機械化（2026-09-14。§18の作業を常設ツールに）





### 18.8. 更新リハーサル: 全構成・毎晩の `copier update` 検証（2026-09-16）

テンプレート運用の最大の恐怖「updateで壊れる」を、出荷する全構成で夜間検証する:

- **`task update-rehearsal`**（`tools/update_rehearsal.py`、667c5521）: 225葉それぞれに
  ユーザーのライフサイクルを再生する——リリースタグでレンダ、ユーザー状態として
  コミット、`copier update` でHEADへ、そして test_update_path.py の契約
  （conflict残留なし / `git diff --check` クリーン / `_commit` がtargetに進行）を検証。
  workerはプロセス（copierのupdateはplumbumでプロセス全体のcwdをジャグルするため、
  スレッドだと他チェックアウトのgit操作を破壊するのを実測）。
- **baseline renderのキャッシュ**（.cache、base commit×葉×回答×copier版でキー）により
  2回目以降はmerge部分のみ。全葉＋収束比較付きで約2分20秒（jobs=8）。
- **収束マップ（reportのみ）**: update結果と新規レンダの差分を情報として出す。初回の
  全葉runで20葉が非収束と判明（bot層の葉——6.0.0にはbot質問が無いためupdateの
  マージ経路が新規レンダと異なる）。failではなく「updateが何を違うやり方でやるかの
  地図」として保持、継続調査の対象。
- **夜間workflow** `.github/workflows/update-rehearsal.yml`（SUN 05:00 UTC、weekly）。
  赤 = update経路が何かの構成で壊れた = リリース前に直すべきシグナル。### 18.7. レンダツイン: 変更の影響を証明する（2026-09-15）

「複雑さへの対処」と「調査の遅さ」は同根——どちらもレンダという巨大な出力を作り直して
確かめるから、コストが 複雑さ×葉数 で増える。根治は **証明**:

- **`task verify-delta`**（`tools/render_delta.py`、aa11c5b2）: 変更後に「どの葉が
  変わりうるか」を二層で判定する。Layer A は各葉のレンダ文脈ハッシュと
  watched テンプレートバイトの diff（保守的候補集合——条件の帰結・値・ファイル内容・
  ファイル集合の4源をすべて過剰含み込みで捕捉）、Layer B は候補葉だけ
  baseline checkout と working tree の両側でレンダし、マニフェスト（ファイル列+
  per-file sha256、`.copier-answers.yml` の `_commit`/`_src_path` は正規化）で
  byte判定する。
- **判定**: 非候補葉は「意味diffが届かない」ことで証明済み、候補葉は直接観察で
  判定。出力は "PROVEN render-identical: K候補再レンダ・byte-identical、
  225-K葉は意味diff非到達"。`--audit N` で非候補葉の無作為実レンダ照合
  （Layer A の健全性を常時監査——裏切ればツインのバグ）。
- **実証**: クリーンtree → 0候補・225/225 PROVEN・レンダ0回（0.25s、キャッシュ後）。
  意図的破壊（vultureゲートを `not oj_bare` → `not oj_code` に「簡略化」——§18が
  記録した kaggle/CTF の区別）→ **8つの ctf 葉だけが差分として検出され fail**。
  これで、これまで手作業のコンボハーネス（29/37/41コンボのベースライン diff）が
  行っていた byte-identity 証明は全域網羅の1コマンドになった。
- 文脈ハッシュは質問状態（copier.yml + questions/ + witnesses.jsonl）でキャッシュ
  されるため、本体bodyの編集では文脈パスは無料。コストは候補レンダにのみ出る。### 18.6. 成長耐性の契約（2026-09-15。複雑化を前にした機械的補強）

「これから複雑さが増す実装を加えていく」に備えて、成長時に壊れ始める4箇所を
機械契約にした:

- **tools/ の依存レイヤー契約**（cc0d3fd5）: 19モジュールを実測グラフから
  standalone / foundations / machinery / drivers / frontends の5層に整理
  （絡まりは0件、例外レジストリは空で両方向stale-proof）。新モジュールは層の
  宣言が必須で、上位importは理由つき登録なしで fail。
- **台帳の自動同期**（9e5bdeb9）: `UPDATE_TIERS=1` が tiers.json と
  test-loop.md の件数表を**同時に**書き直す（wall time は人の手のまま）。
  手編集忘れという最大の退行源を除去。冪等実測済み。
- **葉空間の予算**（16a1c61f）: `LEAF_BUDGET = 450`（現行225の2倍。加算的増分
  +76/+22 を数回許し、乗算的変更で発報）。§24.1 成長則と witness 30分
  timeout を引用するメッセージつき。意図的な拡大は定数の引上げ+wall再測定で決める。
- **質問依存グラフ**（0b11e5a3、`task question-graph`）: 118定義・205エッジの
  依存グラフを可視化し、forward-reference 規則を再計算（現行0違反を実証）。
  `--where` が新しい内部変数の**配置可能位置**を具体名で案内する——
  手動で覚えていたフラグメント順制約のプレイブック化。

拡張の手順そのものは `docs/explanations/extending.md`（拡張ランブック、398c779f）:
5つの設計問い + 13のタッチポイント（各々に検出手段がペア）+ 利用ツール一覧。

§18 #2/#3/#4の手作業（インベントリ → 分類 → 命名 → guard）を、恒常的な機械にした
（e84772c2 + 5a23be8b + b2bc53ec。owner指定: 同一性による統一は機械的に、分類は常に
木構造で、特殊ケースには発火数を、近道（A or B or X）は体系として用意する）:

- **`tools/predicates.py`**（`task predicates`）: render+質問表面の**676条件サイト**
  （質問when 51 / bool内部変数 44 / ファイル名ゲート 125 / 本体if 452 / タスク 4）を収集し、
  225葉それぞれで **copier自体をオラクルに**評価（test_when_model の private-API パターン）。
  出力: invariants.yml の分類木（行ごとの葉数つき）、内部変数ごとの定義/参照/発火数、
  59個の葉空間同値クラス、統一候補、ショートカット提案、評価不能サイトの分離。
- **guard テスト**（`tests/test_predicate_classifier.py`、0.95s）: render側サイト × 内部変数の
  **無条件同値**をZ3自由空間で証明し、同値なのに内部変数を参照しないサイトは
  `DECLARED_EQUIVALENCES`（理由つきレジストリ）に無い限り fail。現在の違反は
  has_*/エイリアスの3組（§18#4が意図設計と記録したもの）のみを理由つき登録。
- **when_model の実バグ修正**: `_eq` が未モデル比較のフォールバック真偽値を
  パーサ位置で名前留めしていたため、同一比較が1式に2回出ると独立の未知数になり、
  同値な述語が「異なる」と判定されていた。オペランドからの命名に修正
  （差分テストは影響なし）。

初回実行の発見（判定はownerの仕事）: 葉空間での統一候補95件（大半は gate 既定値の
偶然一致で問題なし）、命名候補8件（`project_type != 'ros2'` 9サイト等）、
平坦化候補18件（`sphinx`/`mcp_effective`/`bot_slack`/`bot_line`/`ros2_cpp` 等の
225葉で一度も分岐しない内部変数——葉空間が広がるまでの既知状態）。

## 19. テスト・CI の高速化と確実性（2026-09-08 監査）

> 2026-09-13 追記: `task test-fast`（venv/network を外す）/ `task test-heavy`（重い方のみ）を追加した（節22 §W9）。
> marker 化とレンダ結果キャッシュ、CI 側の fast/heavy 分割は未着手で下記は有効。単一ケースの調査は
> `task batch CLI_ARGS="--only X --prepare --shell"`（数秒）で pytest を経由しない。
>
> 2026-09-13 再監査: テストを**書く側**の簡素化・witness 実行・MCP 整備は**節23** に分離した
> （本節は CI コストの話に限定。marker の負債と `test-loop.md` の乖離も節23 が持つ）。

- [x] **uv / graphviz / uvx ツールのキャッシュを入れる**
      → **完了（2026-09-14 監査 + 実装）**: setup-uv の enable-cache / `.venv` の
        actions/cache / uvx 冷起動（uv wheel cache）は対応済み。graphviz の deb キャッシュは
        **入れて壊して外した**（162e44d0: apt が root 所有の `.apt-cache/partial` を作り、
        非特権の cache save が EACCES で失敗 → 毒されたエントリが以後毎回復元。graphviz は
        数秒で入る）。今日その残骸（使われていない `APT_CACHE_WEEK` ステップ）を削除し、
        再導入しない理由を `_docs.yml` のコメントに残した
      - `astral-sh/setup-uv` の cache 有効化 + `.venv` の `actions/cache`、
        docs run の `apt-get install graphviz` 常駐化、hygiene run の
        `uvx conventional-pre-commit / nbstripout / cffconvert` 冷起動のキャッシュ
- [x] **CI を fast / heavy に分割する**
      → **完了（2026-09-14 監査）**: .github/workflows/ci.yml — job 単位の docs-only ゲート（`changes`）と PR/push の `test` = test-fast、夜間の `test-heavy` / `test-randomly`
      - PR 毎は `test_machine_gate` / `test_copier_structure` / `test_qa` /
        生成 docs / gitleaks / lint の fast のみ、heavy（`test_example` / typecheck）は
        `main` / nightly または `paths:` フィルタに。`pytest -m "not slow"` markers +
        `make_venv` 系の `--dist loadfile` グルーピング、事前 sync 済み base venv 再利用を検討
- [x] **`timeout-minutes` を全 workflow に付ける**（例: test 60 / docs 20 / hygiene 10）、
      matrix 復活時は `fail-fast`、タグ時の `_docs.yml: sleep 60` を `concurrency` で解消する
      → **完了（2026-09-14 監査）**: timeout-minutes を全 workflow に付与（.github/workflows/_docs.yml:19 = 20、_hygiene.yml:10、_test.yml、ci.yml）。`_docs.yml` の sleep 60 は concurrency で解消
- [x] **network 系テストの扱いを見直す**
      → **完了（2026-09-14 監査 + 実装）**: ローカル diff 化（tests/test_update_path.py）と
        hypothesis の実使用（tests/test_adopt_stateful.py）は済み。最後に残っていた z3 の
        `importorskip` 黙り skip を全廃（tests/test_when_model.py / tests/test_copier_structure.py /
        tests/test_witness_matrix.py の計 7 箇所）。z3-solver は pyproject の dev 依存なので、
        欠落は「非対応環境」ではなく壊れた環境 → 素の `import z3` で落とす
      - `test_example_repo_updates`（example リポジトリの clone + `copier update` + diff）は
        ローカル `--vcs-ref=HEAD` diff に置き換えるか `scheduled-check` 専用に移す
      - `z3` の `importorskip` 黙り skip をやめ、必須化または skip 件数を assert する
      - `hypothesis` は現状 `tests/` でゼロ使用（deptry 除外で延命）。property test を
        `_tokenize_when` / questionnaire parser に書くか、依存から外すか決める
- [x] **setup 重複を composite action 化する**（runner 分岐の方は 2026-09-16 に完了）
      - `_tasks.yml` / `_test.yml` / `_docs.yml` / `_dist.yml` の
        checkout(fetch-depth:0) + setup-uv/pixi/poetry + setup-task/just 約30行を
        `setup-runner` composite action に抽出する（**未着手**。この一式は
        `template/.../workflows/` の symlink で生成物にも入るので、変更の確認は
        CI 実走が要る）
      - ~~`_test` / `_docs` が `task/just/make/poe/pixi` のみ対応で `invoke/duty` が
        `Unknown task runner` になる分岐漏れを修正（template 側に loud-fail か対応追加）~~
        → **完了（2026-09-16）**: `_test.yml` / `_docs.yml` の `case "$TASK_RUNNER"` に
        invoke/duty を追加（`_tasks.yml` と同じ poetry.lock 分岐つき）。invoke/duty を
        選んだ生成物の CI が実行時に `Unknown task runner` で落ちる実バグで、
        render では見えない。input description の列挙も追随
      - ~~`test_task_runner_just_works` 並みに `invoke` / `duty` の実走テストを追加する
        （poe `cmd &&` / make tab バグはまさに未実走から漏れた）~~
        → **完了**: `test_test_task_executes_on_invoke_and_duty`（heavy+network。
        生成物で `uv run --locked invoke|duty test` を実走。`test` は `_test.yml` が
        毎 push で叩くタスク）。再発防止として
        `test_every_runner_switch_handles_every_task_runner_choice`（fast）が
        3 workflow の switch を questionnaire の全 choice + pixi と照合し、
        loud-fail が残っていることも検査する
- [x] **未検証の組合せ・経路を埋める**（2026-10-04 棚卸し → `notes/DESIGN-ci-coverage.md`）
      - テンプレ本体 CI は 3.11 / ubuntu-latest のみ。生成 matrix（3.11-3.14）/
        windows-macos / pixi・poetry venv 経路は render のみ
      - `torch` 系 render（data_science / kaggle）を typecheck 除外のままにしない
        （重いなりの nightly 化等）。`ros2-cpp`（pyproject 無し）の lint/typecheck/fmt 除外も整理
        → torch は **解決（witness full tier）**: data_science 葉が full tier の
        実行サンプルに入り、torch 依存 sync 込みで type-check まで実走する
        （invariants.yml `project_type=data_science` 行の tier why 参照）。
        ros2-cpp は **2026-09-21 部分解決**: pyproject 無しで孤立していた
        `uv.lock` / `pyproject-fmt.toml` を `not ros2_cpp` ゲートで除外
        （test_example_ros2.py がピン）。lint タスクは ruff の Python のみ
        選択で自ずと no-op、CI tier スキップは test_generated_lint
        EXTRA_PATHS の宣言どおり
      - `tools/check_upstream.py` の network モード、`generate_license_template.py`、
        `_dist` / `_container` / `_pypi` / `_release` / `_example` workflow 群の未実行を
        いずれかの CI で叩く。`example-answers.yml` に `use_recommended_agent` 経路が無い点も補う
        → 2026-09-21 ローカル実走: check_upstream network モードは「Template
        pins are up to date」、generate_license_template は zero drift。
        `use_recommended_agent` は **解決**: example は data_science で質問が
        出ないため key を入れると派生 fixture の `agent_scaffold` を誤反転
        させる — 意図的な不在として test_answer_fixtures.py の
        test_agent_gate_stays_absent_from_the_example_fixture がピン済み
        （経路自体は cli witness 葉 + test_example_layers で担保）。残りは
        workflow 群の CI 実走（着手条件: push 後の run 観察）
      - `audit` タスク（network のため `check` 外し）は木曜 root audit 以外の検証が無い。
        schedule 検証の有無を明記する
        → **解決**: dependency-audit.yml 冒頭コメントが「週次 schedule +
        workflow_dispatch のみが検証経路」を明記済み。Taskfile の audit
        desc にも 2026-09-21 同旨を追記
      - **2026-09-21 act 実走の追加教訓**: `act push -W ci.yml --job lint`
        （ローカル Docker、リユーザブル workflow は act がサポート）で lint
        ワークフローを実走できた。生成物の typos が ethics 例コードの
        `fpr` 識別子を誤検知する実バグを検出（テンプレ側 typos も同様に赤 —
        修正は fpr/fnr を両側の typos ignore リストへ追加する方式に落ち着いた。
        rename から ignore へ差し替えた経緯と `-w` の識別子書き換え挙動は
        docs/how-to/static-analysis.md の「typos: the spellchecker that
        rewrites code」節に文書化）。CI の
        workflow_call への引数渡し・キャッシュ挙動は GitHub と差異があるため
        「初回実走確認」は引き続き push 後の run 観察で行う

## 20. Docs・導入UX の改善（2026-09-08 監査）

> 2026-09-13 追記: 導入の実務（モード判定・衝突一覧・加算マージ・対話確認・ロールバック）は
> `tools/detect.py` / `tools/adopt.py` として実装し、`docs/how-to/{detect,adopt}.md` と
> `docs/tutorials/adopt-existing.md` を実測ベースに書き直した（節22）。
> 2026-09-16 追記: README の TL;DR と wrapper CLI（`python-copier-template new` +
> `presets/`）は着地済みで、Features/mermaid の drift 解消（§22.2 W5）・孤児ページ
> （下の [x] 行）・生成 README の堅牢化・create-new の runner 分岐も完了。節20 の
> `- [ ]` は残っていない。

- [x] **コピペで通る導入導線にする**（2026-09-09 更新: `--with` は不要になった。
      copier-template-extensions 依存を排除したため残りは `--trust` / `--vcs-ref` の2 flag）
      → **完了（2026-09-16 監査）**: 下の3つの残りはすべて解消済みを実測で確認
      - ~~tutorials/installation.md に `--with` を足す~~ → 不要（依存排除で解消）
      - ~~`tutorials/adopt-existing.md:28` の skeleton 経路と :43 非 skeleton 経路の不整合を解消する~~
        → **解消済みを確認**: 例の2行は 2026-09-13 の書き直しで消え、現行は
          skeleton 経路（`--vcs-ref=6.0.0` で detach タグから adopt → `copier update`）と
          非 skeleton 経路（`--data existing_project=true` + `--skip`）が別節に分かれ、
          冒頭の注記（URL 版は最新タグを展開）と矛盾しない
      - ~~`--vcs-ref=main` の理由説明3箇所の矛盾を解消する（README は「v1.0 で re-tag 済み」、
        adopt-existing は「v1.0 未到達で必須」）。単一の version-status 注記に集約し TODO-11 漏れを消す~~
        → **完了（§22.2 + 2026-09-16 実測）**: `--vcs-ref=main` は docs/README から消滅
          （grep で 0 件）。残るのは「URL 版は最新タグを展開」「`--vcs-ref=6.0.0` は exact pin」
          「`--vcs-ref=HEAD` は作業ツリー」の3用途だけで、`template-dev.md` の
          「Documented generation commands must run without `--vcs-ref`」が規約として固定
      - ~~2 flag（`--trust` / `--vcs-ref`）を隠す wrapper script / alias を検討する~~
        → **完了**: `python-copier-template new`（`tools/cli.py`、`--trust` 内蔵で
          release 選択・create/adopt 判定・preset 適用まで行う）が wrapper そのもので、
          README の TL;DR がこれを第一の導線として提示。`--vcs-ref` は
          「exact pin したい人」だけが触る
- [x] **欠落・孤児ページを解消する**
      - ~~生成 README が link する `{{docs_url}}/how-to/run-container` に対応する
        `docs/how-to/run-container.md` を書く~~ → **誤認と判明（2026-09-14 実測）**:
        テンプレには `template/docs/how-to/{% if docker %}run-container.md{% endif %}.jinja`
        が既存し、README のリンクも同じ `{% if docker %}` 節内にあるため
        「リンクが出る＝ページが生成される」で整合。docker+docs の実レンダーで
        ページ実在とリンク解決を確認（nav 非掲載の孤児ページとして build はされる）。
        docs 無効時は `Dockerfile)` への弱代替に落ちるのも意図どおり
      - ~~`docs/explanations/structure.md` の孤児を `explanations.md` index に登録する~~
        → 登録済みを確認（zensical.toml nav の "Structure"）
- [x] **README Features / mermaid と questionnaire の drift を解消する**
      → **完了（§22.2 W5 + 1981f367）**: README は `tools/gen_docs.py` が生成し、
        機能カタログは `docs/reference/features.md` へ分離。README は 120 行の
        エントリポイントに（§22.5 #5 も解消）。mermaid の CTF / scraping 分岐も導入済み
- [x] **生成ドキュメントを堅くする**
      → **完了（2026-09-16、README 側の3点を実測で確認）**: 下の3つの残りを修正
      - ~~生成 `CONTRIBUTING.md.jinja`（30行・外部 how-to URL 依存・`_commit.split` pin 脆弱）を
        `AGENTS.md` と同じコマンドブロック内蔵型にし、offline でも作業可能にする~~
        → **完了（2026-09-14、031be19b）**: Common commands 節が `_tasks.jinja` の
        `_t.agent_cmd_specs` モデルから導出（AGENTS.md と同一ソースで乖離不能）。
        `_commit.split` pin とテンプレ how-to への link は廃止し、docs ルート URL に
      - ~~生成 README の `<details> Platform-specific setup` の Linux/macOS vs Windows
        同一コマンド並列（noise）を差分化または削除~~ → **完了**: web_api は
        `uvicorn` が全 OS 同一なので表をやめて1コマンド、他は「Windows は `py`」と
        差の理由を1行で述べる表に（`<details>` 直後の余分な空行も除去）
      - ~~`**pkg** is a Python package that ...` プレースホルダの ship しやすさに対処~~
        → **完了**: この行を削除（タグラインが既に `description` を出している）。
        NOTE は「tagline はあなたの `description` 回答、下の features を置き換える」と
        実在のプレースホルダ（Features 3行）だけを指す文に
      - ~~docs 無効時の `See ... (.github/CONTRIBUTING.md)` 弱代替を手当てする~~
        → **完了**: ラベルとリンク先を一致させた
        （`See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for ...`）。GitLab 版が
        `.github/CONTRIBUTING.md` を ship しない件は `template-dev.md` の
        GitLab スコープ節に既知の残りとして明記済み（full parity は別プロジェクト）
      - 実測: `copier copy --vcs-ref=HEAD` で web_api / cli / gitlab+docs-off の
        3構成を render して確認。fast+meta（891 passed）と heavy（47 passed）は緑
- [x] **質問票の小粒改善**
      → **完了（2026-09-16）**: 残っていた3点を処理
      - ~~`project_type=web_django` の罠選択肢（選ぶと abort）を choices から外し、文書ポインタにする~~
        → **完了（§22.2 W6）**: choice・help・`_tasks` ガードとも除去済み
      - ~~`license` help の40行 SPDX ダンプを端末向けに短縮（全文は docs 参照）~~
        → **完了（2026-09-14、75f5595a）**: choices を素の SPDX ID に（保存値は
          従来から ID なので answers 互換・順序も同一）。名称は
          choosealicense.com と docs/reference/questionnaire.md を参照
      - ~~`example-answers.yml`（全 gate-off 網羅 fixture）を `create-new.md` +
        `reference/questionnaire.md` から non-interactive 起点として link する~~
        → **完了**: `create-new.md`（preset 節と raw copier 節の2箇所）と
          `reference/questionnaire.md` の冒頭注記から repo の blob URL へ link。
          何をする fixture か（全 gate off = 詳細質問を全部答える / data_science base /
          CI が render する当のもの）も1文で書いた
      - ~~`create-new.md` の commit 手順 `uv sync` 固定を runner 対応に
        （`uv sync` / `pixi install` / `poetry install` / ros2 / micropython 分岐）~~
        → **完了**: 回答→install コマンドの表（uv / poetry / pixi / ros2+apt の
          `rosdep install` / micropython の `--target typings`）に置換し、
          以降の shell 例は uv を既定として残した。コマンドは生成 README の
          Installation 節（`_tasks.jinja` 由来）と同じ語彙
      - ~~README 先頭に5行 TL;DR quickstart + prerequisites（uv / git init）を置く~~
        → **確認済み（既存）**: README.md の `## TL;DR` が prerequisites（uv / git）と
          CLI 1行 + `uvx copier copy` 1行を提示済み

### 修正詳細

#### Issue: docs_type バリデーション問題
**症状**: `--data-file` で `docs_type: zensical` を指定すると
`ValueError: Invalid choice for 'docs_type': 'zensical' is not in ['README', 'sphinx']`
エラーになる。

**原因**: `choices` に Jinja テンプレート (`{%- if micropython_pkg %}...`) を使用すると、
バリデーション時に Jinja が評価されず、一部の choices しか認識されない。

**修正**: `choices` を静的リスト `[README, zensical, sphinx, great-docs]` に変更。
micropython プロジェクトでは sphinx が不要な制限は、テンプレート側で対応
（`template/{% if docs %}docs{% endif %}.jinja` で条件制御）。

#### Issue: 必須質問のデフォルト値不足

**症状**: `--defaults` フラグを使用しても `package_name`, `description`,
`git_platform` が "required" エラーになる。

**原因**: これらの質問に `default` が設定されていないため。

**修正**: 各質問にデフォルト値を追加:
- `package_name`: `my_package`
- `description`: `A Python project generated from python-copier-template`
- `git_platform`: `github.com`

## 21. copier 本体への機能提案・fork 運用（2026-09-08 新設）

`notes/COPIER_UPSTREAM.md` + `notes/upstream-drafts/`（報告済み9件・パッチ2本凍結）は
そのまま残し、*新規*の機能提案と fork 作業場は `copier-fork/` に集約する。
二重管理にしない: 既報9件の再記述は `copier-fork/` に持ち込まない。

- [x] **`copier-fork/` 作業場を新設する**（2026-09-08）
      - `copier-fork/README.md`（hub: 新旧二拠点の整理・非目標・workflow）
      - `copier-fork/FEATURES.md`（新規機能 F1〜F7 + Research。重複する既報9件は拡張参照のみ）
      - `copier-fork/patches/README.md`（命名 `<area>-<slug>.patch`・作成/検証手順）
      - `copier-fork/scripts/{fork-setup,sync-upstream,verify-patch}.sh`
       （fork 作成・upstream 同期・`git apply --check` 検証。`bash -n` 済み）
      - 非目標の明記: upstream コードの vendoring なし（patch は quoted context のみ）、
        生成物への混入なし（`template/` 外のため `copier.yml` 除外不要）
- [x] **fork を作成し、F3（missing 一括報告）から着手する**（2026-10-04）
      → **着地**: `kasi-x/copier` fork 上に `f3-missing-batch` ブランチを push 済み
        （base upstream/master = 9.18.2 系）。`_ask` で missing を収集して一括
        `UserMessageError` に変更、upstream tests（test_copy/test_cli/test_config/
        test_answersfile = 323 passed）緑。patch は
        `copier-fork/patches/cli-missing-answers-batch.patch` として保存、
        `verify-patch.sh` で clean apply 確認済み。PR 投稿は下項どおり人間作業
      - `copier-fork/scripts/fork-setup.sh` で fork（先方慣例ブランチは `master`）。
        ベースラインは copier 9.18.1（本リポジトリ `.venv` 版）。以降は
        `sync-upstream.sh` で追従し、FEATURES.md の行番号参照を更新する
      - 着手順序（小→大）: F3 → F5 → F6 → F1/F2/F4/F7（Discussion 先行）。
        文言系（F3/F5）は既報1/2/4 の PR と同型の単発 PR として出しやすい
      - PR 前に upstream `CONTRIBUTING.md` 通りに該当テストを回す
        （F3 なら answers 系、F5 なら VCS 系）。`verify-patch.sh` で事前検査
- [ ] **投稿は手動で行う**（copier の `AI_POLICY.md` 要件。エージェント投稿禁止）
      - 草稿は貼らず自分の言葉に整える。`gh` コマンド例は `notes/COPIER_UPSTREAM.md`
        「投稿手順」節を正とする（`copier-fork/` に複写しない）

## 22. 劇的改善：実装済みの道具と残タスク（2026-09-11 監査 → 2026-09-13 更新）

委託用の詳細仕様（Target / Change / Acceptance / 所有権 / wave / 共有コントラクト §C1〜C9）は
**`notes/PLAN-improvements.md`** を正とする。この節は「何が動いていて、何が残っているか」を持つ。

動機（実測・再掲）: 最新タグ `5.4.0` は inherited upstream の内容で fork の機能を 1 つも含まず
（`git show 5.4.0:copier.yml` に fork 機能 0 回、HEAD は 69 commits 先）、既定の `copier copy` は
`Invalid choice for 'docs_type': 'zensical'` と `Question "author_name" is required` で失敗する。
全テストが `vcs_ref="HEAD"` 固定のためこの欠陥を検出できない。加えて実行検証は 10 構成のみ
（質問空間 ≳378）、`.github/workflows` に `timeout-minutes` が 0 件。

### 22.1 実装済み: テンプレートを扱う道具（`tools/`）

| 道具 | 何をするか | 入口 | テスト |
|---|---|---|---|
| `tools/detect.py` | 対象のモード判定（`fresh` / `adopt` / `update` / `foreign`）、既存資産の棚卸し、`COLLISIONS`（= `skip`）、実行可能な adopt コマンドの印字。保護条件は `template/` のパス名条件から**実行時導出**（HEAD と作業ツリーの差でも正しい）。形状質問は推測しない（SPEC §12） | `task detect DIR=... CLI_ARGS="--json"` | 22 |
| `tools/adopt.py` | **トランザクション付き adopt**: 計画 → 対話確認 → 適用 → 検証 → 破れれば全体ロールバック。`--ref` は「最新タグが同じ質問集合を持つときだけタグ、でなければ既定ブランチ」を動的判定 | `task adopt DIR=... CLI_ARGS="--dry-run"` | 22 |
| `tools/pyproject_merge.py` | `pyproject.toml` への加算マージ（deps / `[dependency-groups]` / `[tool.*]`）。既存値は不変、tomlkit でレイアウト保持、ビルド・環境テーブルは対象外 | adopt から | 15 |
| `tools/file_merge.py` | `.gitignore` / `Makefile` / `justfile` の追記、`Taskfile.yml`（`tasks:` が最後のキーのときだけ承認つき追記）、既存 `ci.yml` がある場合の `copier-ci.yml` 併置 | adopt から | 12 |
| `tools/batch.py` | JSONL の生成リクエストを順に実行して**判定**（`expect` / `commands`）。`--prepare` で環境構築、`--shell` で調査ループ | `task batch FILE=... CLI_ARGS=...` | 15 |
| `tools/questionnaire.py` | 質問票をデータとして読む（`!include` 解決済みの実質問順、`choices_template` 対応、`_` 設定は分離） | CLI / MCP | 9 |
| `tools/mcp_server.py` | 上記を MCP tool として公開（`template_status` / `list_questions` / `inspect_project` / `adopt_project` / `render_project` / `list_batch_requests` / `run_batch`）。stdio の stdout を汚さない（render は fd 1→2） | `task mcp` | 12 |

テスト 3 段速も導入済み: `task test-fast`（venv/network を外す）/ `task test`（フル）/
`task batch CLI_ARGS="--only X --prepare --shell"`（1 ケース）。詳細は `docs/how-to/test-loop.md`。
関連 docs: `docs/how-to/{detect,adopt,batch,test-loop}.md`、`docs/tutorials/adopt-existing.md`。

### 22.2 残タスク

> テスト記述・実行・MCP の具体差分は**節23**（2026-09-13 監査）に切り出した。
> 以下の W3 / W9 はそのまま有効（節23 は再掲しない）。

- [x] **W0: fork detach と既定経路の是正** → **実施済み（2026-09-13、ユーザー承認後に実行）**
      - 継承タグ 38 個を**ローカルとリモートの両方で削除**（`git push origin --delete <38 tags>`、
        remote tags 0 を実測）し、HEAD に `6.0.0` を 1 つだけ作成して `git push origin main 6.0.0`。
        初回の 6.0.0 は自前 CI の lint が赤だったため、type-check 修正後の commit（CI 全ジョブ緑）へ
        **force-update で付け替え**（作成直後・外部 consumer なしを確認。remote は `6.0.0` 1 本のみ）
      - `--vcs-ref` 前提の記述を撤去: README / docs/tutorials/{create-new,adopt-existing}.md /
        docs/explanations/template-dev.md / docs/how-to/{adopt,test-loop}.md / copier.yml の adopt
        `_tasks` メッセージ / 生成 README の update 行（`uvx copier update --trust --defaults`）。
        `--vcs-ref` は「明示 pin」と「ローカル反復（HEAD）」の説明だけに残置
      - `tests/test_generation_docs.py` の「全ドキュメントは ref を pin せねばならない」2 テストを削除し、
        **引数なし `copier copy` が fork の質問票を出す**挙動テスト 1 本に置換 → 緑を実測
      - 実測: `copier copy --vcs-ref=6.0.0` で生成した project の `_commit: 6.0.0`、
        続く `copier update --trust --defaults`（ref 未指定）が exit 0 で "downgrading" を出さないこと
- [x] **W1: `copier update` 適合マトリクス + 質問票 diff ガード** → **実施済み（2026-09-13）**
      - `tools/check_questionnaire_diff.py`: 最新リリースタグ（6.0.0）の解決済み `copier.yml` と作業ツリーを比較し、
        質問の削除・改名・既定変更に `_migrations` が無ければ `[MISSING MIGRATION] <name>` で exit 1
        （`when` 変更は報告のみ）。scratch repo で rename → exit 1 / `_migrations` 追記 → exit 0 を実測
      - `tests/test_update_path.py`: example-answers + FAST_PATHS 代表 3 件を**リリースタグで生成 → HEAD へ update**、
        conflict 残渣なし・`git diff --check` クリーン・`_commit` 記録を検証（旧 ref レンダはキャッシュ）。5 passed
      - ネットワーク依存の `test_example_repo_updates` を削除（同じ経路をオフラインで被覆）
      - `.github/workflows/update-path.yml`（PR + workflow_dispatch、`timeout-minutes: 30`）
- [x] **W2: タスク定義の宣言的モデル化**（byte-identical 検証つき）
      → **実装済み（2026-09-13、sub agent）**: 単一宣言リスト + inline guard
      （mutation 廃止）、`cmd`→`run` リネーム、poe の文字列スニッフィング廃止、
      AGENTS.md コマンド表をモデルから導出。byte-identical 検証は 23 レンダー
      1684 ファイル + strictness none/basic 4 ケース 316 ファイルで全ハッシュ一致。
      test_task_runners は全7ランナーの厳密タスク集合比較 + make/poe 実走に強化。
      残す polish: シリアライザの macro 集約 → **完了（2026-09-13）**: 7 ランナー分の直列化を
      `_tasks.jinja` の macro に集約し、runner テンプレートは macro 呼び出し 1 行に。
      `test_copier_structure` のスキャナに macro 名/引数を登録。byte-identical は
      baseline(HEAD worktree) vs 作業ツリーの 28 レンダ 2057 ファイルでツリー hash 一致を実測
- [x] **W3: Z3 の証人で質問票の全葉を実行検証**（エンジンは `tools/batch.py`、fast/heavy の 2 tier）
      → **実施済み（2026-09-13）**: `tools/z3_witnesses.py` が既存 Z3 エンコーダ上で blocking clause により
      葉空間（全ゲート on または 1 つ off × at most 1 include × oj_kind）を列挙 → **205 葉・全て一意**
      （`tests/matrix/witnesses.jsonl`）。`tests/test_witness_matrix.py` は fast tier（205 render + 生成 ruff）を
      10s、full tier（宣言した 8 葉サンプル: uv sync + pytest + basedpyright + docs）を実行し、
      `tests/matrix/witnesses.json` に葉ごとの tier/result/source を冪等に記録（`tier: none` の W4 フック付き）。
      guard-the-guard（scratch で `when` を false 化 → 未到達 9 葉を名指しして fail）も実測
      - **成果**: full tier が実欠陥 3 件を検出 → 修正済み（micropython の basedpyright include / OJ の docs /
        cli+agent の reportAny）。修正後は 205/205 pass
      - 未実施の残り: 既存テストの「文言固定 assert」監査 → **完了（2026-09-13）**: 15 モジュールで
        assert 152 行削除 / 128 行追加、テスト関数の削除ゼロ。repo ソースの文字列 pin・help/docstring/
        log の文言・`pytest.raises(match=...)`・substring での YAML/TOML/JSON 読み・形状 pin を除去し、
        挙動/境界/不変条件/実エラー/生成物契約（存在・パース結果・実行結果）・byte 不変・冪等に置換
- [x] **W4: サポートマトリクスの宣言と長尾の整理** → **実施済み（2026-09-13）**
      - `support.yml`: full tier が実行する 8 組合せ（ledger の `source: full`）を `supported`、
        長尾（make/poe/invoke/duty の非実走タスク、poetry、loguru/picologging、ty、ros2、
       非 AtCoder の judge、layer 葉、gate-off 分岐）を `best_effort` として根拠付きで宣言
      - `docs/reference/support.md` は `tools/gen_docs.py` の生成物（README は要約ブロック）。
        `tests/test_support_matrix.py` が「supported は ledger で pass」「生成物と一致」
        「`tier: none` には reason 必須」を担保。`--check` = 9 blocks in sync
      - ledger の降格は行わない（全葉が fast tier で実行済み。`tier: none` は「実行を止める」将来用）
- [x] **W5: ドキュメントを質問票から生成** → **実施済み（2026-09-13）**
      - `tools/gen_docs.py`: `tools/questionnaire.py` のモデルから README の Features 領域リスト・mermaid・
        task runner 行と `docs/reference/questionnaire.md` の 4 ブロックを生成（`--check` / `--write`、
        マーカー方式で手書き散文は不変）。`--check` = 「7 generated block(s) in sync」exit 0
      - `Task (default)` の矛盾を解消（既定は `task_runner.default`）、mermaid に CTF / scraping /
        license_check 分岐が入り、mmdc で構文を実測。`tests/test_generated_docs_sync.py` がドリフトを fail させる
      - support 表は `support.yml` がある時だけ生成（W4 の入力）
- [x] **W6: 導入のワンコマンド化** → **実施済み（2026-09-13）**
      - `tools/cli.py new <dir> [--preset NAME] [--ref REF] [--dry-run]`: `tools/detect.py` でモード判定し、
        fresh は 1 回の render、adopt は `tools/adopt.py` のトランザクションに委譲（rollback と承認ループを再実装しない）。
        `--ref` 既定は最新リリースタグ（6.0.0）、`--preset` は `presets/*.yml` を answers として使う
      - `presets/` に library / cli / web-api / data-science / ros2 / micropython / online-judge-atcoder の 7 種。
        全プリセットが非対話で exit 0 を実測
      - `web_django` の罠を除去（choice・help・`_tasks` ガード）。copier は choice 検証で先に落ちるため guard は到達不能。
        `[project.scripts]` 追加に伴い `packages = ["tools"]` を明示（無いと console script が解決しない）
      - docs/tutorials/{installation,create-new}.md をワンコマンド導線に更新（生の copier は上級者向けとして残置）
- [x] **W7: CI 衛生**（全 workflow に `timeout-minutes`、setup-uv / .venv / apt / uvx のキャッシュ、
      → **実装済み（2026-09-13）**: timeout-minutes 18ファイル付与、setup-uv enable-cache、
      .venv actions/cache、graphviz deb キャッシュ(※)、`sleep 60` → concurrency 置換。
      ※graphviz deb キャッシュは **自己毒化するため撤去**: apt が `.apt-cache/partial` を
      root で作り、非特権のキャッシュ保存が EACCES で落ち、毒されたキャッシュが以後の
      全ランに復元され docs ジョブを連鎖的に赤化(2回連続で docs 失敗の実害)。
      graphviz install は数秒のため cache なしで運用。
      `_docs.yml` の `sleep 60` を `concurrency` 化）
- [x] **W9: テスト実行コストの削減**（marker 化 + レンダ結果キャッシュ）→ **実施済み（2026-09-13）**
      - marker `heavy`/`network`/`fast`/`full`/`slow` を root pyproject に登録。venv を作る 21 テスト
        （test_example）+ test_generated_typecheck 全 6 件 + test_task_runners の実走 3 関数（6 ノード）に
        `heavy`（+`network`）→ 実測 465 件 = fast 435 + heavy 30（和を検証）
      - `task test-fast` = `-m "not heavy"`、`task test-heavy` = `-m heavy`。repo の ci.yml は push/PR で
        fast tier、`schedule: cron 0 3 * * *` で heavy tier（`timeout-minutes: 120`）
      - `tests/render_cache.py`（新規）: (answers, template 指紋) をキーにセッション共有レンダ。
        `test_generated_lint` + `test_pyproject_fmt` で 132 テスト・被覆不変のまま 10.7s → 3.6s（2.78x）
      - **罠**: `tests/conftest.py` は template payload への symlink なので、ここに置くと生成物に
        copier import が漏れる（下記 22.3）。キャッシュは repo-only のモジュールに置いた
- [x] **W-P の残り**: `_load_questions` の `tools/questionnaire` 委譲 → **実質完了と判断（2026-09-09）**。
      現行の `_load_questions` は copier ネイティブの `load_template_config`（!include 解決の
      権威あるローダ）を使う 12 行の薄い実装で、委譲先の `Question` モデルは
      validator 等の未知キーを落とすため Z3 ガードの入力を劣化させる。`tools/questionnaire.py`
      --json は **109 問**（108 + existing_project）を正しく数え、JSON/MCP 層として役割分担。
      読み取り側は実装済み
- [x] **W10（新）**: `tasks.py` / `duties.py` への追記 → **実装済み**（`tools/file_merge.py` の
      `merge_python_tasks` + `adopt.py` の `TASK_APPEND_KINDS`/`_ask_about_task_files`）。
      `ast` で欠落関数だけを末尾追記、デコレータ未 import なら追記せず報告、既存関数のバイト不変を
      検証して破れば巻き戻し。`tests/test_file_merge.py`（報告/追記/冪等/import 欠落）と
      `tests/test_adopt.py` で担保（43 passed を実測）
- [x] **W11（新）**: 既存 `ci.yml` への**ジョブ単位マージ** → **実装済み**（`file_merge.merge_ci_jobs` +
      `adopt._merge_ci_caller`/`_ask_about_ci_jobs`）。既定は非破壊の `copier-ci.yml` 併置で、承認時のみ
      `ci.yml` に読み取り専用ジョブ（`lint`/`test`/`hygiene`）を追記。publish 系（`dist`/`release`/`docs`）は
      追記しない。追記後は YAML 再パースで既存ジョブ不変を検証し、名前衝突は報告のみ。
      `docs/how-to/adopt.md` を実装に合わせて更新済み

### 22.2.1 今回の実行で判明した欠陥（証人マトリクス由来。全て修正済み）

- [x] **`micropython_port=mimxrt` の stubs が解決不能** → **修正済み**: その port は PyPI に
      `1.26.1.post1` しか公開が無い（他 7 port は `1.29.0.post1`）。テンプレートは port 別に
      最新公開系列を pin（`~=1.26.1`）し、upstream 追随時に上げるコメントを付与。
      `just stubs` exit 0、mimxrt の firmware type-check も exit 0（pin を外すと stubs 不在で exit 3 になるため
      「除外」ではなく pin を選択）
- [x] **flat レイアウト + `use_recommended_agent=false`** → **修正済み**: `help=f"..."` を src 版と同様に折返し。
      flat の `just check` exit 0、src 版は byte-identical
- [x] **`oj_code` の生成 docs `index.md`** → **修正済み**: `{% elif oj_code %}` を追加し、パッケージを持たない
      ワークスペース向けの説明に変更（install/import 断片を削除）。atcoder の `just docs` exit 0、
      library の断片は従来どおり
- [x] **W4**: `support.yml` + 生成 `docs/reference/support.md` + `tests/test_support_matrix.py`
- [x] **W3 の残り**: 文言固定 assert の監査（15 モジュール、関数削除ゼロ）

### 22.3 既知の罠（W0 が踏む・copier 9.18.1 で実測再現済み）

次タグは PEP440 で `5.4.0` より大きくする必要がある（例 `6.0.0`）。`1.0.0` を打つと、現 HEAD で生成済みの
プロジェクト（answers の `_commit: 5.4.0-69-ge2a210e1` → version `5.4.0.post69.dev0+e2a210e1`）に対し
`_main.py:1368-1371` が `UserMessageError` を **raise** し、`copier update` が一切通らなくなる:

```
You are downgrading from 5.4.0.post69.dev0+e2a210e1 to 1.0.0. Downgrades are not supported.
```

さらに、同一 commit に複数のバージョンタグを残すと dunamai が低い方を選び偽のダウングレードになるため、
**継承タグは削除し、HEAD のバージョンタグは 1 つだけ**にする。
`_template.py:421` の migration 選択は `new >= migration.version > old` なので、既存の `2.0.0` エントリは
既存ユーザーには発火しない（正常）。受け入れ条件は「HEAD 生成物を新タグへ `copier update` して `_commit` が
前進すること」を実測すること。再現手順と詳細は `notes/PLAN-improvements.md` の W0 を参照。

dirty なテンプレートでは `copier update` が成立しない点も実測済み（copier が clone 内に合成コミットを作り、
その describe がレンダ毎に変わるため「ダウングレード」と判定される）。`tools/batch.py` はこれを
`update-precondition`（clean tree 必須）として実装し、`tests/test_example.py` の adopt-update テストも
clean clone から render する形に修正済み。

### 22.4 追加の罠: template payload への symlink（2026-09-13 実測）

`template/` 配下の次の 13 エントリは**リポジトリ本体への symlink** で、copier はリンクを辿って中身を
生成物に書き込む。つまり「repo の設定ファイル」を編集すると**生成プロジェクトの設定も同時に変わる**:

- `tests/conftest.py` → `../../tests/conftest.py`（生成物に repo の conftest がそのまま入る）
- `.github/workflows/{_test,_tasks,_release,_pypi,_hygiene,_docs,_dist,_container}.yml`、`.github/pages`
- `.vscode`、`.devcontainer`、`.gitleaks.toml`

実害の記録: W9 のレンダキャッシュを `tests/conftest.py` に置いた版は、生成物へ `from copier import run_copy`
を漏らした（生成プロジェクトの dev 依存に `copier` は無い）。さらに生成 ruff の line-length 88 と衝突し、
`test_generated_project_is_ruff_format_clean` が 24 件落ちた。対策としてキャッシュは repo-only の
`tests/render_cache.py` に置き、共有 conftest は空のまま。`_test.yml` への入場追加も、生成側 `ci.yml` が
`task:` を渡さない前提（既定 `test`）と、`schedule:` を共有ファイルに置かないことを守って実装した。

### 22.5 PLAN §7「完了条件」の判定（2026-09-13 実測）

| # | 条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 引数なし `copier copy` が exit 0 | ✅ | `tests/test_generation_docs.py::test_default_copy_sees_the_fork_questionnaire`（6.0.0 を解決） |
| 2 | 全葉が ledger に登録され、`tier != none` の全葉に実行済みの証人 | ✅ | `coverage: {total: 205, executed_fast: 205, executed_full: 8, none: 0, unexecuted: []}`、results 全部 pass |
| 3 | タスク名集合が全ランナーでモデル一致 + `test`/`check` の実走 | ✅ | `test_task_runners.py` の構造比較 7 ランナー + `make test` / `poe check` 実走 |
| 4 | `copier update` が全 fixture ref で conflict なし | ✅ | `tests/test_update_path.py` 5 passed（タグ生成 → HEAD へ update） |
| 5 | README が <130 行 + TL;DR、`gen_docs.py --check` 緑 | ✅ | **完了（1981f367）**: README は 120 行のエントリポイントに。機能カタログは `docs/reference/features.md`、`--check` 緑 |
| 6 | 全 workflow に `timeout-minutes` + `task check` が通る | ✅ | W7 で付与。`task check` 相当を実測: lint ✓ / type-check ✓ / fast tier 657 passed ✓ / **heavy tier 43 passed**（venv 構築含む） |
| 7 | adopt の T1 衝突 | ✅ | W8（解決済み）+ `tools/detect.py` の `COLLISIONS` |
| 8 | `-m "not heavy"` がヘビー tier を外しレンダ被覆を失わない | ✅ | 435 + 30 = 465 を検証、witness fast tier は render 205 件を維持 |

残る唯一の未達は #5 の README 行数削減（別 WP）。あわせて repo 設定側の未整備:
**タグ push で走る `release` ジョブが 403**（`Resource not accessible by integration`。
Settings → Actions → General → Workflow permissions を "Read and write" にするか PAT が必要。
6.0.0 の GitHub Release / PyPI 公開はこれが理由で未作成。テンプレート側の欠陥ではない）

## 23. テストの簡易化・実行の簡易化・MCP 整備・論理検証の到達点（2026-09-13 監査）

節19（CI コスト）と節22 の W3 / W9（marker 化・レンダキャッシュ・witness 実行）の
Acceptance はそのまま有効で、ここには**再掲しない**。この節は今回の実測で新たに判明した
実行系の差分、まだどこにも無い2テーマ（テストを**書く側**の簡素化 / MCP の整備）、
および Z3 検証をどこまで主力にするか（23.4）を置く。

### 23.0 実測（この節の根拠。16 コア・warm）

| 指標 | 実測値 | 出所 |
|---|---|---|
| テスト総数 / ファイル / 行数 | 695 / 23 / 7,981 | `pytest --collect-only` |
| tier 分離 | `-m "not heavy"` 652（heavy 43）/ `-m "not heavy and not slow"` 647 | 同上 |
| wall time（実測 2026-09-13） | `test-fast`（`not heavy`）**151s** / 実質 fast（`not heavy and not slow`）**21s** / フル 695 件 **170s**（3 failed） | `time pytest` |
| 上位の内訳 | witness batch runner **119s** / scraping 11.1s / agents_md 10.5s / update_path 7.4s / adopt 6.0s | `--durations=20` |
| `tests/test_example.py` | 2,171 行 / 定義 130 / `@pytest.fixture` **0** | `wc` / grep |
| marker 使用 | heavy 25・network 25・fast 4・full 4・slow 2 | grep |
| `render_cache` 利用 | 4 ファイル（generated_lint / pyproject_fmt / update_path / witness_matrix）。**セッション内限定**（`tmp_path_factory` basetemp 配下） | grep + `render_cache.py:58-68` |
| witness（W3 着地済み） | 205 葉 / ledger `tests/matrix/witnesses.json` / `-m fast` 208 params / `full` サンプル **8 葉で 3 failed** | 実測 |
| repo 自身の MCP | tool 7 + resource 1、`.mcp.json` **なし**、`_allowed_hosts` のテスト**なし** | `tools/mcp_server.py` |

> 2026-09-13 追記: W3 が着地した（`tests/test_witness_matrix.py` 680 行、`witness.yml`、`tests/matrix/witnesses.json`）。
> よって「witness tier / ledger / カバレッジ assert」を新設する項目は不要になり、23.1〜23.4 の残りは
> **パーサ抽出・不変条件の単一源・差分テスト・MCP**に絞られた。`fast`/`full`/`slow` marker も使用中になった。

### 23.1 テストの簡易化（書く側）

- [x] **`when` パーサと Z3 エンコーダをテストファイルから `tools/` へ出す**
      → **完了（2026-09-14 監査）**: tools/when_model.py（tokenize_when / when_expr_satisfiable / str_domains）へ抽出し、tests/test_copier_structure.py は import に置換（z3_witnesses.py の importlib 逆輸入は §26.1 で消滅）
      - 現在 `tests/test_copier_structure.py:427-633`（`_tokenize_when` / `_when_expr_satisfiable` /
        パーサクラス）にプロダクション相当のロジックがあり、`tools/z3_witnesses.py` が
        `_structure_module()`（`STRUCTURE_TESTS` を importlib でパス読み込み）で逆輸入している。
        テストを書き換えると道具が壊れる依存で、basedpyright / vulture の視界からも外れる
      - 実測（2026-09-13 の W3 作業中）: この逆輸入の副作用で `tools/z3_witnesses.py:220-224` は
        `importlib` で読んだモジュールを `sys.modules` に登録する回避策を持つ
        （`dataclasses` がモジュール解決に `sys.modules` を要求するため）
      - 抽出先 `tools/when_model.py`（パーサ + Z3 エンコード）。テスト側は import に置換。
        W3 の所有権「`test_copier_structure.py` の Z3 関数は呼ぶだけ」とも整合する
      - 併せて `test_copier_structure.py` 向けの per-file-ignores
        （`C901` / `PLR0911` / `PLR0912` / `EM102` / `RUF010`）をプロダクション側の
        正当な ignore へ移せる
- [x] **共有サポートモジュールを作る（`tests/support/`。`conftest.py` へは置かない）**
      → **完了（2026-09-14 監査）**: tests/support.py（run_pipe / make_venv / copy_project）として着地（§27.7-4、a30747e8。ディレクトリでなく単一モジュール）
      - 理由は `tests/render_cache.py:1-13` に実測記録がある: このリポの `conftest.py` は
        `template/.../tests/conftest.py` の symlink 経由で**生成物へ render される**ため、
        copier / fcntl を持ち込めない。`render_cache.py` はその規約の唯一の実例で、
        同じ判断を2度書かないための置き場が無い
      - 移す対象: `run_pipe` / `make_venv`（`tests/test_example.py:66-97`）、レンダ用
        `run_copy` ラッパ（8 ファイルで個別実装）、ファイル集合 assert
        （`test_recommended_path.py:52-100` の MARKERS と `z3_witnesses.py` の
        `COMMON_FILES` / `PROJECT_TYPE_FILES` が二重定義、後者は「mirrors」とコメントで手動同期）
- [x] **answers の単一情報源を作る**
      → **完了（2026-09-14 監査）**: tools/answers.py の BASE が単一源（tests/support.py / tests/test_recommended_path.py / tests/test_answer_fixtures.py が消費し、fixture の質問名を質問票と照合）
      - 現状 5 系統が独立に literal を持つ: `example-answers.yml`、`RENDERED_PATHS`（23 組合せ）、
        `test_recommended_path.py` の BASE、`z3_witnesses.py:BASE`、`test_mcp_server.py:BASE_ANSWERS`
      - `tools/questionnaire.py` の JSON モデル（109 問）を既定値の源にし、各 fixture は
        「既定 + 上書き差分」だけを持つ形にする。drift は無音なので、fixture が要求する質問名が
        質問票に存在することをテストで検証する
- [x] **`test_example.py` を分割し fixture 化する**（2,212 行 / 131 定義 / fixture 0）
      - venv を作る 18 テストが `make_venv(tmp_path)` を個別に呼ぶ。session 共有にできるのは
        「同一 answers の venv 1 回」まで（依存差で偽陽性が出る組合せは PLAN §W9-3 の計測後）。
        まずファイル分割（library / cli / web_api / daemon / oj）で見通しを戻す
      - PLAN §W9 の所有権メモ（ユーザー編集中は触らない）が解けるまで着手しない
      → **完了（2026-09-14、29344b39）**: 分割は質問票の軸で10モジュール
        （example_{library_cli,web_api,data_science,oj,layers,docs_ci,adopt,ros2,micropython,toolchain}）。
        移動のみ（`--collect-only` の関数名 858 件が親コミットと一致、assert・answers の
        変更ゼロ）。共有ヘルパは `tests/support.py` へ。**fixture 化は未着手**（venv session 共有は
        PLAN §W9-3 の計測が前提。§27.7-4）
- [x] **文言固定 assert の整理は W3 の Acceptance に統合する**（節22.2 W3 の
      「4,303 行のうち文言固定だけの assert を洗い出す」が正。ここでは二重管理しない）
      → **完了（2026-09-14 監査）**: §22.2 W3（「文言固定 assert の監査」）に統合済み。ここでは二重管理しない
      - 実例: `tests/test_example.py:751-774` は生成 `mcp_server.py` / `Taskfile.yml` /
        `.env.example` に `"streamable-http"` / `"MCP_ALLOWED_HOSTS"` の**文字列が含まれる**
        ことだけを見る。生成物を実走する検証に置換できる（23.3 の allowlist 実走と同じ作業）

### 23.2 実行テストの簡易化（回す側）

- [x] **marker の負債を返済する**
      → **完了（2026-09-14 監査）**: docs/how-to/test-loop.md の tier 表と docs/explanations/verification.md が fast/full/slow/heavy/meta の意味を固定し、tests/matrix/tiers.json が台帳、Taskfile.yml が test-fast / test-slow / test-heavy / test-meta（未使用 marker の宣言も解消）
      - `fast` / `full` / `slow` は `pyproject.toml` の `markers` で宣言済みだが使用 0、
        `network` は `heavy` と同時にしか付かない。W3 の witness tier を `fast` / `full` に
        割り当てるならその時に使い、使わないなら宣言を消す（second convention を作らない）
      - `docs/how-to/test-loop.md` の tier 説明が現行と乖離: 「`task test-fast` は
        `test_example.py` と `test_generated_typecheck.py` を**丸ごと除外**」と書いてあるが、
        実装は `-m "not heavy"` で `test_example.py` も **112/136 件が走る**（実測。
        `test_generated_typecheck.py` 側は 6/6 が heavy なので除外で正しい）。
        docs を実装に合わせて書き直す
- [x] **marker ドリフトのガードテストを足す**
      → **完了（2026-09-14 監査）**: tests/test_marker_drift.py — venv / network 作業を持つテストに heavy / network をソース走査で強制（tier 収集集合と台帳・docs の一致も検証）
      - 「`make_venv` / `uv sync` / ネットワーク clone を含むテストは `heavy`（必要なら
        `network`）を持つ」ことをソース走査で強制する。今は 18/18 正しいが、新規テストが
        1 本 marker を忘れると fast tier が無音で 20 秒級になる
      - 件数（429 / 36）はテストで固定しない（検証内容ではなく実装の写し）
- [x] **`tools/batch.py` に `--jobs N` を足す**
      → **完了（2026-09-14 監査）**: tools/batch.py の --jobs N（ProcessPoolExecutor）。実測 113.8s → 10.2s、Taskfile.yml の `witness` が既定 numCPU で使う（§26.1）
      - 現在 `jsonl` は直列（`--fail-fast` のみ）。witness 205 葉のレンダだけで
        205 × ~1.3s ≈ 4.5 分が下限（`render_cache.py` の実測コメント）。
        リクエストごとに独立した作業ディレクトリを持つため thread pool で安全に並列化できる
      - `render_cache`（同一 answers の重複排除）とは役割が違い、両方入って初めて
        205 葉が実用時間になる
- [x] **`task witness` を追加する**（`z3_witnesses.py --jsonl` → `batch.py --json` の一発化）
      → **完了（2026-09-14 監査）**: Taskfile.yml の `witness`（tools/z3_witnesses.py --jsonl → tools/batch.py --json --jobs）
      - 現状 Taskfile に witness を回す口が無く、`--jsonl` の再生成も手打ち。
        W3 が `tests/test_witness_matrix.py` + `witness.yml` を作る際の入口になる
- [x] **CI に `paths:` フィルタを入れる**（docs のみ / pyproject のみの変更で venv tier と
      render matrix を回さない）。節19 の fast/heavy 分割・キャッシュとは別物として残す
      → **完了（2026-09-14 監査）**: .github/workflows/ci.yml の job 単位 docs-only ゲート + witness.yml / update-path.yml の paths-ignore（必須チェックを Pending にしないため workflow 級 `paths:` にはしない。§27.7-5、f4838b75）
- [x] **ローカル編集ループのエルゴノミクスを docs に固定する**
      → **完了（2026-09-14 監査）**: docs/how-to/test-loop.md「Ergonomic flags」（task test-fast CLI_ARGS="--lf" / -x / --durations=25）と tier 表
      - `task test-fast CLI_ARGS="--lf"` / `-x` / `--durations=25` は既に動くが
        `test-loop.md` に記述が無い。`task batch ... --shell` と合わせて
        「1 ケース（2s）→ ファイル（17s）→ フル（37s）」の3段として明文化する
- [x] **coverage の扱いを決める**（`task test` は `--cov` を出すが `fail_under` が無く、
      `cov.xml` がローカルにも残る）。閾値を入れるか、ローカルでは coverage を外して
      CI のみにするか（現状は「出るが誰も見ない」）
      → **決着（2026-09-14、121b221a）**: 閾値は入れない（テンプレ repo の coverage は
        運用指標にならない）。repo の `task test` は xml を `.cache/cov.xml`
        （gitignore済み）へ、生成プロジェクトは codecov 用にルート `cov.xml` を維持

### 23.3 MCP の整備

- [x] **このリポジトリ自身の `.mcp.json` を追加する**（dogfooding）
      → **完了（2026-09-14、36b7fc7d）**: ルート `.mcp.json` + `docs/how-to/mcp-tools.md`
        （tool 一覧ページ）。`task mcp` と同一の stdio 起動
- [x] **開発ループの実 tool を足す**（12 tool まで拡充済み。残りは `run_tests(tier)` のみ）
      → **完了（2026-09-14、b6458297）**: `run_tests(tier, only=..., timeout=...)` を追加。
        tier は `fast` / `heavy` / `slow` / `meta` / `all` で、marker 式は
        `tests/matrix/tiers.json` の該当行から読む（Taskfile と突き合わせ済みの台帳を
        第4の写しにしない）。返す verdict は `run_witness` と同じ per-test 形式
        （id / ok / seconds / checks）。テストは `-k` で 1 件に絞って配線だけを固定
      - `run_tests(tier)` — `fast` / `heavy` / `witness` を回して**構造化 verdict** を返す。
        本命: エージェントが pytest のテキストを解釈せずに済む（`batch.py` の verdict 形式を流用）
      - [x] `render_diff(answers_a, answers_b)` — 2 レンダのファイル単位 byte 比較
      - [x] `lint_render(answers)` — render して `ruff format --check` / `ruff check` まで
      - [x] `list_witnesses()` / `run_witness(tier)` — W3 の成果物を tool 面に出す
      - [x] `template_fingerprint()` — `render_cache.py` の指紋（render 入力の sha256）を返す
- [x] **`render_project` の戻り値を拡張する**（現状はファイル一覧 + dest）
      - ファイルごとの sha256 と `diff_against`（既存 dest との差分）を返す。
        tool の出力がそのまま回帰検証の入力になる。回帰比較そのものは
        `render_diff` が既に担うので、本項は利便性の重複整理として優先度低
- [x] **repo 側 MCP の未テスト経路を埋める**
      → **完了（2026-09-14、36b7fc7d）**: `tests/test_mcp_server.py` が実サーバを実走し
        「allowlist 無しの 0.0.0.0 bind は起動拒否（stderr が変数名を指す）/
        allowlist 有りで悪意 Host は /mcp 421・/health は 200」を固定
      - [x] `tests/test_mcp_server.py` の tool docstring 検査は「cost と戻り値の形を
        docstring に書く」規約の強制として動作中（docstring が両方書かないと fail）
- [x] **resource を増やす**（`template://questionnaire` のみ）
      → **完了（2026-09-14、da4ef143）**: `template://support` を追加（`support.yml` を
        `tools/gen_docs.py` の `load_support` 経由で返す＝docs ブロックと
        `tests/test_support_matrix.py` と同じ 1 つのローダ）。テストは宣言された
        `supported` を `list_witnesses` の在庫と突き合わせ、「CI が実際に実行したもの」を
        答える resource であることを固定
      - `template://witnesses`（205 葉の一覧と tier）、W4 後は `template://support`（`support.yml`）。
        エージェントが「何が検証済みか」を 1 resource で読める
- [x] **生成 scaffold と repo server の関係を 1 つに決める**（drift の芽）
      → **完了（2026-09-14 監査）**: 「統合しない」の結論を docs/how-to/mcp-tools.md「Relationship to the generated scaffold's server」と tools/mcp_server.py:44-50 に明記
      - 前者は「型付き tool の見本 + security 実装」（`_shared/mcp_server.py.jinja`）、
        後者は「テンプレート保守用」（`tools/mcp_server.py`）。共通コードはゼロで、
        `TransportSecuritySettings` の扱いだけが二重実装になっている。目的が違うため
        **統合しない**と明記して second convention を防ぐ（統合するなら `_allowed_hosts` だけ
        `_shared/` に寄せる）

### 23.4 論理検証（Z3）をどこまで証明の主力にするか（2026-09-13 追記）

願望は「Z3 が通れば全部安全」。現在の Z3 層が実際に証明しているのは**質問票の入力空間**だけ:

- 証明済み: 各 `when` が充足可能（`test_copier_structure.py:636`）、typo / 自己矛盾ゲート /
  不可能なジャンル組合せを sweep が検出する（同 :704-741。検出器自身を壊して検出できることを確認する
  meta テストつき）、葉が 205 個に列挙される
- **未証明**: レンダ結果の内容、ファイル間の整合、タスク定義の等価性、生成物が実際に動くこと。
  これらは Jinja + copier + ファイルシステムの実行意味論が要る領域で、Z3 の外

つまり「Z3 単独で全部安全」は原理的に取れない。取れるのは
**「Z3 が入力空間を漏れなく列挙し、宣言的な不変条件を全葉で実行検証する」= 有限で網羅的な証明**で、
Z3 の力は「どこを実行すれば十分か」を確定できる点にある（実行コストは 205 葉 × 検証で有界）。
その形に寄せるための残タスク:

- [x] **`when` モデルの差分テスト（最優先。これが無いと Z3 の結論が信用できない）**
      → **完了（2026-09-14 監査）**: tests/test_when_model.py:181 — copier の Worker._ask とモデルの真偽を全葉・probe で突き合わせ（約 9,800 比較。§26.1）
      - Z3 側の `when` 解釈は `test_copier_structure.py:427-633` の**再実装**（projection）であり、
        `tools/z3_witnesses.py` の `PROJECTED_GATES` は手書き +「mirror できなければ SystemExit」で
        保守している。Jinja の実評価とモデルの判定が食い違えば、緑のまま**偽の安心**になる
      - 全葉（または全 `when` × 代表 answers）で「実 Jinja の真偽」と「Z3 モデルの真偽」を突き合わせ、
        乖離したら fail させる。sweep の meta テスト（:704-741）と同じ精神を
        **モデル本体**に適用する
- [x] **不変条件を宣言的単一源にする**
      → **完了（2026-09-14 監査）**: tests/matrix/invariants.yml + tools/invariants.py が単一源（§27.2 T6 で z3_witnesses / test_recommended_path / test_render_invariants の dict を集約）
      - 今は「葉が満たすべきファイル集合」が Python の dict で `z3_witnesses.py`（`COMMON_FILES` /
        `PROJECT_TYPE_FILES` / `INCLUDE_FILES`）と `test_recommended_path.py:52-100` に二重定義され、
        コメントで手動同期している。`tests/matrix/invariants.yml`（or `support.yml` の隣）に一本化し、
        W3 のランナー / `test_recommended_path` / W4 の `support.yml` / W5 の docs 生成が同じ源を読む
      - 「仕様 = 1 ファイル」になれば、テストの追加は「不変条件を 1 行足す」に縮む（23.1 の簡素化と同根）
- [x] **列挙の完全性を明示する**
      → **完了（2026-09-14 監査）**: tests/matrix/invariants.yml の `excluded:`（web_django + 統合 2 問、理由付き）+ tools/z3_witnesses.py のカバレッジ出力（§27.7-6、bb6a9e53）
      - 205 葉は projection の全モデルであるべき。除外（`EXCLUDED_PROJECT_TYPES` の web_django、
        `when` を mirror しないゲート）は**明示リスト**にしてカバレッジ出力に載せる。
        「列挙した」「除外した」を数字で言えるようにする（現在は unprojected が居たら SystemExit）
      - `witnesses.jsonl` が質問票の現行版と同期しているかも検証する（`ref: HEAD` の陳腐化検出）
- [x] **不変条件を content 述語まで広げる**（ファイル集合 → 中身）
      → **完了（2026-09-14 監査）**: tests/matrix/invariants.yml の `predicates:`（pyproject / agents-md / readme-links / docs-nav）と tests/test_render_invariants.py の実装
      - `pyproject.toml` が parse でき、依存集合が質問票モデルから導出した期待集合と一致する
      - タスクランナーのタスク集合が宣言モデルと一致する（W2 で手作業検証した「1684 ファイル全ハッシュ一致」は
        23.3 の `render_diff` tool 化 + この不変条件で自動化）
      - AGENTS.md のコマンド表がタスクモデルと一致する / 生成 README の内部リンクが実在する
      - いずれも**レンダ後に決定的に判定できる**述語だけを不変条件にする（実行・network は入れない）
- [x] **手書きテストを不変条件へ移す棚卸し**（W3 Acceptance の「文言固定 assert の洗い出し」と同一作業）
      → **残り（2026-09-14 監査）**: 単一源と述語は着地済みだが移行は未完（§26.4-1b T12 の「他で回していない」render sweep 6 本 ≈60s を L1 へ移す）
      - 465 本のうち「葉 × 不変条件」で置換できるものを移し、実行テスト（heavy）は
        **不変条件で表現できない領域だけ**に絞る。これが「Z3 + 全葉検証」の比率を上げる唯一の道
- [x] **非目標を明文化する**（ここを曖昧にすると「Z3 で全部安全」の看板が嘘になる）
      → **完了（2026-09-14 監査）**: docs/explanations/verification.md「Non-goals」（Z3 は入力空間のみ。venv / pytest / network / Docker は heavy tier、目標は3点セット）
      - venv 構築 / 実際の pytest 実行 / network / Docker / 外部 CI は Z3 でも不変条件でも覆えない。
        heavy tier は「残った実行領域」として意図的に保持する（PLAN §W9 の非目標と同じ）
      - 目標は「Z3 が入力空間 / 不変条件が仕様 / 全葉実行が証明」の3点セットであって、
        「Z3 が単独で全部」ではない。この言い方を docs（`docs/explanations/`）にも固定する

## 24. 検証アーキテクチャと拡大則（2026-09-13 深掘り）

節23 は個別の残タスク、この節はその**背後の方針**: どの層が何を保証し、拡大すると
どこがどう増えるか、その増え方をどう有界に保つか。節19/22/23 の項目は再掲しない
（同一の項目は「節23.x と同一」と明記して指すだけにする）。

### 24.0 問題の整理（すべて実測つき）

| # | 問題 | 実測された症状 | 拡大でどう悪化するか |
|---|---|---|---|
| P1 | **tier の意味と実測コストが乖離し、誰も気づかない** | `task test-fast` は今 **151s**（650 passed）。`docs/how-to/test-loop.md` は 17s と記載。内訳の **119s は `tests/test_witness_matrix.py::test_witness_batch_runner_executes_every_leaf`**（slow + full。heavy ではないので `-m "not heavy"` をすり抜ける）。`-m "not heavy and not slow"` なら **21s**（645 passed） | tier が増えるほど「どこに入れるか」が属人的になり、遅いテストが編集ループに混入する。実際に混入した |
| P2 | **仕様が3箇所に散在** | 期待ファイル集合が `tools/z3_witnesses.py` の dict / `tests/test_recommended_path.py` の MARKERS / `tests/matrix/witnesses.jsonl` の `expect` に分散。「mirrors」コメントで手動同期 | 機能追加ごとに同じ事実を3箇所へ書く。drift は無音 |
| P3 | **入力空間のモデルが Jinja の再実装** | `when` の Z3 解釈は自作パーサ。検証は「検出器が injected bug を検出する」meta テストのみで、実 Jinja との**差分行きテストが無い**（節23.4） | projection の穴（未対応構文）が増え、緑のまま偽陰性 |
| P4 | **再現コストの単位が重い** | L3 は 13–24s/ケース（PLAN §W9 top5）。レンダは **0.58s/葉**（119s ÷ 205 葉）。`render_cache` は**セッション内限定**（`tmp_path_factory` basetemp 配下）なので実行のたびに 205 葉を再レンダ | 葉 × venv が線形に増える。dep manager / runner 軸が増えると venv tier が倍々 |
| P5 | **増えてよい軸が宣言されていない** | `support.yml`（W4）未作成。長尾（make/poe/invoke/duty、loguru/picologging、pyrefly/ty）は render されるが実行検証は薄い | 「オプション追加」にコスト見積りが無く、検証が長尾に薄く広がる |
| P6 | **L3 の失敗が滞留する** | `-m full`（8 葉サンプル）が**今 3 葉 fail**（実測 132–195s）: (a) `micropython/gate=recommended` — basedpyright `File or directory ".../smoke_example" does not exist` で exit 3、(b) `online_judge/.../atcoder` — `just docs` が `mkdocstrings: accessing 'smoke_example' raises ModuleNotFoundError`、(c) `cli/gate=off:use_recommended_agent` — `agent.py:81` の `prompt`/`model` が Any で basedpyright exit 1。**L2（205 葉・21s）は緑のまま** | 夜間が赤いまま常態化すると L3 の signal が死ぬ。逆に L3 が無ければこの3件は出荷されていた |
| P7 | **コストの観測点が無い** | tier の実測コストを記録する台帳が無い。17s→151s の drift は人手で気づくしかない（`--durations` は実行時のみ） | 拡大のたびに「遅くなった」に事後で気づく |

P6 は方針の裏付けでもある: **L3 サンプルは 8 葉で 3 件の実欠陥を出した**。
「Z3 と不変条件で全部」が取れないことの、これ以上ない証拠。

### 24.1 コストの実測モデル（16 コア・warm）

| 層 | 何を保証するか | 入力 | 実測単価 | 拡大則 |
|---|---|---|---|---|
| **L1 入力空間** | 到達不能・矛盾した組合せが無い / 全葉を列挙できる | `copier.yml` + `when` | ms（render なし） | O(問い × 選択肢) |
| **L2 出力不変条件** | 全葉のレンダ結果がファイル集合・内容述語を満たす | 全葉 205 | **0.58s/葉**（serial）。xdist 16 + セッション内キャッシュで 205 葉 ≈ 10s | **O(葉)**。葉 ≈ 2.7 × Σ_pt (1 + その pt の gate-off 次元) = 76 × 2.7 = 205 |
| **L3 実行** | venv 構築・生成物の実走・network・docs build | 有界サンプル 8 葉 | **13–24s/ケース**、8 葉で 132–195s | O(サンプル)。**全葉にはしない** |

葉の成長則（実測値から）:
- **+1 include 層**（全 base と合成）= **+76 葉** ≈ +45s serial / +3s（16 worker）/ **キャッシュ後ほぼ 0**
- **+1 gate-off 次元** = +8 base ≈ **+22 葉** ≈ +13s serial / +1s（16 worker）
- **+1 project_type** = 不変条件の行 + L3 サンプル 1 件（+20s）+ その pt の base（例: +3 base ≈ +8 葉）
- ⚠ **現在 include 層は 1 葉につき最大 1 つ**（実測: 0 個 108 葉 / 1 個 97 葉）。排他を崩して
  2 層同時を許すと乗数が 2.7 → 組み合わせ数に跳ね上がる（葉数が指数的になる）。
  層の追加時は「排他（choose-one）を保つか、直積を受け入れるか」を必ず宣言する

**結論**: 拡大は L2 に寄せれば有界（+22 葉 ≈ +1s 並列 / 0s キャッシュ）。L3 を厚くすると
線形に高くつく。だから「L2 で表現できない理由」が無い限り L3 に置かない。

### 24.2 方針

1. **3層の責務と予算を宣言する**（tier は慣習ではなく契約）
   - `fast` = L2 まで（**予算 30s**）、`slow` = 全葉バッチランナー等（編集ループから除外）、
     `heavy`/`network` = L3（CI の nightly / pre-push）、`full` = L3 サンプル
   - 予算超過は台帳（P7）で検出する。「速い tier」を名乗るなら測る
2. **拡大は L2 に寄せる**。新規の検証は「不変条件を 1 行足す」を第一候補にし、
   実行テストを書く前に L2 で表現できないか必ず検討する
3. **L3 の失敗は資産**。落ちた葉は (a) テンプレの欠陥を直す、(b) `tier: none` + reason で
   「検証しない」と宣言する（W4 の仕組み）のどちらかに**必ず決着させる**。放置は signal の死
4. **仕様は単一源、コストは台帳**（節23.4 の不変条件単一源 + P7 の台帳）
5. **外部ツールは「自作より安い」の証明があるものだけ採用**。新 dep は dev に閉じる（24.3）

### 24.3 外部ツールの採用判定

| 候補 | 代替/補強する対象 | 判定 | 根拠・条件 |
|---|---|---|---|
| `pytest-testmon` | 編集ループのテスト選択 | **スパイク** | v1.4 で xdist 対応（testmon.org/blog）。ただしテンプレは**データ駆動**で `template/**` の変更は全テストに波及するため、「`template/**` / `copier.yml` / `_shared/**` を触ったら全選択にフォールバック」するガードが必須。無ければ偽陰性 |
| `pytest-split` / xdist `--dist loadgroup` | CI の L2/L3 シャーディング | **採用（小）** | `--dist loadgroup` は追加 dep ゼロ。シャード分割を自作する理由が無い |
| `pytest-randomly` | 順序依存・共有状態の flake 検出 | **スパイク** | `tests/conftest.py` に「xdist の hook-env 分離を試して 46s→7m44s で撤回」の履歴あり。入れるなら tier 予算への影響を測ってから |
| `hypothesis` | L2 の内容述語の反例生成・縮小 | **採用 or 削除の二択** | dev 依存にあるが使用 0（deptry の `DEP002` ignore が隠している）。answers 空間は Z3 が持つので、価値は「レンダ結果の述語の反例探索」のみ。使わないなら削除して ignore も消す |
| `syrupy` / `pytest-regressions` | レンダ結果の byte 比較（W2 の手作業ハッシュ検証） | **スパイク** | pytest 9 対応が未確認。不変条件の単一源で `sha256` を宣言すれば同じ保証が得られるなら dep を増やさない |
| `nektos/act` | witness / update-path workflow のローカル再現 | **導入済み（2026-09-16）** | `task act WORKFLOW=ci.yml JOB=lint`（`.actrc` は catthehacker runner イメージにマップ、docs/how-to/local-ci.md）。lintジョブのローカル実行を検証済み — コンテナは working tree を見るため、ローカルの赤 = 本物の赤。CI 側の dep にはならない |
| Task の `sources:` / `generates:` / `status:` | ローカルのタスク再実行抑制 | **採用** | 既に task runner。`.cache/` にスタンプを置けば dep ゼロで「変わっていなければ skip」 |
| `pixi`（既存の対応 runner） | venv 共有・タスクキャッシュ（L3 の再利用） | **スパイク** | PLAN §W9-3 の実装候補。`UV_PROJECT_ENVIRONMENT` 共有 + `--inexact` も同じ枠で計測 |
| `docker buildx --cache-to/--cache-from` | コンテナ経路の L3 | **不採用（今は）** | コンテナ経路の検証サンプルがまだ薄い。W4 で `best_effort` が決まってから |
| `hyperfine` / `pytest-benchmark` | コスト台帳（P7） | **採用** | 24.4 T5 の実装手段。`--durations` の台帳化だけでも可 |
| Bazel / pants / buck2 | 増分ビルド + リモートキャッシュ | **不採用** | 対象はコンパイル成果物ではなく「Jinja レンダ + 外部ツールチェーン」。build graph の利得より導入・維持コストが上 |
| `depot` / `blacksmith` 等の高速 CI runner | L3 の wall time | **保留** | 金で買える短縮。T5 の台帳で「L3 が本当に律速か」を確認してから |

### 24.4 TODO（優先順）

- [x] **T1: L3 の 3 失敗に決着をつける（最優先。今 夜間が赤い）** → **実測で解消（§26.1）: `-m full` の8葉で3葉とも PASS**
      - (a) `micropython` basedpyright: `_shared/pyproject-basedpyright.toml.jinja:9` の
        `include = ["{{ pkg_dir }}", ...]` が micropython の layout と一致しない
        （`smoke_example` が無い）。`_tasks.jinja:88-90` が micropython では
        `basedpyright -p firmware/pyrightconfig.json` も走らせる点と合わせて設計を直す
      - (b) `online_judge`(atcoder) docs: mkdocstrings が `smoke_example` を collect できない
        （競技 layout にパッケージが無い）。生成 docs の API リファレンスを
        `oj_code` では出さない/差し替える
      - (c) `cli` + agent gate off: `agent.py:81` の `run(parsed.prompt, model=parsed.model)` が
        Any（argparse 由来）。生成コード側で型を明示する（`cast` / 明示注釈）
      - 受け入れ: `pytest tests/test_witness_matrix.py -m full` が緑、または各葉に
        `tier: none` + `reason`（W4 の仕組み）が入り、その理由が docs に出る
- [x] **T2: tier を宣言どおりに直す（最小・即効）** → **実測で解消（§26.1）: slow tier 新設、fast は slow を除外**
      - `task test-fast` を `-m "not heavy and not slow"` に（**151s → 21s**、645 passed 実測済み）
      - `task test-slow` を新設（`-m slow`。対象は witness batch runner 119s + update-path の 1 本）
      - `pyproject.toml` の `markers` 説明に**予算**を書く（fast ≤ 30s / slow / heavy・network）
      - CI: PR の `test` は fast のまま短縮。`witness.yml` の fast も 205 葉レンダを含むので予算を測る
- [x] **T3: レンダキャッシュをセッション外へ**（P4） → **実測で解消（§26.1）: `.cache/renders/`**
      - `tests/render_cache.py` の root を `tmp_path_factory` basetemp から `.cache/renders/` へ。
        指紋（`template/**` + `_shared/**` + `copier.yml` + `_tasks.jinja` の sha256）は実装済みなので
        置き場を変えるだけ。`.cache` は既に gitignore 済み（`.gitignore:42`）
      - 受け入れ: 2 回目の `task test-fast` で `RenderCache.summary()` の `renders` が 0、
        `template/` を 1 バイト変えると全再レンダ
- [x] **T4: `tools/batch.py --jobs N`** → **実測で解消（§26.1/26.2）: 205 葉 113.8s → 10.2s。batch runner テストにも `--jobs 8` を渡し slow tier 172s → 72s**（節23.2 と同一。T2 の slow tier と
      witness の slow 実行がこれで縮む。リクエストごとに独立した作業ディレクトリなので thread pool で安全）
- [x] **T5: コスト台帳を CI で記録する**（P7 の恒久対策） → **実測で解消（§26.1/26.2）: `tests/matrix/tiers.json` + `test_marker_drift.py`。ただし wall_seconds は未測定値が入っていたのを実測で埋め直した**
      - `--durations=0 --durations-min=1` を parse して `tests/matrix/cost.json` に checked-in。
        前回比 +30% で fail。tier ごとの wall time も同時に記録
      - 受け入れ: `test-loop.md` の表（現在「17s」「ファイル除外」と実装に 9 倍乖離）を
        `tools/gen_docs.py` が台帳から生成し、`--check` が drift を fail させる
- [x] **T6: 不変条件の単一源**（節23.4 と同一。24.2 の「拡大は L2 に寄せる」の前提）
      → **完了（2026-09-14 監査）**: §27.7-1 / §27.2 に統合済み（tests/matrix/invariants.yml + tools/invariants.py。§23.4 の同一項目も完了）
- [x] **T7: 拡大の受け入れゲートを docs 化する**（P5）
      → **完了（2026-09-14 監査）**: docs/explanations/verification.md の「Growth rules」「Before adding a check: five questions」+ support.yml / docs/reference/support.md のマシン可読契約
      - `docs/explanations/` に「検証の3層 / tier 予算 / 拡大の5問（既存の何の上に載るか・葉の増分・
        不変条件の行・tier・support level）」を 1 ページ。W4 の `support.yml` をマシン可読な契約にする
      - 24.1 の成長則（+1 層 = +76 葉 ≈ +3s、+1 gate = +22 葉、include は排他を崩すと指数的）を
        そのページに載せ、**設計判断のたびに葉の増分を見積もる**習慣にする
- [x] **T8: 外部ツールのスパイクを 1 本ずつ**（24.3）。各スパイクは
      「置換対象 / 期待削減 / 偽陰性リスク / 撤退条件」を 1 行で書いてから着手する
      → **完了（2026-09-14 監査）**: §27.4 / §26.4-8 に統合済み（§27.7-7: pytest-testmon 却下・pytest-randomly 採用=夜間 job・syrupy 不要・pixi venv 共有却下を実測で確定）

## 25. 形式検証をどこまで持ち込むか（2026-09-14 追記）

前提: これは §23.4 / §24 の3層を置き換える話ではない。**Z3 は既に形式検証（SMT）**であり、
上に行くほど「より強いソルバ」ではなく**対象が変わる**。持ち込める対象は3つに限られる。

### 25.1 何が言えて、何が原理的に言えないか

| 対象 | 形式化 | 道具 | 現状 |
|---|---|---|---|
| 質問票の入力空間 | **できる**（有限） | Z3/SMT | 実装済み（L1、205 葉） |
| **レンダ結果そのもの** | **できない** | — | 検証済みの Jinja/copier 意味論が存在しない。だから全葉レンダ + 不変条件（L2）で代替する |
| 外部ツールチェーン（venv / basedpyright / mkdocstrings / CI） | **できない** | — | L3 サンプルで代替（§24.0 P6 の3件はこの層でしか出ない） |
| **adopt / update のプロトコル** | **できる**（状態機械） | TLA+/Quint/Apalache | 未着手（→ 25.2 が動機） |
| **merge / パーサの性質**（保存・冪等・単調・parse 安定） | **できる** | Crosshair + deal / Hypothesis | 未着手 |
| `when` モデルと Jinja の一致 | 差分テストでしか担保できない（実装がオラクル） | 差分テスト | §23.4 で起票済み |

### 25.2 形式手法が既に見つけたもの: adopt はクラッシュアトミックではない

`docs/how-to/adopt.md:3` は「transactional driver」と書くが、実際は**プロセス内**トランザクション:

- `tools/adopt.py:378-385` `_snapshot` は旧バイト列を **メモリの dict** に保持（`_roll_back` も同じ）
- `tools/adopt.py:481` の try は `except Exception`。`KeyboardInterrupt` は `BaseException` なので
  **Ctrl-C ではロールバックされない**
- `batch.render` は**その場で書き込み**、`_verify`（:388）は後から検証 → 書き込みと検証の間の窓が無防備
- `tools/adopt.py:517` は `_MergeError` しか捕まない

→ SIGINT/SIGTERM/SIGKILL/電源断のどの時点でも「部分的に adopt された木」が残り、**復旧コマンドが無い**
（バックアップはプロセスと共に消える）。テストは 22 本あるが、踏むのは例外経路だけで、
クラッシュ点は列挙できない。これは形式手法（クラッシュ action つきモデル検査）が最も得意な形。

ただし**修復は証明ではなく機構**: 変更前に on-disk ジャーナル（旧バイト + created 予定パス）を書き、
`--recover` を足す。または staging に書いて `os.replace` で原子的に差し替える。モデルの価値は
「設計したジャーナルが全クラッシュ点を覆うか」の検査にある。

### 25.3 道具の判定

| 道具 | 対象 | 判定 | 理由 |
|---|---|---|---|
| Z3/SMT | 入力空間（L1） | **採用済み** | 有限で網羅的。ここは完成に近い |
| **Quint（Apalache）/ TLA+（TLC）** | adopt/update のプロトコル | **スパイク（最有力）** | crash action を入れて「どの時点で落ちても観測可能な部分状態が無い」を検査できる。モデルは骨格（backup → mutate → verify → rollback\|commit）だけで 200–400 行。Quint は simulator + Apalache + JSON で CI に向く |
| Alloy | 質問票 / 葉の関係 | **不要** | Z3 が同じことをしており、乗り換える利得が無い（可読性だけ） |
| **Crosshair + deal/icontract** | `tools/*.py` の**実 Python** を SMT 記号実行 | **スパイク** | 実装を書き換えずに演繹系の利得を得られる唯一の候補。第一対象は `file_merge.merge_taskfile` / `merge_ci_jobs` の「既存バイト不変」事後条件。パス爆発したら撤退 |
| Hypothesis（stateful / property） | merge・adopt の**実行可能な仕様** | **採用** | 既に dev dep で未使用（§24.3）。「貧者の TLA+」として最安。24.3 の「採用 or 削除」は V4 で採用側に倒す |
| model-based testing + 参照実装 | adopt の状態遷移 | **採用** | ランダムな木 + 操作列を生成し「不変条件 + 参照実装と一致」を検証。参照実装がオラクルになる |
| Dafny / Verus / Lean / F* | merge アルゴリズムの演繹証明 | **却下（今は）** | 走るのは Python のままなので、証明はモデルに対するものになり**モデル-コードギャップを新設**する。merge バグが再発クラスになったら再考 |
| Kani / CBMC / Creusot | — | **対象外** | C/Rust が無い |
| 検証済み Jinja / copier | レンダ自体 | **存在しない** | この道は閉じている。だから L2/L3 の実行検証が残る |

**Z3 と Quint の役割（混同しやすい点。2026-09-14 追記）**: 競合ではなく層が違う。
`quint verify` は自分で解かず **Apalache が TLA+ 経由で SMT に落として Z3 を使う**
（もう一方の backend の TLC は explicit-state の全状態列挙で SMT を使わない。
`quint run` はランダム・シミュレータで、Z3 も TLC も使わない）。

| | Z3 | Quint |
|---|---|---|
| 何か | SMT ソルバ | 仕様言語 + シミュレータ + モデル検査のフロントエンド |
| 入力 | 理論つき一階論理式 | 状態機械（`init` / `step`）+ 不変条件 + 時相性質 |
| 問い | 「この式を満たす値の割当てが**存在するか**」（1 ステップ） | 「**実行（トレース）**が bad state に到達するか / 全到達状態で不変条件が成り立つか」 |
| 反例 | モデル（値の割当て） | トレース（状態列。ITF で可視化） |
| 完全性 | 決定可能な断片では完全、他は unknown | 有界（trace 長 k / 有限化した定数）。全実行の証明には帰納不変条件が要る |
| このリポジトリ | L1（葉の充足可能性・網羅列挙） | adopt/update のプロトコル（V2） |

つまり L1 を Quint に置き換える意味は無い（状態機械ではない）。逆に adopt の
クラッシュ安全性を Z3 だけでやるなら遷移関係と k ステップの unroll・frame condition を
手書きすることになり、それは Apalache が生成しているものそのもの。手書きが新しい誤り源になる。
なお Quint の `run --mbt` は**モデルからテストを生成**する（モデル-コードギャップを
「証明」ではなく「テストで突き合わせる」方向で埋める）ので、V4（Hypothesis stateful）と同じ枠で使える。

### 25.4 前提（順序）

形式手法は**オラクル（仕様）**を要求する。このリポジトリの仕様は今も散文 + Python dict で、
§24.2/24.4 T6 の「不変条件の単一源」がまだ無い。無いまま道具を入れても
「何も無いもののモデル」を証明することになる。順序は
**T6（仕様の artifact 化）→ V4（実行可能な仕様）→ V1/V2（プロトコル）→ V3（実装の記号実行）**。

### 25.5 TODO

- [x] **V1: adopt のクラッシュアトミック性を設計する（機構が先）** → **実測で解消（§26.1）: on-disk ジャーナル + `--recover` + fsync、`tests/test_adopt.py` に SIGKILL ドリル**
      - 変更前に on-disk ジャーナル（旧バイト + created 予定パス）を書き、`--recover` を足す。
        または staging + `os.replace` で原子的に差し替える
      - 受け入れ: レンダ中 / マージ中の任意の時点で SIGKILL しても `--recover` で byte-identical に戻る
        （テストで再現可能。現在は復旧不能）
- [x] **V2: adopt/update のプロトコルを Quint（または TLA+）で小さく書く**
      → **完了（2026-09-14 監査）**: §27.3 / §26.4-5 に統合済み（models/adopt_crash.qnt + .github/workflows/quint.yml。TLC 51 状態で不変成立、late-journal 変種の反例を CI が毎回確認）
      - crash action を含む反例を出し、V1 のジャーナルが全クラッシュ点を覆うことを確認する。
        非目標: 全機能のモデル化。骨格だけ
- [x] **V3: Crosshair + deal を merge の 1 関数に試す**（`merge_ci_jobs` の既存不変。撤退条件つき）
      → **完了（2026-09-14 監査）**: §27.3 / §26.4-6 に統合済み（V3 却下: merge_ci_jobs の記号実行は 10 分で決着せず。§27.5 で merge_taskfile の欠陥を発見）
- [x] **V4: Hypothesis stateful で adopt を回す**（既存 dev dep。§24.3 の判定を「採用」で確定させる）
      → **完了（2026-09-14、a4275e36）**: `tests/test_adopt_stateful.py`。
        ランダムな木 + 操作列で参照モデルと毎ステップ照合。
        vulture は `@rule` / `@invariant` を見えないため `ignore_decorators` に追加
        （§26.4 item 7 と同一）
- [x] **V5: merge の事後条件を artifact 化**（§24.4 T6 と同一。形式手法のオラクル）
      → **完了（2026-09-14 監査）**: §27.7-1 に統合済み（2a907080: tests/matrix/invariants.yml の `merges:` + tests/test_merge_contracts.py）

## 26. 実装状況の検証と、今回見つけて直したもの（2026-09-14 実測）

§23〜§25 の項目が並行セッションで一気に実装されたため、この節は**コードを書いた本人ではなく
動かして**確認した結果を固定する。数字はすべて 16 コア・warm の実測。

### 26.1 解消を実測で確認したもの

| 項目 | 実測（以前 → 現在） |
|---|---|
| §24.4 T1: L3 の3失敗 | `-m full`（8葉）で `micropython` / `atcoder` / `cli`+agent-off の3葉が **PASS**（以前は exit 3 / `just docs` 失敗 / exit 1） |
| §24.4 T2: tier | `task test-fast` が slow を除外（**151s → 19〜33s**）。`task test-slow` 新設 |
| §24.4 T3: レンダキャッシュ | root が `.cache/renders/`（セッション外・内容アドレス・gitignore 済み） |
| §24.4 T4: `batch.py --jobs` | 205 葉が **113.8s（直列）→ 10.2s**（docstring に実測を記載） |
| §23.1: パーサ抽出 | `tools/when_model.py`。`z3_witnesses.py` の importlib 逆輸入は消滅 |
| §23.3: MCP | tool **7 → 12**（`render_diff` / `lint_render` ほか）、`.mcp.json`、`docs/how-to/mcp-tools.md` |
| §23.4: 差分テスト（最優先と書いた穴） | `tests/test_when_model.py` が**全葉 × 全 `when`** を copier の `Worker._ask` と突き合わせ（約 9,800 比較） |
| §25 V1: クラッシュアトミック性 | `tools/adopt.py` に on-disk ジャーナル + `--recover` + fsync。`tests/test_adopt.py` に SIGKILL ドリル |

### 26.2 今回見つけて直したもの

- **`x == y` の符号化バグ**（`tools/when_model.py:_eq`）: 2参照比較が自由ブールに落ちており、
  `pinned` では**答えに関係なく充足**していた（§23.4 が警告した silent weakening の実例）。
  修正は「両ドメインが共有する答えの選言」。**最初の修正案（`Int(x) == Int(y)`）も誤り**で、
  質問ごとに index が 0 から振られるため `ros2 == ctf` が真になった — 差分テストが両方の誤りを検出した。
  回帰テスト `test_a_comparison_between_two_references_compares_answers_not_indices` を追加し、
  **pre-fix に戻すと fail することを実測**（`the model says True for 'ros2' == 'ctf'`）
- **slow tier の直列実行**: batch runner テストが `--jobs` を渡さず 205 葉を直列レンダしていた（171.9s）。
  `--jobs 8`（xdist の兄弟ワーカーを圧迫しない上限）で **71.9s**（-100s）。`--fail-fast` は付けないので
  全葉判定は維持される
- **lint の残骸**: パーサを `tests/` から `tools/` へ出した際に per-file-ignores が追随せず `task lint` が赤
  （`tools/when_model.py` 12 件 + `tests/test_when_model.py` 2 件）→ pyproject に両ファイルの ignore を
  追加（CONTEXT 付き）
- **型の赤**: `context` の `dict` → `Mapping`、`@contextmanager` の戻り `Iterator` → `Generator`
- **台帳の未測定値**: `tiers.json` の `wall_seconds` が4 tier すべて同じ値（22.0）で、`test` は
  自分の `test-slow`（70s）より小さい 65.9s という矛盾があった → 実測で埋め直し
  （fast 37.7 / slow 71.9 / heavy 28.7 / full 138.9）、docs の表も同値に更新

### 26.3 現在の緑（2026-09-14 実測）

- `ruff check .` / `ruff format --check .`: 0 件
- `task type-check`（basedpyright / pyrefly / vulture / deptry / typos）: 緑
- `tests/test_marker_drift.py`: 5 passed（tier の collect 集合・台帳・docs の件数が一致）
- `task test`: 763 passed / 137.5s（スイート全体、warm）
- `task test-fast`: 715 passed / **37.7s**（下の内訳。同じリビジョンでも 32〜51s で振れる）

fast tier の上位（`--durations=15`、同一リビジョン）:

| 秒 | テスト |
|---|---|
| 15.3 | `test_mcp_server.py::test_run_witness_returns_a_verdict_per_test` |
| 13.2 | `test_batch.py::test_jobs_change_only_the_schedule` |
| 12.1 | `test_example.py::test_template_include_ctf_not_offered_elsewhere` |
| 10.9 | `test_example.py::test_template_include_scraping_not_offered_elsewhere` |
| 10.7 | `test_example.py::test_template_agents_md_absent_for_ai_ng_judges` |
| 10.6 | `test_example.py::test_template_mcp_not_offered_to_data_science` |
| 8.5 | `test_example.py::test_template_agents_md_present_for_kaggle_and_opt_in_judges` |
| 7.5 | `test_adopt.py::test_a_killed_adoption_is_recovered_byte_for_byte[after-a-merge-write]` |

> 数値は「その時点のリビジョン」のもの。実装が動いている間は `tiers.json` の
> `wall_seconds` が正であり、この節の数字は根拠（内訳）として読む。

### 26.4 残タスク（優先順。すべて 2026-09-14 の実測が根拠）

1. **T9: fast tier の予算超過を解消する**（最小・即効）
   - 実測: `task test-fast` = **37.7s**（同一リビジョンで 32〜51s と振れる）。
     `docs/explanations/verification.md:110` が宣言する編集ループ予算 **30s を超過**
   - 犯人（§26.3 の内訳）: 新規の `test_mcp_server::test_run_witness_returns_a_verdict_per_test`
     (15.3s) と `test_batch::test_jobs_change_only_the_schedule` (13.2s) が 1 本で 10s 超、
     `test_example.py` の "not offered elsewhere" 系 6 本が各 8.5〜12.1s、
     `test_adopt.py` の確認系 5 本が各 6〜7.5s
   - 注: `test_marker_drift` の実コストは **~2.5s**（48.5s → 51.0s の A/B 実測）。
     以前「drift が ~13s」と書いたのは誤り（xdist の起動込み wall と call time を混同していた）
   - 変更: (a) 10s 超の 2 本を tier から出す（`slow` にするか、サンプル数を絞る）、
     (b) 下の T12 で "not offered elsewhere" 系を L1 へ移す。(b) が本命で、
     残る (a) は対症療法
   - 受け入れ: `task test-fast` が 30s 以内（かつ p50 で 30s を超えない）。移した検査は
     `test-slow` / PR CI のどこかで必ず走る

1b. **T12: "not offered elsewhere" 系を L1（Z3）へ移す**（§24.2「拡大は L2 に寄せる」の実践）
   - 例 `test_template_include_ctf_not_offered_elsewhere`（12.1s）は **4 プロジェクトを render**
     して「library/cli 以外では `ctf_effective` が立たない」ことを確かめている。これは
     *レンダ結果*ではなく**質問空間**の性質で、`tools/when_model.py` の `str_domains` +
     `when_expr_satisfiable(pinned=...)` が ms で判定できる
   - 同じ形が 6 本（ctf / scraping / mcp / agents_md ×2 / license_check）あり、
     ワーカー時間で ~60s、critical path で数秒〜10s を占める
   - 変更: (a) モデルで `project_type × include_* → 派生フラグ` の真理値を全组合で検証（L1）、
     (b) 「そのフラグが artifact を gate している」ことは代表 1 葉のレンダで検証（L2）
   - 受け入れ: 6 本の render 掃引が消え、同じ不変条件が L1 + 代表 1 render で担保される。
     ガードのガードとして、`when` を 1 つ壊すと新しい L1 検査が fail すること

2. **T10: コスト台帳の陳腐化を検出する**（P7 の残り）
   - 現状 `test_marker_drift.py` は**件数**しか見ないので、`wall_seconds` が古くても緑のまま。
     2026-09-14 に実際「4 tier すべて同値」の未測定値が入っていた（§26.2）
   - 変更: `measured` の日付が N 日（例 30）より古い tier を fail（または警告）にする。
     実測は並行編集で動くので「日付が古い＝測り直せ」の合図を機械化する
   - 受け入れ: 日付を N 日戻すとテストが fail し、メッセージが再測定のコマンドを出す

3. **T11: witness fast ジョブを台帳に入れる**
   - `witness.yml` の fast ジョブ（`-m fast`、205 葉レンダ）は PR ごとに走るが、
     `tiers.json` の 4 tier に入っておらずコストが未測定。CI の wall はローカルの
     `test-fast` とは別物（setup + 205 レンダ）
   - 受け入れ: `witness-fast` を台帳に足し、PR CI の実測 wall を記録、timeout（30 分）に対し
     余裕があることを確認（不足なら `--jobs` 化を検討）

4. **T6 の残り: 不変条件の単一源**（§23.4 / §24.2 の前提。**部分実装**）
   - 現状 `tools/z3_witnesses.py` の `COMMON_FILES` / `PROJECT_TYPE_FILES` / `INCLUDE_FILES` /
     `GATE_FILES` と、`tests/test_render_invariants.py` の内容述語、`tests/test_recommended_path.py`
     の MARKERS が別ファイルに散っている
   - 変更: 「葉が満たすべきファイル集合 + 内容述語 + tier + 除外理由」を 1 ファイル
     （`tests/matrix/invariants.*`）に集約し、生成器・ランナー・docs 生成が同じ源を読む
   - 受け入れ: 新しい層/枝を足すとき、編集するファイルが 1 つで済む。既存の重複 dict が消える

5. **V2: adopt/update を Quint（または TLA+）で小さくモデル化**（§25.3 の最有力スパイク）
   - 対象は骨格だけ: `backup → mutate → verify → rollback|commit` + `crash` action。
     V1 のジャーナルが**全クラッシュ点**を覆うことを反例探索で確認する
   - 受け入れ: 「ジャーナル書き込みを 1 手順削った」モデルで復旧不能トレースが出る（ガードのガード）
   - 撤退条件: fsync の順序を表現できず 1 日で形にならなければ、機構（V1）のテストで代替し、
     モデルは却下として記録

6. **V3: Crosshair + deal を merge の 1 関数に試す**（§25.3）
   - 第一対象: `file_merge.merge_ci_jobs` の「既存ジョブ不変」事後条件。実装を書き換えずに
     実 Python を SMT 記号実行で反例探索できる唯一の候補
   - 受け入れ: 反例ゼロ、または具体的な反例入力が出る。撤退条件: パス爆発で 10 分以上 → 却下

7. **V4: Hypothesis stateful で adopt を回す**（§24.3 の「採用 or 削除」を採用側で確定）
   - 既に dev 依存にあり使用 0。ランダムな木 + 操作列で「不変条件 + 参照実装一致」を検証
   - 受け入れ: 100 シーケンスが緑、かつ意図的に壊した merge で fail する

8. **T8 の残り: 外部ツールのスパイク**（§24.3 の表。各 1 本、判定は表のとおり）
   - `pytest-testmon`（要: `template/**` 変更時の全選択フォールバック）、`pytest-randomly`、
     `syrupy` / `pytest-regressions`、`pixi` の venv 共有。各スパイクは
     「置換対象 / 期待削減 / 偽陰性リスク / 撤退条件」を 1 行書いてから着手する


## 27. §26.4 の実行結果（2026-09-14 実測。残タスクは §27.7）

§26.4 の 8 項目を並行実装し、**実測で**確認した。数字はすべて 16 コアのこのマシン（負荷 60〜117 の
時間帯を含む）で、負荷条件は各項目に付記する。

### 27.1 tier とコスト（T9 / T10 / T11）

| 項目 | 結果 |
|---|---|
| T9 | `test-fast` は `-m "not heavy and not slow and not meta"`（**731 / 41s**、負荷 ~60）。drift 検査は `meta` marker + 専用 CI ジョブ `test-meta`（`timeout-minutes: 15`、`required-checks-passed.needs` 入り）へ移動。`_test.yml` は payload なので触っていない |
| T10 | 台帳の `measured` が 30 日超の行は fail。メッセージがその行の再測定コマンドを出す（back-date デモ済み）。行ごとの `command` 列を追加し、ledger / Taskfile / docs の件数一致を機械検査 |
| T11 | `witness-fast` を台帳に追加。**cold 39.4s / 1800s timeout（45 倍の余裕）** — `--jobs` 化は不要と判断 |

### 27.2 不変条件の単一源（T6 / §23.4）

- `tests/matrix/invariants.yml`（22 行）+ `tools/invariants.py`。以前は
  `z3_witnesses.py` の 4 辞書 / `test_recommended_path.py` の MARKERS / `test_render_invariants.py` の
  predicates / `support.yml` の tier 方針に散っていた事実を 1 ファイルへ統合。未知の select 値・
  predicate・tier、重複 id、どの行にも属さない葉は**読み込み時に落ちる**
- 移行で実ギャップを発見: `data/DEIDENTIFICATION.md` は fast path の MARKERS だけが主張し、
  witness の `expect` には入っていなかった（＝205 葉では消えても気づけない）→ 49 葉の期待に追加し、
  再生成（`witnesses.jsonl` が変わった唯一の理由）

### 27.3 形式手法（V2 / V3 / V4）

- **V2: 採用（範囲限定）**。`adopt` の骨格（journal → mutate → verify → rollback|commit + crash）を
  Quint 219 行で書き、TLC で 51 状態を全探索。**journal を 1 手遅らせた変種は 2/3 状態の反例**が出る。
  fsync の耐久性は表現できない（write は原子的と仮定）ので、その半分は V1 の SIGKILL ドリルが担う。
  次の一手: **rollback 中と recover 中の kill フックが無い**（`_crash_at` の呼び出しは write 時と verify 時の 2 箇所）
- **V3: 却下**（撤退条件成立）。`merge_ci_jobs` / `merge_taskfile` は 10 分の記号実行で**判定が出ない**
  （YAML パースが下流の全契約を決定不能にする）。決定版の対照実験: 契約が**具体的実行では捕まえる**
  意図的な破壊版も、記号実行では捕まえられない → CI に入れても飾り。YAML 非依存の `_recipe_blocks`
  だけは 1 分 50 秒で実反例を出した（採用しない理由はレポート §5）
- **V4: 採用**。Hypothesis stateful（100 シーケンス / 312 ルール実行 / 毎ステップ不変条件）が
  **編集ループ 17s** で回る。モデルは実装のヘルパーを呼ばず自前の tomllib/regex で読む。ガードのガード済み

### 27.4 外部ツールの判定（T8）

| ツール | 判定 | 根拠 |
|---|---|---|
| `pytest-testmon` | **却下** | `-m` と併用で選択が自動無効（この repo の fast tier はまさに `-m`）。さらに `.jinja` を追跡せず、`template/CHANGELOG.md.jinja` に 1 行足しても **26 件の render テストが選ばれない**（偽陰性を実測）。testmon は coverage トレーサ由来でデータファイルを読まない |
| `pytest-randomly` | **採用（夜間 seed ジョブとして実装済み、§27.7-7）** | 8 回のランダム順で順序依存は出ず（xdist/serial 両方）。`-p no:randomly` を addopts に入れて全 tier 既定で無効化し、夜間ジョブ（ci.yml schedule の `test-randomly`）だけ `-p randomly` で有効化。実測 50.3s（741 テスト、seed はヘッダに出力） |
| `syrupy` / `pytest-regressions` | **不要** | pytest 9.1.1 で動くことは確認したが、この suite は render の byte / 解析結果を見ており、snapshot は audit が意図的に消した「文言固定」に戻る |
| `pixi` venv 共有 | **不採用**（実測 §27.7-7、詳細は `/tmp/spike-tools/REPORT.md` も参照） | 節約より危険が先に実測された: 共有 `UV_PROJECT_ENVIRONMENT` + `--inexact` は `-n auto` の下で **2.2-2.4 倍遅い**（28.5-30.3s → 63.9-71.7s。1 env = 1 本の uv 環境ロックで venv 作業が直列化）うえ、ベースラインでは出ない失敗が毎回 5-9 件（別ワーカの sync が editable を付け替え、他葉の木を collect）。依存差の偽陽性も単体で実測: 葉の lock から依存を除しても共有 env は生成 pytest 8/8 を通し、隔離 env では 2/8 失敗 |

### 27.5 スパイク・stateful 実行が見つけ、その場で直した欠陥

- **`merge_taskfile` が parse 不能な Taskfile を書いて applied=True を返す**（CrossHair の
  property を書く過程で発見）: 検証が「元からあったタスク」しか見ないため、`tasks: {}` や
  parse 不能な target では**空虚に真**になり、インデントしたブロックを追記して壊していた。
  → 追記後に「parse できる」かつ「追記したと主張したタスクが全部ある」を要求し、破れば巻き戻す
- **`pyproject_merge` が malformed な target を誤診・例外**: (a) 元から parse しない
  pyproject を「マージが壊した」と報告して adopt 全体を拒否していた（before の parse 検査を
  after より後にやっていた）→ 順序を修正。(b) `dependencies = "httpx"` / `= 5` が
  append ループで AttributeError / TypeError になっていた → 形を各セクションで検査し、
  位置を名指しした note で残りを続行
- **`test_batch.py` の load 依存 flake**（3.01s vs 3.217s）→ stopwatch 比較をやめ、
  **ハンドシェイク**（互いに相手が in-flight でなければ完走できない 2 リクエスト）で並行性を証明

### 27.6 PLAN §7 完了条件

**8 件すべて達成**。最後の 1 件（README <130 行 + TL;DR）は **522 → 120 行**、カタログは
`docs/reference/features.md` へ移動（生成ブロックも一緒に移動、`gen_docs --check` 緑、リンク解決済み）。

### 27.7 残タスク（2026-09-14 時点）

1. [x] **V5 / T6 の残り**: merge の事後条件を invariants.yml 側へ（現在は実装内の検査）
   → **完了（2026-09-14、2a907080）**: `invariants.yml` に `merges:` 節（kind →
     保証する事後条件のレジストリ）を新設し、`tests/test_merge_contracts.py` が
     条件実装を持ち、dispatch と双方向に照合（kind と契約の片方欠けで fail）。
     各条件は benign merge で成立 + 自身の違反の検出を二重証明（guard-the-guard）。
     レジストリは事実を記録: pyproject マージは tomlkit の再整形のため
     `original_is_prefix` を保証しない（契約は idempotent/existing_declared/reparse）
2. [x] **V2 の次の一手**: rollback / recover 中の kill フックを `tools/adopt.py` に足し、
   Quint が証明した「全クラッシュ点が覆われている」をテストでも標本化する
   → **完了（2026-09-14、23a84342）**: `_crash_at("rollback" / "recover")` を追加し、
     SIGKILL ドリル2本（rollback からの byte-identical 復元 / recover の収束、両 recover
     部分状態を parametrize）+ stateful マシンに専用 rule 2本で標本化。
     ついでに stateful モデルの潜在バグを1件修正（`start_a_project` だけ
     `pending_journal` ガードが無く、kill 後の journal を model が取り消していた。
     ドライバは無関係）。fast tier に +3 テスト / +5.5s
3. [x] **Quint モデルを CI へ**: モデル 2 本（+変種）を `models/` に置き、repo-only workflow で
   `quint verify --backend=tlc`（~2s）。Node 22 + quint 0.32 が前提
   → **完了（2026-09-14、7901cbc1）**: `models/{adopt_crash,adopt_crash_journal_late}.qnt`
     + `quint.yml`（quint 0.32.0 pin）。良モデルは 51 状態で不変成立、journal 遅延変種は
     3状態の反例が出ることを CI が毎回確認（変種が通ったら job を落とす二重ガードつき）。
     TLC は JVM を要するため ubuntu-latest の preinstalled Temurin に依存（README に記載）。
     `.gitignore` の `models/*` に否定パターンを追加、zizmor の `adhoc-packages` 監査は
     文書付き ignore で例外化。マージ後に `.gitignore` の union 検査が赤化したため
     テンプレ側へもミラー（7d7b6e84）
4. [x] **§23.1 の残り**: answers の単一情報源、`test_example.py` の分割（所有権メモが解けたら）。
   `tests/support.py` 共有モジュールの第一スライスは完了（a30747e8: `run_pipe` / `make_venv`
   を test_example から移設、importer 改線、marker スキャンの edge 追従を meta tier で実証）
   → **完了（2026-09-14）**:
   - **answers の単一情報源（75e3254e）**: `tools/answers.py` の `BASE` を7箇所
     （test_recommended_path / test_mcp_server / test_batch / copy_project_recommended /
     z3_witnesses / example-answers.yml / batches/base.yml）の共有源にした。`repo_name` /
     `distribution_name` は copier の導出に任せて BASE から外し、葉の answers を持つ
     `witnesses.jsonl` / `witnesses.json` を再生成（描画は同一）。drift ガードは
     `tests/test_answer_fixtures.py`（未知の質問名・choice 外の値・gate-off の維持・
     `batches/base.yml` と BASE の一致）。派生名を fixture から読んでいた
     `test_render_invariants.py` は描画自身の `.copier-answers.yml` を読む形に変更（e62d0e89）
   - **分割（29344b39）**: 2,177 行 / 135 ノード → 質問票の軸で10モジュール
     （example_{library_cli,web_api,data_science,oj,layers,docs_ci,adopt,ros2,micropython,toolchain}）。
     本体は移動のみ（差分ゼロを `--collect-only` の関数名 858 件一致で実証）。共有ヘルパは
     `tests/support.py` へ（TOP / copy_project / copy_project_recommended / ci_requested_tasks）
   - **未着手**: venv の session 共有（`@pytest.fixture` 0 のまま）。PLAN §W9-3 の計測が前提
5. [x] **§23.2 の残り**: CI の `paths:` フィルタ
   → **完了（2026-09-14、f4838b75）**: required check になる ci.yml の test / test-meta は
     job 単位ゲート（`changes` job の `docs-only` 出力。skip は branch protection で
     success 扱い）とし、required でない witness.yml / update-path.yml は workflow 級の
     `paths-ignore: [docs/**, **/*.md]`。pyproject-only は意図的にゲートしない
     （renovate の bump こそ fast tier の捕まえるべき変更）。test-loop.md に記載
6. [x] **§23.4 の残り**: 列挙の完全性（除外リストをカバレッジ出力に載せる）、`witnesses.jsonl` の陳腐化検出
   → **完了（2026-09-14、bb6a9e53）**: 除外は invariants.yml の `excluded` 節が単一源
     （web_django + integration 質問2件、理由つき。load 時に questionnaire と照合して腐ったら落る）。
     coverage 出力は「205 enumerated, 3 excluded (<names>)」を明示。
     `witnesses.jsonl` は in-process 再導出で陳腐化検出（失敗時に `task witness` を表示）。
     再導出の結果、現行ファイルは新鮮と実証
7. [x] **T8 の残り**: `pixi` venv 共有の採否、`pytest-randomly` を夜間ジョブに入れるか
   → **完了（2026-09-14、両方とも実測で決着）**。
     - **pixi / `UV_PROJECT_ENVIRONMENT` 共有 + `--inexact` は不採用**。`-m heavy` 43 テストを
       16 core・ウォームキャッシュで実測: 現行の葉ごと venv は 28.5s / 30.3s、共有 env は
       **63.9s / 71.7s（2.2-2.4 倍の悪化）**。16 xdist ワーカが 1 本の環境を取り合うため venv
       作業が uv の環境ロックで直列化され、スパイクが見込んだ 5-7% の節約（隔離 12.3s → 共有
       2.1s）は並列の下では符号が逆になる。さらに共有モードだけで毎回 5-9 件の失敗
       （ベースライン 2 連続は全緑）: `uv run` の暗黙 sync が走っている隙に別ワーカの sync が
       editable を付け替え、web_api 葉の生成 pytest が `No module named 'app'` で他葉の木を
       collect した。§24.2 が禁止する「case A の依存欠けを case B の env が満たす」も単体で
       実測: ある葉の lock から structlog を除して共有 env で走らせると生成 pytest は 8/8 パス
       ・basedpyright も 0 エラー（漏れマスク）、同じ木を隔離 env で sync し直すと 2/8 失敗 +
       `ModuleNotFoundError`。安全な代替は env 共有ではなく**キャッシュ共有**
       （`UV_CACHE_DIR` 保持 + 葉ごと env。uv の hardlink が既にそれに近い安さ）であり、
       env 共有が正しいのは「分布名が異なり依存集合が同一の葉」のときだけ —— このサンプルは
       その逆のために存在する
     - **pytest-randomly は夜間 seed ジョブとして採用・実装**: dev dep（5.0.0、`>=5.0,<6`）、
       addopts に `-p no:randomly`（全 tier 既定で無効。編集ループは払わない）、`task
       test-randomly` だけがコマンドラインで `-p randomly` を渡して再有効化。ci.yml の
       schedule に `test-randomly` ジョブ（test-heavy の隣、`_test.yml` 経由なので SHA ピン/
       permissions 契約はそのまま）。seed は毎回新規でヘッダに出力。実測 50.3s
       （741 テスト、順序依存なし）。台帳側は test_marker_drift.py が「`-p randomly` を払う
       タスクは test-randomly 一つ」と構造で固定し、tiers.json に test-randomly 行を記録
8. [x] **`task test`（全 879 件）を `-n auto`（32 ワーカ）で回すと、full tier の docs ビルドが
   無音で空の `site/` を残す**（2026-09-14 実測。CI の選択には出ない）
   - 症状: `test_witness_full_tier[...]` が「the docs build produced no site/ output」で
     1〜5 件落ちる（毎回同じ葉ではない）。失敗メッセージに出力を足して分かったのは、
     `uvx --from rust-just just docs` が **rc=0** で、`site/` は**空のまま**（dir だけできる）。
     落ちたディレクトリで同じコマンドを手で回すと 0.2s で 4 ファイル出る（zensical は正常）
   - **今日のコミット由来ではない**: `acb9af30` の内容に戻した同じ木でも 3 件落ちた。
     `-n 8` は全緑、単体実行も緑（12s）。`-n auto` の負荷下だけ再現
   - 単純な uvx 競合説は否定: 自明な justfile のディレクトリで `uvx --from rust-just just docs`
     を 32 並列で回しても無音 no-op は 0 件。プロジェクト venv と docs ビルドまで含めた
     負荷でだけ起きる
   - 副作用が本体: 落ちた verdict は `tests/matrix/witnesses.json` に `fail` として残り、
     fast tier の
     `test_support_matrix.py::test_supported_combinations_have_a_recorded_full_tier_pass`
     まで赤くなる（クリーンな `-n 8 -m full` で消える。今日は赤→緑を 2 往復した）
   → **解決（2026-09-16、485f3618）**: 根本原因は zensical のファイルウォッチャ。
     one-shot の `build` を inotify ウォッチャ経由で駆動し、ウォッチャを起動できないと
     無音で死ぬ（monitor スレッドが panic → 入力チャネルが切断 → "Build finished" を
     出して rc=0、`site/` は空のまま）。引き金は 1 ユーザーあたりの inotify インスタンス
     上限（128。ボックスの全プロセスと共有）の枯渇で、本 suite を `-n auto` で回す
     dev box が普通に到達する。`tests/support.py` に `build_docs` を新設し、
     `ZENSICAL_POLL_WATCHER=1`（zensical 公認の no-inotify フォールバック）で 1 回だけ
     再試行する。両試行の出力を assert に載せたので、「マシンがウォッチャを拒んだ」
     （再試行で緑）と「render の docs ソース/設定が壊れた」（どちらの試行も 1 ページも
     書かない）を区別できる。恒久策としていた「full tier の並列度を明示」は不要になった

### 27.8 逆テンプレの旗艦クエリに答える葉を足し、その過程の drift を直す（2026-09-16）

`include_mcp` は `use_recommended_integrations` の裏の詳細質問で、Z3 の投影
（gate × include layer × project_type）には乗らない。全葉がデフォルト false のまま
だったので、「docker + MCP」を要求する逆テンプレの旗艦クエリ
（`--require docker=true --require mcp_effective=true`）に答えられる葉が 1 本も無かった
（§18.8 の残り）。

- **葉空間の派生**（`tools/z3_witnesses.py`）: integrations gate を切った web_api 葉 3 本
  それぞれに、その gate の詳細を選んだ変種葉を 1 本導出（`DETAIL_VARIANTS` = docker +
  include_mcp を on）。web_api 限定なのは mcp_effective が成立するのがそこだけだからで、
  scaffold は固定の `app/` に生えるので 1 行で全配置を主張できる。225 → 228 葉。
  宣言先は invariants.yml の新行 `gate_off=use_recommended_integrations/details-chosen`
  （ships: `.mcp.json`, `app/mcp_server.py`）。`include=include_mcp` 行は src/flat 配置
  専用に `web_api: false` で絞り、`excluded` から include_mcp を外した（残りは
  include_sentry 1 件）
- **単一源**: 詳細変種が答える名前は `DETAIL_VARIANTS` 1 箇所。導出（`build()`）・含有
  チェック（`_check_includes`）・証人側の検証（`test_excluded_names_hold_*` は「宣言された
  質問が実際に列挙葉で true になっているか」を列挙葉から確かめる）が全部そこを読む。
  leaf_space の `restrictions` にも変種の規則を 1 行足した
- **葉数を二重管理していた assert を派生に**: `test_mcp_server` は jsonl の id 数、
  `test_update_rehearsal` は台帳の `coverage.total`（+ 225 の下限ラチェット）と比較。
  葉空間が動いても「数え直し忘れ」では落ちず、落ちるのは実体がずれた時だけになる
- **render_delta が葉空間の変化で落ちていた**（この作業で発見。slow tier の
  `test_verify_delta_proves_an_untouched_tree`）: ベースラインが宣言していない葉を
  `_render_side` が描画しようとして KeyError。修正は (a) 宣言に無い id はスキップ、
  (b) 片側にしか無い葉は added / removed として名指しし diff failure にはしない
  （比べる相手が無いだけで、render が変わったわけではない）、(c) diff の集合内包が値を使わない
  死んだ dict 内包だったので set 内包に。さらに `_context_hashes` が copier の context
  全体（`_src_path` / `_commit` / `_copier_conf`（LazyDict の repr = アドレス）/
  `_copier_answers` / `_folder_name`）をハッシュしていたため、両側が同じ cache entry を
  共有しない状況——まさに葉空間を変えた時——では 228 葉すべてが候補になり semantic diff の
  絞り込みが消えていた。実測（同一解答を baseline worktree と TOP で描画）: context 全体は
  不一致、public entry（解答とそこから導かれた internal）だけなら一致。よって public entry
  のみをハッシュし、`CONTEXT_HASH_SCHEME` で cache を版管理する。回帰テストは crafted state の
  `_classify` 2 本 + 上の slow 統合テスト（candidates == 追加葉数）
- **台帳の再収集**: `UPDATE_TIERS=1` で葉数の動いた 4 行（test-fast / test-randomly / test /
  witness-fast）を再収集し、wall_seconds/measured も実測で置き換えた（当時の静箱・ウォーム
  キャッシュ: witness-fast cold 11.2s（warm 3.3s）/ test-fast 25.8s / test-randomly 24.7s /
  test 159.7s）。§27.9 のテスト追加でもう一度再収集しているので、最終値は tiers.json を正とする。
  test-loop.md の tier 表と prose も追随。225 を読んでいた記述
  （tools / tests / Taskfile / docs / 生成 block）は 228 か「葉空間」に置換し、歴史記録
  （205 葉の 2026-09-13 監査など）は日付つきのまま残した
- **実証**: 旗艦クエリは 3 葉に一致（web_api base / +bot / +data_science）。
  `task test-fast` + `task test-meta` green、`-m slow` green（228 葉の serial batch 判定と
  render twin）、lint / type-check / `zensical build` / `gen_docs --check` green

### 27.9 生成 README / 導入ドキュメント / 生成 CI の実バグ（2026-09-16）

節20 の `- [ ]`（生成ドキュメント・質問票の小粒改善・導入導線）と、節19 の runner 分岐の
残りを処理した。render では見えない「ユーザーの生成物が壊れる」修正が2つ含まれる。

- **生成 README の3点**（`template/.../README.md.jinja`）:
  - `**pkg** is a Python package that ...` のプレースホルダ行を削除（タグラインが既に
    `description` を出している）。NOTE は「tagline は `description` 回答で、置き換えるのは
    下の features」と実在のプレースホルダだけを指す文に
  - `<details> Platform-specific setup`: web_api は `uvicorn` が全 OS 同一なので表をやめて
    1 コマンドに、他は「Windows は `py`」という差の理由を1行添えた表に。直後の余分な空行も除去
  - docs 無効時の `See [how-to guides](.github/CONTRIBUTING.md)` → ラベルとリンク先を一致
    （`See [CONTRIBUTING.md](.github/CONTRIBUTING.md)`）。GitLab 版が当該ファイルを
    ship しない件は `template-dev.md` の GitLab スコープ節に既知の残りとして記載済み
  - 実測: `copier copy --vcs-ref=HEAD` で web_api / cli / gitlab+docs-off を render して確認
- **create-new.md**: commit 手順の `uv sync` 固定を、回答→install コマンドの表
  （uv / poetry / pixi / ros2+apt の `rosdep install` / micropython の `--target typings`）に。
  `example-answers.yml` を preset 節と raw copier 節から、`reference/questionnaire.md` の
  冒頭注記から link（何をする fixture かも1文で）
- **導入導線の残りは解消済みを確認**: `--vcs-ref=main` は docs/README から 0 件、
  adopt-existing の skeleton / 非 skeleton 経路は別節で整合、2 flag を隠す wrapper は
  `python-copier-template new`（`tools/cli.py`）がそのもので README TL;DR が第一導線に置いている
- **生成 CI の実バグ（invoke/duty）**: `.github/workflows/_test.yml` / `_docs.yml` の
  `case "$TASK_RUNNER"` に invoke/duty が無く、その toolchain を選んだ生成物の CI が
  `Unknown task runner` で落ちていた（`_tasks.yml` には有った。workflows は
  `template/.../workflows/` の symlink で生成物にも入る一式）。両方に poetry.lock 分岐つきの
  branch を追加し、input description の列挙も追随
- **再発防止と実走**: `test_every_runner_switch_handles_every_task_runner_choice`（fast）が
  3 workflow の switch を questionnaire の全 choice + pixi と照合し、loud-fail の存在も検査。
  `test_test_task_executes_on_invoke_and_duty`（heavy+network）が生成物で
  `uv run --locked invoke|duty test` を実走（`test` は `_test.yml` が毎 push で叩くタスク）
- **台帳**: 追加テストで 4 行を再収集・再実測（test-fast 889 / test-randomly 889 /
  test-heavy 49 / test 954。他セッションが同居した負荷下の値なので note に明記）
- **render twin の前提を明示**: 作業ツリーが base と一致しない時（今回のように
  テンプレ本体を編集中）は `test_verify_delta_proves_an_untouched_tree` が skip し、
  twin が見つけた差（今回は 225 葉が README.md を再レンダー）をメッセージに載せる。
  常時要求するのは `proven + failures == leaves`（全葉の会計）だけで、prove-clean は
  base と一致する木に限る。一致木での実測: 作業ツリーを一時 worktree に commit して
  `tools/render_delta.py --base HEAD` を実走 → `228 leaves, 0 candidate(s) re-rendered
  against HEAD` と `PROVEN render-identical: ... 228 unaffected`



---

# 監査メモ（2026-09-18、TODO.md 索引から移動 — §B 残件の着地状況）

> **2026-09-18 監査メモ**: §28 の 41 項目がすべて着地した時点での現状確認。
> (i) §19 の小項目 2 件（z3 の `importorskip` 黙り skip / hypothesis ゼロ使用）は
> **すでに後続作業で解決済み**（test_when_model.py:64 の必須化コメント、
> tests/test_adopt_stateful.py の RuleBasedStateMachine 使用）。(ii) §23 の
> `render_project` 戻り値拡張は原文が「優先度低（render_diff と利便性重複）」と
> 判定済みだったが **2026-09-18 に着地**（mcp_server.render_project が
> `{path, sha256}` を返し、`diff_against` で過去レンダとの manifest 差分
> （render_diff 同型・スタンプ mask 付き）を出力）。手書きテスト→不変条件の
> 棚卸し残り（§26.4-1b T12 の render sweep 6 本の L1 移し）も **2026-09-18 着地**
> （test_example_layers.py の FLAG_TABLE + Worker._ask 共有パス。13 render を撤去、
> ガードのガード付き）。§19 の composite action 化も **2026-09-18 着地**
> （.github/actions/setup-runner/action.yml 新設、_tasks/_test/_docs/_dist を
> 置き換え、template symlink で生成物にも同梱、workflow security pin 追加。
> 生成物 CI の初回実走確認のみ残留）。§15 の zizmor version: latest 教訓は
> security.yml.jinja への cli ピン追加で解消。残る §B は CI 緑確認・バッジ・
> Periodic・未検証組合せ（push と run 観察が前提）。(iv') §4 の Gmail bot スライスは **2026-09-18 着地**（discord → slack → LINE に続き
> 最後の platform。`bot_gmail_effective` + `_shared/bot-gmail.py.jinja`（OAuth +
> ポーリング、/ping に pong 返信）、google-* 依存、.env/.gitignore/scripts/
> Docker/tasks/docs 一式、生成テスト + fake transport。228 葉は不変、非 gmail 葉の
> バイト同一を twin で実証）。「1つずつ潰す」計画はこれで完結。
> (iv) 機能の将来拡張の残り（5 件）と公開・運用手順（14 件）は
> リリース時・利用時の手順であり、コード変更では解消されない。
> (iv'') 追加発見の修正（2026-09-18、Gmail スライス中に発見）:
> `tests/render_cache.py::_record_inputs` は `{{ pkg_dir }}` 配下の template
> source を消費集合に記録できていなかった（output_name が tag 剥離で先頭 `/` を
> 残し厳一致が生成物名と交差しない）。`_shared/bot-*.py.jinja` 等 pkg 木所有の
> 共有 body への編集が bot render のキャッシュを無効化しない実害。接尾辞規則へ
> 修正（render_delta と同じ照合）+ CACHE_SCHEME v4 clean break + pin テスト
> （tests/test_render_cache.py::test_a_pkg_dir_body_partial_is_recorded_and_invalidates）。よって §B は
> 各自の着手条件が到来するまでアーカイブのまま残すのが正。
> (v) §17 の「library の空依存を維持するか質問化するか」は **維持で決着**: 依存は
> 既存の `log_library` 質問の出力であり、「ゼロ依存」は `logging` 選択として既に
> 存在する（pin:
> tests/test_example_library_cli.py::test_template_library_dependencies_come_from_the_log_choice）。
> (vi) §21 の upstream fork PR は原文が「投稿は手動で行う（エージェント投稿禁止）」と
> 明示する人間タスク。これらの着手条件（CI 実走・detach・GitHub 操作・投稿）が
> 到来するまで §B はアーカイブのまま残すのが正。
> (vii) 追加改善（2026-09-18、§28 完結後の追い込み）: **bot platform を葉空間へ**
> （228 → 234 葉）。predicates 分類器が `bot_slack_effective` / `bot_line_effective` /
> `bot_gmail_effective` を「0/228 葉で不発 — 決して分割しない」と報告していた穴。
> 投影軸は `use_recommended_bot` を gate として運ぶが `bot_platform` は運ばず、
> gate オフ葉（cli / web_api の 2 葉）は既定 discord のままになる — a515149a が
> docker + MCP を `DETAIL_VARIANTS` で足したのと同型のギャップ。`BOT_PLATFORM_VARIANTS`
> （slack / line / gmail）を新設し、`use_recommended_bot` オフの各葉から 1 葉ずつ派生
> （discord は基底葉自身が担う）。invariants スキーマに `bot_platform` select キーを
> 追加（選択肢と既定は Vocabulary が質問票から読む。NAMED_SELECT_KEYS は
> project_type / oj_kind / include / gate_off / bot_platform の 5 つ。既定を受ける葉は
> 次元を主張しない = include/gate_off/oj_kind と同じ規則）、ベース 2 行に
> `bot_platform: [discord]` を付けて新規 6 行（cli / web_api × slack / line / gmail、
> 兄弟平台ファイルの absent 付き）を追加。witnesses.jsonl 再生成（234）+ 台帳再記録
> （witness 240 / test-fast 942）+ 228 → 234 の参照を docs / コメントに同期。
> 検証: witness fast 240 passed（`.cache/renders` を空にして cold 16.9s）/ predicates が
> 3 つの `bot_*_effective` の分割（2/234 ずつ）を報告 / lint / type-check 5 種 / meta 10
> passed / docs sync 10 blocks / test-fast 25.6s（予算 30s 内。cold cache で 34.1s は
> 測定条件として台帳ノートに明記）。
