# HUMAN_TODO: 普及戦略のうち人間が実行する作業

出典: `notes/PLAN-widespread-adoption.md` / `TODO.md` §36-§37（2026-10-04）。
リポジトリ内で実装可能な項目は済（`task regen`、CLI リモート delegation、
`presets/mcp-server.yml`、README/CONTRIBUTING 刷新、foundry リネーム統一、
移行ガイド、good first issue 5件、§38 law-map 連携、実 `uvx` 検証）。
以下は権限・判断・対外発信が必要な残作業。

## Phase 2: 独立・リブランディング（目安 1週間）

- [x] **フォーク解除**: ✅ 2026-10-04 完了。delete+recreate で実施（API の
      `fork=leave` は no-op、Support/web UI は非対話不可のため）。注意:
      push protection（旧履歴のダミー slack webhook）回避のため
      `test_gitleaks_precommit.py` を履歴から除去した全書き換え — **全コミット
      SHA とタグ SHA が変わった**。タグ名参照の copier プロジェクトは無影響、
      SHA ピンのみ壊れる。gh-pages/releases/secrets/topics/Pages/issues は
      復元済み。push protection は現時点で OFF（履歴に別の疑似値が残る可能性
      への一時措置；再有効化は要判断）。
- [x] **固有ブランド名の決定**: ✅ `foundry`（`ConstitutiveTemplates/foundry`
      として公開済み）。pyproject.toml・README・CITATION.cff・codemeta.json・
      zensical.toml・workflows・docs・template jinja・tools/ の名称/URL は
      2026-10-04 に一括統一済み（残る `kasi-x/python-copier-template` 参照は
      履歴記録と example リポのみ）
- [x] **NOTICE ファイル新設**: ✅ DiamondLightSource / python3-pip-skeleton /
      copier の系譜と Apache-2.0 を明記済み（2026-10-04）
- [x] ~~**v1.0.0 リリース**~~ → **7.0.0 に変更（2026-10-05）**: copier は最大タグを
      採用するため 6.1.0 がある限り v1.0.0 は選ばれない。詳細 TODO.md §39.3。
      ✅ 7.0.0 は 2026-10-05 公開・Latest 済み
- [ ] **Secrets 再設定（2026-10-06 時点で `GITLEAKS_LICENSE` の値のみ残り）**: org 再作成で旧リポの secret が消滅。
      `GITLEAKS_LICENSE` — secret 自体は存在するが action に空で届く。エージェント側の配管（`_hygiene.yml` の `workflow_call` secret 宣言 + env 受け渡し、`ci.yml` 本体・生成物の forward）は PR #19 で修正済み。残りは**保存値が空/不正**の可能性が高く、API では値を確認できない。対処: gitleaks.io で無料 org キーを再取得し `gh secret set GITLEAKS_LICENSE --repo ConstitutiveTemplates/daimonion` で再設定。
      ~~`EXAMPLE_DEPLOY_KEY`~~ — ✅ 2026-10-06 にエージェントが再設定（`daimonion-example` に write 権限の deploy key を登録 + secret 設定。秘密鍵は破棄済み）。push 後の `example / update` 実走で有効性を最終確認する。
      `PYPI_API_TOKEN` — 未設定のまま（PyPI 側の発行が必要）。
      **deploy key 方式で継続決定（2026-10-05）**: org Settings →
      Member privileges で deploy keys を有効化したうえで、
      ConstitutiveTemplates/daimonion-example に deploy key を登録し
      `EXAMPLE_DEPLOY_KEY` secret を再設定
- [x] **`uvx --from git+...` の実ネットワーク検証**: ✅ 2026-10-04。
      `uvx --from git+https://github.com/ConstitutiveTemplates/foundry.git
      foundry new . --preset bare` が clone→cache→render（61 files）まで
      完走（cold cache、実 GitHub 経由）。tag 6.1.0 が最新 questionnaire を
      持たないため ref は main にフォールバック（v1.0.0 タグで解消）
