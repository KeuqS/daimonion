# PLAN: このOSSが広く普及・愛用されるための拡大戦略と実践ロードマップ

対象リポジトリ: `ConstitutiveTemplates/daimonion`（2026-10-04 策定。旧 `kasi-x/python-copier-template`）
関連ドキュメント: `TODO.md` (§36, §37)、`notes/Strategy.md`、`notes/SPEC-adoption.md`、`docs/explanations/vision.md`、内部 `HUMAN_TODO.md`（人間作業のチェックリスト — 2026-10-13 に kasi-x/daimonion-internal へ移設）

---

## 0. 診断: 驚異的な技術的完成度と、普及におけるギャップ

### 0.1 本テンプレートの技術的資産
- **SMT (Z3) による質問空間の形式検証**: 質問票の論理式（`when:`）を Z3 で充足可能性証明。デッドコードやタイポを数学的に排除し、272葉の証人空間を完全網羅。
- **5次元×4タイミングのMECEドリフト検知**: コード無変更でも経年劣化（ツールチェーン進化・依存更新・上流変化）で壊れる問題を、定期スケジュールCI等で自動検出。
- **AIコーディングエージェント共創基盤（AGENTS.md）**: 各プロジェクト種別・ルールに即した `AGENTS.md`、倫理・法務レジストリ（EU CRA, SAMD, PKI, ライセンスドリフト）を動的コンパイル。
- **エンタープライズ級のサプライチェーン保護**: 全 GitHub Actions の SHA 固定、zizmor 監査、OpenSSF Scorecard 高得点基準。
- **安全な既存プロジェクト採用（Adopt）**: 衝突検知、既存資産保護、トランザクション適用とロールバックを備えた `adopt.py`。

### 0.2 普及を妨げている「5つの壁」
1. **フォーク属性とブランドの壁**: GitHub 上で `DiamondLightSource/python-copier-template` のフォーク表示。名称が一般名詞のまま（固有の存在として認知・言及されにくい）。
2. **導入・試用体験の摩擦（UX）**: README の先頭が「リポジトリを `git clone` してローカルCLI実行」。高度な数理専門用語（SMT/Z3/272葉）が前面に出過ぎており、ライト層が「大げさすぎる」と離脱。
3. **卓越した技術力の対外未発信**: Z3検証、ドリフト検知、AGENTS.md 等の独創的仕組みがリポジトリ内ドキュメントに埋没し、外部コミュニティ（Hacker News, Reddit, Zenn, Qiita）に届いていない。
4. **既存導入（Adopt）の埋没**: 最大のキラー機能である「既存プロジェクトを壊さず近代化する（`adopt.py`）」がローカルスクリプト扱いになっており、世界中の既存リポジトリへ届くワンライナーになっていない。
5. **ソーシャルプルーフと貢献の敷居**: Showcase（採用リポジトリ一覧）の不在。質問票変更に6コマンドを要する保守コスト（§36）により、Bus Factor = 1 の状態が継続。

---

## 1. 普及のための6大戦略（Pillars）

### P1. アイデンティティ確立とリブランディング（Brand & Identity）
- **脱フォークと独立リポジトリ化**:
  - §11/§16 の合意を実行。`git checkout --orphan` または GitHub Support 申請でフォーク関係を解除し独立。
  - 由来（DiamondLightSource, python3-pip-skeleton）は NOTICE / README / docs に明確に刻み、正統性を確保。
- **固有ブランド名の策定**: 会話やSNSで指名しやすく、検索性の高い固有名称（例: `copier-python-hypermodern` / `agentic-python` / `proven-python` 等）。
- **2026年の最前線ポジショニング**:
  - 「**AIコーディングエージェント共創時代の、数理検証された高信頼Pythonテンプレート**」
  - 開発停止した `cookiecutter-hypermodern-python`（1900+ stars）の正統後継としての旗幟。
  - `copier-uv`（ライブラリ特化）との住み分け: 「単機能ライブラリなら copier-uv。実務全般（Web API / Data Science / CLI / 競プロ / 組込）× AIエージェント × 堅牢性なら本テンプレート」。