- [ ] **PyPI 公開判断**: `uvx foundry`（git+ URL なし）に
      するかどうか → **daimonion 改名で前提が消滅（`foundry` は PyPI 取得済み）。
      `uvx daimonion` にするかの判断に置き換わる。Phase 2.5 の PyPI 確保を参照。**

## Phase 2.5: `daimonion` への改名（2026-10-05 決定。TODO.md §39）

- [ ] **PyPI `daimonion` 確保**: 0.0.0 プレースホルダを公開（`PYPI_API_TOKEN` 発行が必要）。
      リポ内の改名（§39.1）より先でよい — 名前は早く押さえるほど安全
- [x] **GitHub リポ名変更**: ✅ 2026-10-05 完了。`foundry` → `daimonion`、
      `foundry-example` → `daimonion-example`。PR #11 は同日 merge 済み、
      `uvx --from git+.../daimonion.git daimonion new --preset cli` で実ネットワーク検証済み
      （ref 7.0.0、52 files）。ローカル checkout も `daimonion/` に改名、`uv sync` 再生成済み
- [x] **Pages URL の確認**: ✅ `constitutivetemplates.github.io/daimonion/` に自動追随済み
      （rename 後 building → success 確認）。`daimonion.dev` は NXDOMAIN（未取得）。
      取得するかは人間の判断（`.com`/`.io` は既に取得済みのため優先度低）
- [x] **改名後最初のリリース 7.0.0**: ✅ 2026-10-05 公開済み。タグ `7.0.0`
      （ledger-fix 込みの HEAD 84f2ab44 に再タグ）、GitHub Latest = 7.0.0、
      git-cliff ノート生成済み。test/test-meta/docs/lint 緑、hygiene のみ
      GITLEAKS_LICENSE 未設定で赤（既知の secret 欠落）
- [ ] **（§40 由来）内部メモ用の private リポ/Wiki の用意**: `notes/outreach/`・
      `copier-fork/`・本ファイルの移設先。作成後は移動自体はエージェント可能

## 直近の作業（2026-10-05 時点の残り全部）

**今週（ブロッカー優先）**:

- [ ] **Secrets 3種を再設定**: `GITLEAKS_LICENSE` / ~~`EXAMPLE_DEPLOY_KEY`~~ /
      `PYPI_API_TOKEN`。`GITLEAKS_LICENSE` は保存値自体が空/不正の診断で、
      配管修正は PR #19 で merge 済み（2026-10-06）。再取得した org キーの
      `gh secret set` が残作業。設定後は #2（scheduled check）の次回週次実行で
      緑を確認して close。
- [ ] **PyPI `daimonion` の確保**: 0.0.0 プレースホルダ公開
      （`uv build` + `uv publish`。`PYPI_API_TOKEN` 前提）。`uvx daimonion`
      （git+ URL なし）を実現するかの判断も同時に。
- [x] **PR #9 の扱い決定**: ✅ 2026-10-06 に解決。fork 削除済みで
      merge 不可だったため、内容を共著クレジット付きで #23 として再作成。
      #9 は superseded として close、#5 は #23 の merge で close。
- [ ] **copier upstream への F1-F7 投稿**: fork に実装済み（パッチ 4 本 +
      Discussion 草案 2 本、`notes/upstream-drafts/` + `copier-fork/patches/`）。
      upstream の AI_POLICY により投稿は手動のみ。

**来週以降（Phase 3 発信）**: 下の Phase 3/4 を全部。先に `notes/outreach/` の
草案の最終編集（daimonion 名は反映済み）。

**未判断のもの**:
- `daimonion.dev` ドメイン取得（現在 NXDOMAIN、低優先）
- 内部メモ用 private リポ/Wiki（§40: `notes/outreach/`・`copier-fork/`・本ファイルの移設先）
- 定期リリース周期（§40。現在 PR 経由の運用は開始済み）
- push protection の再有効化（Phase 2 の注意書き参照）— 2026-10-09 レビューで優先度上げ:
  `GITLEAKS_LICENSE` 欠落で gitleaks も赤のため、現在は秘密情報検知が二重に停止中。
  履歴の疑似値を allowlist 化して早期に再有効化（TODO.md §41）