### P2. 導入体験（UX）の極小摩擦化（Zero-Friction Onboarding）
- **ゼロインストール・ワンライナーの前面化**:
  - `git clone` 前提の手順を即時廃止。README 先頭を `uvx copier copy --trust gh:<org>/<repo> my-project` に刷新。
  - CLI（`daimonion`）のパッケージ構成を整理し、`uvx --from git+... daimonion new my-project --preset library` を可能に。
- **プリセット主導の「3秒スタート」体験**:
  - 質問票の第1問目で「推奨プリセットから選ぶ（Web API / CLI / Data Science / Library / Minimal Bare）」を案内し、1回のリターンキーで即座に走る体験を提供。
- **既存プロジェクト近代化ツール（Adopt）のワンライナー化**:
  - `uvx <name> adopt .` を提供。「すでにあるリポジトリに Ruff、basedpyright、GitHub Actions CI、AGENTS.md を安全に追加する」ユースケースを開放（アドレス可能市場が新規作成の10倍に拡大）。
- **視覚的証明（Visual Proof）**:
  - 15秒のターミナルGIF（vhs）: プロジェクト生成から `task check` が爆速でパスし、`AGENTS.md` が配備される様子。
  - GitHub "Use this template" ボタン用のクリーンなテンプレートリポジトリ（exampleプロジェクト）の整備。

### P3. 技術的特異性の対外発信・エバンジェリズム（Technical Content & Buzz）
- **3大キラー技術記事の公開（英語・日本語）**:
  - 記事1: **"Why we used an SMT solver (Z3) to mathematically verify our Copier template's 272 question combinations"**
    （Hacker News / Reddit r/Python / Lobsters 向け技術ディープダイブ。テンプレート業界初のアプローチとして技術者の知的好奇心を刺激）
  - 記事2: **"Continuous Drift Detection: How we keep generated Python projects from rotting across 5 failure dimensions"**
    （ツールチェーン進化でコード無変更でもCIが壊れる問題への解法。DevOps/SRE/メンテナ層に響く）
  - 記事3: **"The AI-Agent-Native Project Template: Why every Python project in 2026 needs AGENTS.md and verified constraints"**
    （Cursor, Claude Code, omp, Codex 時代の必須インフラとしての訴求。Zenn, Qiita, X/Twitter, Dev.to）
- **エコシステムカタログ・リストへの登録**:
  - `awesome-python`, `awesome-copier`, `awesome-uv` への PR 提出。
  - Astral 公式 Discord や Python コミュニティ（PyCon, Python Weekly, Python Bytes ポッドキャスト）への露出。

### P4. 2026年キラーユースケースの研磨（Use-Case Excellence）
- **AI / LLM / Agent 開発者向けスタックの強化**:
  - プリセットに `preset: mcp-server`（MCPサーバー開発特化）を新設・前面化（AIツール作者層の獲得）。
  - すでに持つ bot platform（Slack/Discord/LINE/Gmail）や web scraping との組み合わせを「AIエージェントの道具箱」として位置づけ。
- **モダン・データサイエンス環境の強化**:
  - §35 で Colab 対応を確認済み。2026年標準の `marimo`（モダン・リアクティブ・gitフレンドリーなノートブック）対応や Quarto 連携の強化。
  - Poetry や Conda の重さに疲弊したデータサイエンティスト層に uv 爆速環境を提供。
- **Web API の実用性向上**:
  - FastAPI + Docker + Pydantic v2 + Sentry + OpenTelemetry/Prometheus。

### P5. コミュニティ基盤とコントリビューター育成（Community & Lowering Barriers）
- **§36（S1〜S4）の着実な実行**:
  - `task regen`（S1）の導入で、質問票変更の手間を1コマンドに集約。
  - blast-radius レダー（S2）と Contributing 101（S4）の整備。
- **「コードを書かない/小さく書く」貢献の受け口**:
  - 倫理/法務セクション（`_shared/ethics/`）の一次情報ウォッチ・ドラフト作成。
  - プリセットの追加、ドキュメント改善。
  - `good first issue` を常に5〜8件維持。
- **Showcase / "Used by" ギャラリー**:
  - 本テンプレートを採用しているオープンソースプロジェクト一覧を README/Docs に掲載。
  - ドッグフーディング成果の可視化。

### P6. 信頼と品質のエンタープライズ級アピール（Trust & Enterprise Reliability）
- **アップデート検証（Rehearsal）の可視化**:
  - テンプレート利用者の最大の恐怖「将来テンプレートを更新したときに自分のプロジェクトが壊れるのではないか？」。
  - 「全272葉でタグ間アップデートが機械的にリハーサルされている」事実を明示し、安心感を提供。
- **OpenSSF Scorecard 高得点の前面化**:
  - SHA固定、zizmor、最小権限トークンによる強固なサプライチェーンセキュリティ。企業の基幹システムでも採用できる品質。

---

## 2. 具体実装方針（Implementation Specifications）

### 2.1 ゼロクローン・ワンライナー化（P2）の実装方針
1. **README.md の構成刷新**:
   - `TL;DR` を冒頭に引き上げ、最優先の生成コマンドを `uvx copier copy --trust gh:<org>/<repo> my-project` とする。
   - プリセット指定: `uvx copier copy --trust --data-file https://raw.githubusercontent.com/<org>/<repo>/main/presets/web-api.yml gh:<org>/<repo> my-project` または copier の answers 引数連携、もしくは CLI。
   - 旧来の `git clone` 手順は「Advanced / Contributing」節へ後退。
   - `vhs` (Charmbracelet) を用いた 15 秒のターミナルデモ GIF（`demo.gif`）を生成し、README ヘッダに埋め込み。
2. **CLI のスタンドアロン・リモート対応**:
   - 現状 `tools/cli.py` は `TOP = Path(__file__).resolve().parent.parent` でローカルリポジトリを前提としている。
   - **改善**: `cli.py` において、ローカルに `copier.yml` が見つからない場合は自動的に最新リリースタグのリモート git URL（`https://github.com/<org>/<repo>.git`）をテンプレートソースとして Copier に渡すフォールバックロジックを実装。
   - `pyproject.toml` に `dependencies = ["copier>=9,<10", "pyyaml>=6.0,<7"]` を最小限のランタイム依存として定義（現状は `dev` のみに存在）。
   - これにより `uvx --from git+https://github.com/<org>/<repo>.git <cli-name> new my-project --preset library` や PyPI 配布時の即時実行が実現。
3. **Adopt のリモート・ワンライナー対応**:
   - 既存プロジェクトのディレクトリ内で `uvx <cli-name> adopt .` を実行した際、リモートテンプレートを一時クローン/キャッシュして衝突検知・トランザクション適用・ロールバックを実行可能にする。

### 2.2 メンテナンス基盤（§36 S1/S2/S4）の実装方針
1. **`task regen` を `Taskfile.yml` に新設**:
   ```yaml
   regen:
     desc: 'Run the full regeneration pipeline in dependency order'
     cmds:
       - uv run --locked python tools/z3_witnesses.py --jsonl tests/matrix/witnesses.jsonl
       - uv run --locked python tools/batch.py tests/matrix/witnesses.jsonl --jobs {{ .JOBS | default numCPU }} --quiet
       - UPDATE_TIERS=1 uv run --locked pytest -q -m meta
       - uv run --locked python tools/gen_ethics_appendix.py
       - uv run --locked python tools/gen_docs.py --write
       - uv run --locked python tools/predicates.py --json > /dev/null
   ```
   - 依存順に一括実行し、作業者が1コマンドで Definition of Done を達成できる。
2. **CI docs-only 判定の狭隘化**:
   - `.github/workflows/_hygiene.yml` / `ci.yml` において、変更がドキュメントのみの場合でも `lint`（ruff / typos / basedpyright）は常時実行し、コミット間の債務蓄積を遮断（~20秒の最小コスト）。
3. **`CONTRIBUTING.md` への「変更の blast-radius 表」と「Contributing 101」追記**:
   - 変更対象（docsのみ / テンプレートpayloadのみ / 質問票本体）ごとの必要な検証ステップを明文化。