- showcase 用の自プロジェクト選定（Phase 4）

## Phase 3: 対外発信（ローンチ後 2〜4週間）

- [ ] **3大技術記事の執筆・公開**（PLAN §3 ステップ1 に構成案あり）:
  下書き 3 本は `notes/outreach/` に起票済み（DRAFT ヘッダ付き。
  葉数は現行 272 に同期済み。公開・最終編集は人間）:
  - [ ] EN: "Why we used an SMT solver (Z3) to verify 272 question
        combinations" → Show HN + r/Python（PST 火/水 7-8時）
        `notes/outreach/show-hn-z3-verified-template.md`
  - [ ] EN: "Continuous Drift Detection: 5 failure dimensions" →
        r/programming / DevOps 系 `notes/outreach/drift-detection-article.md`
  - [ ] JA: 『272通りを Z3 で形式検証した話』→ Zenn/Qiita
        `notes/outreach/zenn-z3-template.md`
- [ ] **Awesome リスト PR**: `vinta/awesome-python`（Project Scaffolding）、
      `donhui/awesome-uv`、copier Discussions / Astral Discord。
      **訂正（2026-10-05）**: `copier-org/awesome-copier` は存在しない —
      公式経路は topic `copier-template`（設定済み=掲載済み）。
      文面素案は `notes/outreach/awesome-list-entries.md` に起票済み。
- [ ] **ニュースレター推薦**: Python Weekly / PyCoder's Weekly の
      推薦フォーム、Python Bytes へのトピック提案。
      **文面素案は `notes/outreach/newsletter-pitches.md` に起票済み**
      （~50語 / ~30語 / Python Bytes セグメント文の3形態 + 各フォーム URL）。
- [x] **移行ガイド**: ✅ `docs/how-to/migrate-from-hypermodern.md` 新設済み
      （2026-10-04。toolchain 対比表 + fresh/adopt 2 経路 + 実在の gap 列挙。
      zensical.toml nav 登録済み）
- [ ] **`cookiecutter-hypermodern-python` の代替探しスレッドへ案内**:
      敬意を払い中立な形で後継として言及（元作者のスレッドは慎重に）。
      **返信草案は `notes/outreach/hypermodern-thread-reply.md` に起票済み**
      （中立文案 + 投稿前チェックリスト付き）。

## Phase 4: コミュニティ定着（継続）

- [ ] **demo GIF 作成**: `vhs` (Charmbracelet) で15秒 — 生成→`task check`
      通過→`AGENTS.md` 配備。README ヘッダへ埋め込み。
      **tape ファイルは `notes/outreach/demo.tape` に起票済み**
      （vhs 未導入のため生成自体は人間）。
- [ ] **Showcase 開設**: 自分のプロジェクトを本テンプレートで生成し
      「採用例」を README/Docs に掲載。`built with` バッジの配布。
- [x] **`good first issue` シード**: ✅ 5 件起票済み（#4 preset 追加、#5
      プリセット表 docs、#6 `--list-presets`、#7 installation troubleshooting、
      #8 codex セクション草案 — すべて leaf 空間非接触）
- [ ] **Issue/PR 初動体制**: 24h 以内応答、`CONTRIBUTORS.md` 記載で
      リテンション。
- [x] **marimo 統合の判断**: ✅ 実装済み + 本セッションで 3 件のギャップを修正
      （data_science の notebooks/ に marimo seed 追加、`notebook` task が
      必要とする jupyterlab を experiment extra へ、per-file-ignores を
      kaggle 専用から `**/notebook*/**` へ一般化 — 2026-10-04）

## Phase 1 補遺（判断待ち）

- [x] **質問票第1問のプリセット案内**: ✅ 採用（A: help 追記、2026-10-05）。
      `project_type.help` に全 12 プリセット名を列挙する導線を追加 +
      `test_every_preset_is_named_in_project_type_help` でプリセット名↔help
      の一致を機械化（新プリセットで help 未更新なら失敗）。leaf 空間非接触。