### 2.3 独立リポジトリ化とアイデンティティ確立（P1）の実装方針
1. **リポジトリ移行手順**:
   - リポジトリ新設（例: `github.com/<org>/<new-name>`）。
   - `git checkout --orphan main-standalone` によるクリーンな履歴での独立、または GitHub Support への detach 依頼（過去 Issue 履歴を維持したい場合）。
   - `NOTICE` ファイルを新設し、DiamondLightSource / python3-pip-skeleton / copier-template の系譜と Apache-2.0 ライセンスを明記。
   - リポジトリメタデータ（`pyproject.toml`, `CITATION.cff`, `codemeta.json`, `README.md`）のプロジェクト名と URL を統一。
   - GitHub Secrets（`EXAMPLE_DEPLOY_KEY`, `PYPI_API_TOKEN`）、Pages、Branch Protection rulesets（署名コミット・リニア履歴・CI必須チェック）の再設定。

### 2.4 キラー機能・プリセット（P4）の実装方針
1. **`presets/mcp-server.yml` の新設**:
   - `project_type: cli`, `include_mcp: true`, `mcp_transport: stdio`, `use_recommended_security: true` 等の構成。
   - `tests/test_presets.py` に `test_preset_renders[mcp-server]` を追加し、sentinel ファイルをアサート。
2. ~~**`marimo` ノートブックの統合**~~: → **既存レイヤーと判明（2026-10-04）**: `data_science` の `experiment` extra に marimo 同梱済み、`task marimo`（`_tasks.jinja`）と `docs/how-to/data-science.md`「Notebooks: marimo or Jupyter」で案内済み。新規作業なし。

---

## 3. 対外アピール・エバンジェリズムの実践プロセス（Outreach & Evangelism Process）

### ステップ 1: リブランディング＆v1.0.0 ローンチ時の告知プロセス（Day 1）
1. **Hacker News (Show HN)**:
   - **タイトル案**: `Show HN: We mathematically verified a Python project template's 272 paths with Z3`
   - **投稿形式**: テキスト投稿（Show HN）。
   - **本文の構成**:
     - *Hook*: 多くのPythonテンプレートはオプションが増えるとサイレントに壊れる（組合せ爆発）。
     - *Solution*: 質問票の論理式（`when:`）を SMT ソルバ (Z3) で充足可能性証明し、272の「証人葉」を網羅テストするアーキテクチャを構築した。
     - *Features*: uv-native, ruff ALL, basedpyright, 自動生成される `AGENTS.md`、OpenSSF Scorecard 満点基準、既存リポジトリへの安全な `adopt`。
     - *Call to Action*: 1行で試せるコマンド `uvx copier copy ...` と GitHub リンク。
   - **タイミング**: 米国太平洋標準時（PST）火曜または水曜の朝 7:00〜8:00（最もHNのトラフィックと投票が活発な時間帯）。
2. **Reddit (`r/Python`, `r/programming`)**:
   - **r/Python**: `[Project] A formally verified, agent-ready Copier template for Python (uv, ruff, basedpyright, AGENTS.md)` として投稿。モデレーターのセルフプロモーションルール（通常 10% ルール）を遵守し、技術的洞察とコミュニティへの価値提供を中心に記述。
   - **r/programming**: Z3 による制約充足問題としてのテンプレート検証にフォーカスした技術重視の投稿。
3. **日本語圏（Zenn / Qiita / はてなブックマーク）**:
   - **Zenn 記事**: 『Copierテンプレートの全分岐（272通り）をZ3ソルバで数学的に形式検証した話』
     - なぜテンプレートの条件式は壊れるのか
     - Jinjaの `when` 条件を Z3 の論理式に落とし込む実装（`when_model.py`）
     - 未到達分岐やタイポを静的解析で一網打尽にする仕組み
   - トレンド入り・はてブ獲得を狙い、日本のPythonコミュニティおよびAIエージェント開発層へ一気にリーチ。

### ステップ 2: エコシステム・リスト・ポッドキャストへの掲載申請プロセス（Day 2〜14）
1. **GitHub オーガニック掲載（Awesome リスト等）**:
   - **`vinta/awesome-python`**: `Project Templates` カテゴリへの PR。既存の cookiecutter や copier-uv と並び、「SMT-verified multi-domain template」として追加。
   - **`copier-org/awesome-copier`**: 公式の Copier テンプレート一覧への PR。
   - **`astral-sh/uv` コミュニティ**: uv の Discussions（Show & Tell）や Discord の `#showcase` チャンネルでの紹介。
2. **Python 系ニュースレター・ポッドキャストへの推薦送信**:
   - **Python Weekly / PyCoder's Weekly**: 記事 URL（Z3記事やドリフト検知記事）の推薦フォームから送信。
   - **Python Bytes Podcast**: Michael Kennedy / Brian Okken へのトピック提案（「Copier template with Z3 verification and AGENTS.md」は彼らの好むユニークな切り口）。

### ステップ 3: 難民層・移行層へのピンポイント訴求プロセス（Week 2〜4）
1. **`cookiecutter-hypermodern-python` 難民の救済**:
   - `docs/how-to/migrate-from-hypermodern.md` を作成。
   - Poetry → uv、Flake8/Black → Ruff、mypy → basedpyright、Cookiecutter → Copier（更新可能）への対比表を明示。
   - Claudio Jolowicz 氏の元リポジトリの Issue / Discussions（代替を探しているスレッド）において、中立的かつ敬意を払った形で「2026年版の後継アプローチ」として言及・案内。
2. **AIコーディングエージェント開発者へのアプローチ**:
   - Cursor / Claude Code / Cline / Roo Code / omp のコミュニティや X (Twitter) で、「AIエージェントにプロジェクトを作らせる・自走させる際のベストプラクティス基盤」として `AGENTS.md` と ethics レジストリの仕組みを解説。
   - 「AIが勝手にライセンス違反の依存を入れたり、暗号化の古い規約を入れないようにリポジトリで強制する」という実務的価値を強調。

### ステップ 4: 成果の定着・フィードバックループ（Week 4 以降）
1. **Showcase（採用実績）の構築**:
   - 自分のプロジェクト（MCPサーバー、CLIツール、競プロリポジトリ）を本テンプレートで生成し、`README.md` に「採用例」として掲載。
   - 外部ユーザーのリポジトリに「Adopt」を提案する PR（またはサンプルリポジトリ）を作成し、感謝とともに Showcase への掲載許可を得る。
   - `[![Built with daimonion](https://img.shields.io/badge/built%20with-daimonion-blue)](https://github.com/ConstitutiveTemplates/daimonion)]` バッジの配布。
2. **初動の Issue / PR 体制と contributor ladder**:
   - 新規スターやフォーク、Issue が立った際は 24時間以内に丁寧に応答。
   - `good first issue`（倫理ドラフトの追加、タイポ修正、ドキュメント改善）に最初の貢献があった場合、即座にレビューして merge し、`CONTRIBUTORS.md` に記載してリテンションを高める。

---

## 4. マイルストーンと実行タイムライン

| フェーズ | 期間目安 | 主要マイルストーン | 完了基準 |
|---|---|---|---|
| **Phase 1: 摩擦の撤廃** | 1〜2日 | README 刷新（`uvx` 前面化）、`task regen`、CI docs-only 狭隘化 | ✅ 2026-10-04 実施: README の TL;DR/`new`/`adopt` を `uvx` ワンライナー化、`task regen` 新設、lint/hygiene は既に常時実行と確認、CONTRIBUTING に blast-radius 表と Contributing 101 追加、CLI リモート delegation（`uvx --from` 対応・runtime deps 追加）実装済み |
| **Phase 2: 独立・リブランディング** | 1週間 | リポジトリ detach / 新設、v1.0.0 リリース、CLI 配布対応 | 部分実施（2026-10-04）: `ConstitutiveTemplates/daimonion` として独立公開・ブランド名 `daimonion` 確定・全リネーム統一・NOTICE 新設済み。残: v1.0.0・Scorecard/branch protection・実 `uvx` 検証（人間作業） |
| **Phase 3: 対外発信・エバンジェリズム** | 2〜4週間 | HN/Reddit/Zenn 記事公開、Awesome 系 PR、移行ガイド | 部分実施: `docs/how-to/migrate-from-hypermodern.md` 新設済み。記事執筆・投稿・awesome PR は人間作業 |
| **Phase 4: コミュニティ定着・機能拡充** | 継続 | Showcase 開設、`preset: mcp-server`、Marimo 統合 | 部分実施: `presets/mcp-server.yml` + sentinel、`good first issue` 5件起票（#4-8）。marimo は既存レイヤーと判明（experiment extra + `task marimo`）。Showcase・GIF は未着手 |
