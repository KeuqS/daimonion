# TODO

> アーカイブ: §1–27 は `notes/archive/TODO-sections-01-27.md`(行番号は旧 TODO.md
> と同一)、完了済み §28/§30–34/§38–39/§41–42/§44 は
> `notes/archive/TODO-sections-28-44-done.md`(旧行番号は各節の `<!-- 旧 TODO.md Lx–Ly -->`
> コメントに記録)へ移動した(2026-10-12)。本文・コード・docs の「TODO.md §xx」
> 「TODO §xx」参照は節番号で両アーカイブを指す。現行の残作業は下の索引と残存節
> (§29, §35–37, §40, §43)を正とし、`- [x]` は記録であって現状の主張ではない。

## 設計原則（2026-09 合意・更新: AGENTS.md / online_judge / kaggle 再編を反映）

> 注: §1–27 は `notes/archive/TODO-sections-01-27.md` へ移動済み。現行残作業の正は下の索引と §28 の `- [ ]` とし、`- [x]` は履歴記録であって現状の主張ではない。

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
    - 2026-09-21 更新: AGENTS.md は全判定で常時生成に変更（本 bullet の
      「置く/置かない」は本文の**文言**が変わることを指すようになった）。
      ファイルの有無を軸にしなくなっても、規約の軸は project_type /
      oj_kind / oj_allow_ai に残るため project_type の設計は変わらない。
  - 逆に、実行環境も AI 規約も同じなら project_type を増やさない。
    CTF、botter（discord / slack / LINE / Gmail）、data_science の拡充、SRE、FastHTML 等は
    「既存 project_type の上に載るレイヤー / 亜種」として扱う。増やしたい要求は
    必ず「既存の何の上に載るか」を答えてから設計する。
- **AI コーディングエージェント向けの指示（AGENTS.md）は、デフォルトで全プロジェクトに置く**
  - library / cli / web_api / data_science / script / kaggle には常時生成。
  - 2026-09-21 方針変更: **ros2 / micropython / online_judge にも常時生成**
    （`agents_md_effective` は定数 true）。旧合意「AI 利用 NG の online_judge
    には置かない / ros2・micropython は build がスコープ外」は廃止。
    - online_judge: `oj_allow_ai`（atcoder/leetcode のみ提示）は生成の有無
      ではなく**本文の文言を選ぶフラグ**に転用。Yes は「AI 利用可、ただし
      規約が上位」、No は「提出は手書きで行え」を記載し、共通で「提出前に
      大会の現行規約を確認せよ」を置く。yukicoder/AOJ は質問なしで
      check-the-rules 文言。
    - ros2 / micropython: PKIチェーン ethics セクションのチャネル確保が
      動機（§29.B `baseline-pki-chain` の解消）。
  - 個別の ON/OFF 質問は作らない（内蔵の初期構成とする）。
- **対象外の領域は web_django 方式で明示的に拒否する**
  - このテンプレートの守備範囲外（Ansible の IaC、Terraform/K8s、Django 等）は
    project_type の選択肢として「NOT supported。生成を abort して代替を案内」する。
    黙って無視する選択肢を増やさない。
- **選択肢は「推奨1本 + No でカスタム」を保つ**
  - 現行の `use_recommended_*` 方式。詳細な選択肢（ORM 5種、GraphQL/REST 等）を
    一度に並べるカタログ型（例: s3rius/FastAPI-template）にはしない。

## 残タスク索引（2026-10-12 更新。ここは案内のみ — チェックボックスにしない）

原文の置き場所:

- §1–27 の残り 28 件 → `notes/archive/TODO-sections-01-27.md`(行番号は旧 TODO.md と同一。
  §B 残件の着地状況メモは同ファイル末尾へ移動)
- 完了済み §28/§30–34/§38–39/§41–42/§44 → `notes/archive/TODO-sections-28-44-done.md`
- コード・docs の `TODO.md §xx` / `TODO §xx` 参照は節番号で追える(番号不変)

### A. このファイルに残るもの

- §29 ethics 昇格ロードマップ → このファイル。draft 節は着手条件つき保留
  (region 2件は同梱参照方式で着地済み、appendix 生成化も着地済み)
- §35–37 検討・構想 → このファイル。実行環境配慮(Colab/Lambda)、メンテナンス戦略、
  普及戦略。エージェント実施済み分は各節に記録、残りは人間作業・判断待ち
- §40 レビュー改善点 → このファイル。**開放中の 3 件は全て人間作業**
  (secrets 再設定・private repo 分離・upstream PR 投稿)
- §43 再評価 → このファイル。設計判断の維持基準(閾値条件付き)
- §49 次期改善候補 → このファイル。2026-10-13 レビュー。法務レイヤー不整合
  (legal-check 未実装・law-lint ルール drift・law-map 孤児 checks)、
  law-lint 強化、§36 S5 / §29 region 昇格の着手条件充足など

### B. アーカイブ側の残り(28 件 + 各着地記録。原文は archive)

- 機能の将来拡張(7): OJ 9 種＋その他(§2, archive L117)[§2 本体に記録済み(着地)]/ bot LINE・Gmail 残り(§4, L182)[着地済み]/
  スタンドアロン MCP レシピ(§5, L362)[着地 2026-10-13: `docs/how-to/mcp-distribute.md`]・MCP 本番運用(§5, L363)[人間判断: §49 頭注の web_api Docker 一体設計]/ SQLAdmin・FastCRUD(§6, L440)[人間判断]/
  library 空依存の維持・質問化(§17, L1058)[「維持」決着済み]/ 実行環境への配慮 — Colab / AWS Lambda(§35, このファイル)[人間判断]
- 公開・運用手順(14)[全て人間作業: repo admin/secrets・外部投稿・組織判断]: v1.0 fork 解除(§11, L544)/ renovate digest・example 再生成・
  Scorecard 確認・branch 保護(§12, L615–621)/ 改名・由来明記・Scorecard 初回・告知・
  hypermodern 乗換・Z3 記事・bus-factor(§16, L995–1028)/ fork 作成 F3 着手・手動投稿(§21, L1489–1497)
- CI・検証の残り(8): CI 緑確認・教訓(ネスト)・バッジ乖離・Periodic(§15, L800–815。
  **2026-10-13 確認済み**: run 38342604347 全ジョブ緑(lint/docs/hygiene/test/
  test-meta/Security/Scorecard/example update)。basedpyright が警告のみでも
  exit 1 を返す分岐が判明し、葉分割由来の 151 警告を pragma で沈黙させた)/
  setup composite 化[着地済み・実走確認のみ人間]・未検証組合せ(§19, L1328–1348)[一部着地 2026-10-13: weekly `pixi-render-test` + `poetry-render-test` を scheduled-check.yml に追加(poetry は `[tool.poetry] packages` 明示 + `__init__` の importlib.metadata fallback で修正済み)。windows/macos・release 経路・初回実走確認は人間]/ `render_project` 戻り値・
  手書きテスト棚卸し(§23, L1841–1910)[着地済み]


## 29. ethicsセクションの昇格ロードマップ（2026-09-19 検討）

`_shared/ethics/` の draft → active/kind 昇格の現状と残り論点。機構の説明は
`docs/explanations/template-dev.md` の「Accumulate ethics/regional/operational
rules as sections first」、レジストリは `_shared/ethics/REGISTRY.yml`。

### A. 済（2026-09-18〜19 着地）

- 初回昇格: AGENTS.md ethics 付録に 5 セクション。ゲートは既存派生変数のみ
  （質問追加ゼロ・葉空間不変 228）:
  `license-drift`(全ガイド) / `pqc-fips`(library, cli, web_api) /
  `copyright-ai`(cli, data-science レイアウト) / `llm-appsec`(`mcp_effective`) /
  `ml-bias`(data-science レイアウト, kaggle)。
  検査は invariants.yml の `ethics-appendix` 述語（過剰配布も検知）＋
  リーフクラス行のコンテンツペア。レジストリ逆方向ピン
  （test_distributed_sections_are_included_by_their_parents）追加済み。
- 生成側 typos への固有名詞無視ミラー（`HashiCorp` 等がスペルチェックに
  誤検知されるため。`_shared/pyproject-test-coverage.toml.jinja`）。

### B. 残り draft の扱い（着手条件つきで保留）

- **`baseline-pki-chain`**: **2026-09-21 着地（active 昇格）**。候補 (ii) の
  方針変更を採用 — ros2 / micropython / online_judge にも AGENTS.md を常時
  生成するようになり（上の設計原則 bullet）、AGENTS.md 自身が旧 draft が
  待っていたチャネルになった。gate は `project_type in ['micropython', 'cli']
  or web_api`（registry audience `[iot, cli, web]`。iot→micropython の写像は
  gate と ETHICS_SECTIONS selector の両側に同じ綴りで置き、registry 側は
  人間語のまま）。ros2 は audience 外（own 行の content ペアでネガティブ
  ピン）。検査は ethics-appendix 述語 + invariants.yml の micropython/cli/
  web_api 行の `PKIチェーン` コンテンツペア + レジストリ親ピン。
- **`sector-samd-regulatory`**: **2026-09-20 着地（active 昇格済み）**。
  domain_traits の `medtech` 選択がゲート（ETHICS_SECTIONS の
  samd-regulatory 行）。ここには記録として残す。
- **`region-jp-external-transmission` / `region-eu-eaa`**: 保留継続
  （**2026-10-13 再判断**: §49.C で再検討済み。3 件目 `region-eu-cra` は
  既存回答 `distribution` で active 昇格したため「市場ゲート節の同梱経路」
  の前提が成立せず、本 2 節は regions.yml 同梱経路で唯一の適用対象
  （web_api）に葉 +0 で届いている。昇格には `target_markets` 質問＝葉次元増
  が必要で対価不整合 → 保留継続。再トリガー: regions.yml を共有する 3 件目の
  市場ゲート節、または市場型質問の独立正当化）。
  - 元案: 展開地域を知る質問（`target_markets`: any-of jp/eu/us…）を新設。
    ただし新質問は葉次元を増やす（witness 再記録が必須）。
  - 2026-09-21 の次候補（質問化しないチャネル）: **各国ルールの参照ファイル
    を生成物に同梱し、AGENTS.md から随時参照させる**方式。lang/ 辞書
    （copyright-terms.yml と同型の構造化データ）をレンダしてプロジェクトに
    置き、ガイドは「対象地域の節を読め」と案内するだけ。質問追加ゼロで
    葉空間は動かない。3 件目の地域セクション（米国州法系など）が集まったら
    この方式で昇格を再検討する。`region-kyushu-ntp` は地域ではなく
    audience ゲート型なのでこのバンドルには載らない。
- **`baseline-copyright-ai` の法域拡張**: **2026-09-21 着地**。保護期間の
  法域差を `_shared/ethics/lang/copyright-terms.yml`（8 法域・戦時加算を
  データ化・1次出典付き・review_by を registry 行と同期）に構造化。
  ガードは test_ethics_registry.py の copyright-terms テスト、セクション
  本文からテーブルへ逆参照し drift を防ぐ。

- **`_shared/ethics-appendix.jinja` の生成化**: **2026-10-01 着地**。include
  チェーンは `tools/gen_ethics_appendix.py` が `REGISTRY.yml` の `status` +
  `gate` から生成するコミット済み生成物になり、AGENTS.md.jinja は
  `{% include "_shared/ethics-appendix.jinja" %}` 一行だけを持つ。
  `gate` が「どの葉が節を持つか」の唯一の綴り — テスト側の述語は
  `tools/ethics.py` の制限 eval で同じ文字列を評価する（λ 表と
  `test_generated_lint.py` の private OJ_CODE_KINDS は解消）。
  `invariants.yml` の per-row コンテンツペア（ライセンス変動等 23 件）も
  除去 — 述語が同じ主張をするので重複していた。`FLAGS.yml` の `gate:` 列も
  registry への重複スペルだったため除去（外部契約は `audience` 写像のみ）。
  新規テスト: 生成物の鮮度チェック + 全 gate の安全/束縛チェック
  （test_ethics_registry.py）。バッチ仕様に `expect.agents_md` を追加し、
  smoke.jsonl の 7 リクエストがレジストリ id で節の有無をピンする。
- **地域ルールの同梱参照**: **2026-09-28 着地（上の「次候補」の実施）**。
  `ethics/regions.yml`（web_api のみ生成）が per-market 要約 + 1次出典表を
  同梱し、AGENTS.md は表へのポインタを持つ。`serves:` が draft 節への唯一
  許される参照（テストでピン）。2 節は draft のまま — 質問追加なしで
  葉空間不変のまま読者に届く。

### C. enforcement の引き上げ候補（L0 → L1/L2）

- **基盤強化（2026-09-21、複数人でのセクション執筆に備えて）**:
  - **review_by 期限ピン**: 期限切れの `review_by` は
    `test_ethics_registry.py::test_no_review_date_has_passed` が fast tier
    で毎回検査し、CI を赤くして再調査を促す（それまでは誰も表面化しなかった）。
  - **権限分割の明文化**: GOVERNANCE.md に「既定規約・昇格判断はメンテナ、
    draft 執筆・一次ソース調査・review_by 再確認は寄稿者」の節を新設。
  - **runbook**: `docs/how-to/ethics-section.md`（draft 追加→昇格チェックリスト→
    enforcement→lang/ 辞書→メンテナンス）。extending.md が質問票拡張の
    runbook であるのに対し、倫理セクション側の道筋はこれが初。

- **L1（存在assert）**: **機械消費者は 2026-09-19 着地**。セクションの
  「設定側トリガー」正規表現は tools/ethics.py が全行パースし、MCP の
  `check_ethics` ツール（テキストを食わせるとヒットした節を enforcement 順で
  返す。draft も警告付きで提示）と `template://ethics` リソースとして公開。
  契約は test_ethics_registry.py（全行パース可能・大文字小文字非依存・
  一意）と test_mcp_server.py がピン。レンダ側の存在assert は従来通り
  invariants.yml の `ethics-appendix` 述語が担う（active 5 セクション）。
  draft セクションのトリガーは昇格まで警告専用。
- **L2（実ゲート）**: **着地（2026-09-19）**。`license-drift` の copyleft ゲートが
  生成プロジェクトに同梱された — `license-check` タスク
  （`pip-licenses --from=mixed --partial-match --fail-on=<導出ポリシー>`。
  permissive→GPL系、GPL/LGPL→AGPL。AGPL-3.0 は fail-on なし）。
  質問は security ゲート配下の `license_check`、内部は
  `license_check_effective`、dev 依存 `pip-licenses>=5,<6`（rec + effective 時）、
  CI は ci.yml の lint ジョブが type-check と並行で呼ぶ。
  ネットワーク依存のため `type-check`/`check` には入れていない（offline 契約）。
  レジストリ側も同期済み: `baseline-license-drift` を enforcement L2 に
  引き上げ（version 2026-09-19.1）、セクション本文が同梱タスクを参照。

### D. ウォッチ（確度つき。各セクションの制度変更ウォッチと review_by が一次）

- OWASP 次版（2026・インシデントデータ基準への転換）: 確度 未確認。
  review_by 2026-12-18。公表されたら `llm-appsec` の番号参照（名称参照に
  統一済み）と marks を更新。
- Let's Encrypt チェーン / ISRG ルート儀式: review_by 2026-12-18。
- FIPS 206 (FN-DSA) 草案 / IR 8547 final: review_by 2027-03-31。

## §35 検討: 実行環境への配慮 — Colab / AWS Lambda（2026-10-02 提案）

生成物の検証はローカル + GitHub Actions 中心だが、実際の実行環境には
Colaboratory / AWS Lambda 等がある。スライスごとの衝突を棚卸しする。

- **第一ステップ（2026-10-02 実施）**: 各 1 回実レンダで確認し、記述を修正。
  - data_science: `notebooks/` は `.gitkeep` のみ、requirements.txt 無し —
    Colab(pip)に install 経路が無いことを確認。→ repo docs の
    `docs/how-to/data-science.md` に Colab 節を追記
    （`%pip install -e .`、GPU は CUDA wheel を先に入れる旨）。
  - web_api + `cloud_provider: aws`: boto3 は入るが Lambda ハンドラ・
    関数設定・デプロイ定義が無いことを確認。→ `docs/how-to/web-api.md` の
    "Things deliberately left out" に serverless を追記
    （ASGI は Lambda 関数ハンドラと別世界、Mangum 等の adapter を
    「必要になったら」明示的に足す、と明記）。
  - 現時点の判断は **docs-only**。`deploy_target` 質問による Lambda 向け
    生成（Mangum 統合・SAM/CDK）は leaf 空間を広げるため見送り。
    生成物の docs/how-to は data-science / web-api の how-to を同梱しない
    （run-container / contribute のみ）ので、この記述は repo docs 層で完結。
- **web_api / AWS Lambda**: `cloud_provider: aws` は現状 AWS サービス依存を
  足すだけ（boto3 等; questions/_common_b.yml）でデプロイ形態は定めない。
  Lambda で動かす場合 — メモリ/タイムアウト（生成 workflow の timeout は
  あるが関数自体の設定は無い）、`Dockerfile` の起動方式（uvicorn サーバーは
  Lambda の関数ハンドラと別世界）、env 管理（`.env.example` は local 前提）。
- **判定基準**: 各スライスの「検証環境」と「実際の実行環境」のズレを
  ドキュメントで明示するだけに留めるか、質問（`deploy_target` 等）を足して
  Lambda 向けハンドラ/project 設定を生成するか、を設計監査として判断。
  Leaf 空間を広げるなら witness 再生成（272 葉基準）が必要。
  **判断（2026-10-13 確定）: docs-only を維持、`deploy_target` 質問は
  設けない。** 根拠: (a) 設計原則「実行環境が同じで AI 規約も同じなら
  project_type/質問を増やさない」— Lambda はデプロイ形態差であって別の
  実行環境・規約の第一級軸ではない（同じ ASGI プロセスモデルの
  adapter 問題）。(b) `deploy_target` 追加は葉次元 +1 = witness 全再記録
  で、得られるのは Mangum 等 adapter ファイル 1 枚の生成のみ —
  対価が合わない。(c) 実需要が観測されていない（本 TODO 自身が
  「利用者価値をまだ測れていない前提」と分類）。再検討トリガー:
  generated web_api を Lambda で運用した実例報告が 2 件以上集まるか、
  serverless が「規約の軸」（例: AWS 固有のコンプライアンス要件）として
  顕在化した場合。
- 着手はこのTODOの番号（§35）を参照。まず `data_science` の notebook が
  Colab で開けるか（依存インストール経路）と、`web_api` cloud_provider=aws
  の Lambda 適合を各1回実レンダで確認するのが最初のステップ。

## §36 検討: メンテナンス性とコントリビューター増のための設計戦略（2026-10-02）

診断: 資産は検証の深さ（272葉 witness・コスト台帳・不変条件・twin レンダ・
render cache）。負債は「検証の支払いコスト」— 質問票変更の定義完了に
`task witness` → `task predicates` → `task question-graph` → `UPDATE_TIERS`
（台帳）→ `gen_docs.py --write` → zensical docs の **6 コマンド**が別々に必要。
CONTRIBUTING.md は 45 行で装置が載らない。フォーク関係がハイブリッド（大幅
乖離 + upstream 追跡の並存）。2026-10-02 の CI 失敗カスケードは docs-only
判定が lint / hygiene まで skip し、format・type-check 債が複数コミット分
蓄積して一斉露出したのが直接原因。

戦略（優先度順）:

- **S1 検証生成の一元化（`task regen`）**: witness / ledger / docs /
  question-graph を依存順に回す 1 コマンド。CI の meta tier は既に drift を
  検出するので装置は変えず、definition of done を暗黙知から 1 コマンドへ。
  最大 ROI。
- **S2 blast-radius 分類 + 貢献レダー**: 変更を docs-only（検証不要）/
  render-only（twin レンダ + fast tier）/ questionnaire（`task regen`）に
  分ける決定表を CONTRIBUTING に置く。`good first issue` ラベル + leaf 空間に
  触れない種（ethics 節追加・task 追加・docs）を 5–8 件シード。
- **S3 フォーク・アイデンティティ確定**: (a) upstream thin overlay か
  (b) 完全独立か。乖離は既に深く (b) が現実的 — 文書で確定し、COPIER_UPSTREAM
  を定期レビュー用に再定義 or アーカイブ。6.2.0 タグ切れの判断もここに含む。
- **S4 オンボーディング面**: 1 PR を端まで追う「Contributing 101」
  （例: ethics 節を 1 つ足す → regen 1 コマンド → CI 緑）を追加。装置の詳細は
  template-dev.md（reference）に据え置き。
- **S5 結合アーティファクトの導出化**: invariants / layers の手書き行を
  質問票から生成（witness / ledger / docs は生成化済み。残る手動結合はここ）。
  大きなリファクタなので S1–S4 の後に。
- **機制の穴の修正（推奨着手）**: docs-only 判定でも lint / hygiene は常時
  実行に狭める（~20s の追加で、CI 失敗カスケードの再発防止）。
- 推奨着手順: S1 + lint/hygiene の docs-only skip 縮小 → S2 レダー + good
  first issue。

## §37 構想: このOSSが広く普及・愛用されるための包括的拡大戦略（2026-10-04）

### 37.0 診断: 驚異的な技術的完成度と、普及におけるギャップ
本テンプレートは「Z3ソルバによる質問空間（272葉）の数理的充足性証明」「5次元×4タイミングのMECEドリフト検知」「AIコーディングエージェント（AGENTS.md）および法務・倫理レジストリの動的コンパイル」「OpenSSF Scorecard / 全Action SHA固定の徹底的サプライチェーン保護」など、Pythonテンプレート界において世界屈指の技術的深度を持つ。
しかし、外部への普及・利用拡大においては以下の「5つの壁」が存在し、利用者の獲得を妨げている:

1. **フォーク属性とブランドの壁**: GitHub 上で `DiamondLightSource/python-copier-template` のフォークとして表示され、星が分散し、一般名称（`python-copier-template`）のままのため固有の存在として認知・言及されにくい。
2. **導入・試用の摩擦の壁**: README の先頭が「リポジトリを `git clone` して CLI 実行」となっており、プロジェクトを作りたいだけの初見ユーザーにとって心理的敷居が高い。また高度な専門用語（SMT、272葉、EU CRA）が全面に出過ぎており、ライト層が「大げさすぎる」と敬遠する認知的過負荷がある。
3. **対外発信・エバンジェリズムの壁**: 他に類を見ない技術的差別化点（Z3数理検証、ドリフト検知、AGENTS.md）がリポジトリ内のドキュメントに留まり、Hacker News、Reddit、Zenn、Qiita、カンファレンス等の外部コミュニティへ届いていない。
4. **既存リポジトリへの導入（Adopt）の埋没**: 最大のキラー機能である「既存プロジェクトを壊さずに近代化する（`adopt.py`）」がローカルスクリプト扱いになっており、世界中の既存リポジトリへ届くワンライナーになっていない。
5. **ソーシャルプルーフとコミュニティの壁**: 「誰が本番で使っているか」のShowcaseがなく、コントリビューションの敷居の高さ（§36で指摘）により Bus Factor = 1 の状態が続いている。

---

### 37.1 普及のための6大戦略（Pillars）

#### P1. アイデンティティ確立とリブランディング（Brand & Identity）
- **フォーク解除・独立リポジトリ化**: §11/§16 の合意を実行。`git checkout --orphan` による新履歴での独立公開、または GitHub Support を通じた detach。DiamondLightSource および祖先への謝辞・クレジットは NOTICE / README / docs に明確に刻む。
- **固有のプロジェクト名・呼称の策定**: 会話やSNSで指名しやすく、検索性の高い名前（例: `copier-python-hypermodern` / `agentic-python` / `proven-python` 等の軸から決定）。
- **2026年の最前線ポジショニング**:
  - 「**AIコーディングエージェント共創時代の、数理検証された高信頼Pythonテンプレート**」
  - 開発停止した `cookiecutter-hypermodern-python`（1900+ stars）の正統後継・移行先としての旗幟。
  - `copier-uv`（ライブラリ特化）との住み分け: 「単機能ライブラリなら copier-uv。実務全般（Web API / Data Science / CLI / 競プロ / 組込）× AIエージェント × 堅牢性なら本テンプレート」。

#### P2. 導入体験（UX）の極小摩擦化（Zero-Friction Onboarding）
- **ゼロインストール・ワンライナーの前面化**:
  - `git clone` 前提の手順を即時廃止。README 先頭を `uvx copier copy --trust gh:<org>/<repo> my-project` に刷新。
  - CLI（`foundry`）の PyPI 公開または `uvx` 配布対応（パッケージ構成を整理し、clone なしで `uvx <name> new my-project --preset library` を可能に）。
- **プリセット主導の「3秒スタート」体験**:
  - 質問票の第1問目で「推奨プリセットから選ぶ（Web API / CLI / Data Science / Library / Minimal Bare）」を案内し、1回のリターンキーで即座に走る体験を提供。
- **既存プロジェクト近代化ツール（Adopt）のワンライナー化**:
  - `uvx <name> adopt .` を提供。「すでにあるリポジトリに Ruff、basedpyright、GitHub Actions CI、AGENTS.md を安全に追加する」ユースケースを開放（アドレス可能市場が新規作成の10倍に拡大）。
- **視覚的証明（Visual Proof）**:
  - 15秒のターミナルGIF（vhs）: プロジェクト生成から `task check` が爆速でパスし、`AGENTS.md` が配備される様子。
  - GitHub "Use this template" ボタン用のクリーンなテンプレートリポジトリ（exampleプロジェクト）の整備。

#### P3. 技術的特異性の対外発信・エバンジェリズム（Technical Content & Buzz）
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

#### P4. 2026年キラーユースケースの研磨（Use-Case Excellence）
- **AI / LLM / Agent 開発者向けスタックの強化**:
  - プリセットに `preset: mcp-server`（MCPサーバー開発特化）を新設・前面化（AIツール作者層の獲得）。
  - すでに持つ bot platform（Slack/Discord/LINE/Gmail）や web scraping との組み合わせを「AIエージェントの道具箱」として位置づけ。
- **モダン・データサイエンス環境の強化**:
  - §35 で Colab 対応を確認済み。2026年標準の `marimo`（モダン・リアクティブ・gitフレンドリーなノートブック）対応や Quarto 連携の強化。
  - Poetry や Conda の重さに疲弊したデータサイエンティスト層に uv 爆速環境を提供。
- **Web API の実用性向上**:
  - FastAPI + Docker + Pydantic v2 + Sentry + OpenTelemetry/Prometheus。

#### P5. コミュニティ基盤とコントリビューター育成（Community & Lowering Barriers）
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

#### P6. 信頼と品質のエンタープライズ級アピール（Trust & Enterprise Reliability）
- **アップデート検証（Rehearsal）の可視化**:
  - テンプレート利用者の最大の恐怖「将来テンプレートを更新したときに自分のプロジェクトが壊れるのではないか？」。
  - 「全272葉でタグ間アップデートが機械的にリハーサルされている」事実を明示し、安心感を提供。
- **OpenSSF Scorecard 高得点の前面化**:
  - SHA固定、zizmor、最小権限トークンによる強固なサプライチェーンセキュリティ。企業の基幹システムでも採用できる品質。

---

### 37.2 ロードマップ・実行順序（提案）

1. **フェーズ 1: 摩擦の撤廃（即効性・1〜2日）**
   - README の導入手順を `uvx copier copy --trust ...` に全面刷新（clone 手順を後退）。
   - §36 の S1（`task regen`）と lint/hygiene の docs-only skip 縮小を実装。
   - ターミナル GIF（15秒）を README 先頭に配置。
2. **フェーズ 2: 独立とリブランディング（1週間）**
   - リポジトリの detach / 独立公開、固有名称・新リポジトリの確定。
   - v1.0.0 タグの打ち直し、Scorecard 初回計測、Branch Protection 設定。
   - `foundry` CLI パッケージの整理（PyPI または `uvx` 配布）。
3. **フェーズ 3: 対外発信と認知拡大（ローンチ後 2〜4週間）**
   - 3大技術ブログ（Z3検証、ドリフト検知、AGENTS.md）の同時公開（Hacker News / Reddit / Zenn）。
   - `awesome-python` / `awesome-copier` への PR 提出。
   - `cookiecutter-hypermodern-python` ユーザー向けの移行ドキュメント公開。
4. **フェーズ 4: エコシステムとコミュニティ育成（継続）**
   - `good first issue` のシード、Showcase ページの開設。
   - `preset: mcp-server`、Marimo データサイエンス連携等の2026年キラー機能拡充。

### 37.3 具体実装方針（Implementation Specifications）

#### 1. ゼロクローン・ワンライナー化（P2）の実装方針
- **README.md の構成刷新**:
  - `TL;DR` を冒頭に配置し、最優先の生成コマンドを `uvx copier copy --trust gh:<org>/<repo> my-project` とする。
  - `--preset` の利用方法を Copier の `--data-file` URL 経由、または `answers` 注入で案内。
  - 旧来の `git clone` 手順は「開発者向け・オフライン環境向け」として後方へ移設。
  - `vhs` (Charmbracelet) を用いた 15 秒のターミナルデモ GIF（`demo.gif`）を生成し、README ヘッダに埋め込み。
- **CLI のスタンドアロン・リモート対応**:
  - 現状 `tools/cli.py` は `TOP = Path(__file__).resolve().parent.parent` でローカルリポジトリを前提としている。
  - 改善: `cli.py` において、ローカルに `copier.yml` が見つからない場合は自動的に最新リリースタグのリモート git URL（`https://github.com/<org>/<repo>.git`）をテンプレートソースとして Copier に渡すフォールバックロジックを実装。
  - `pyproject.toml` に `dependencies = ["copier>=9,<10", "pyyaml>=6.0,<7"]` を最小限のランタイム依存として定義（現状は `dev` のみに存在）。
  - これにより `uvx --from git+https://github.com/<org>/<repo>.git <cli-name> new my-project --preset library` や PyPI 配布時の即時実行が実現。
- **Adopt のリモート・ワンライナー対応**:
  - 既存プロジェクトのディレクトリ内で `uvx <cli-name> adopt .` を実行した際、リモートテンプレートを一時クローン/キャッシュして衝突検知・トランザクション適用・ロールバックを実行可能にする。

#### 2. メンテナンス基盤（§36 S1/S2/S4）の実装方針
- **`task regen` を `Taskfile.yml` に新設**:
  - コマンド連鎖:
    1. `uv run --locked python tools/z3_witnesses.py --jsonl tests/matrix/witnesses.jsonl` (witness 272葉生成)
    2. `uv run --locked python tools/batch.py tests/matrix/witnesses.jsonl --jobs {{ .JOBS | default numCPU }} --quiet` (判定)
    3. `UPDATE_TIERS=1 uv run --locked pytest -q -m meta` (コスト台帳更新)
    4. `uv run --locked python tools/gen_ethics_appendix.py` (ethics-appendix 生成)
    5. `uv run --locked python tools/gen_docs.py --write` (docs 自動生成ブロック更新)
    6. `uv run --locked python tools/predicates.py --json > /dev/null` (述語分類の整合性確認)
  - 依存順に一括実行し、作業者が1コマンドで Definition of Done を達成できる。
- **CI docs-only 判定の狭隘化**:
  - `.github/workflows/_hygiene.yml` / `ci.yml` において、変更がドキュメントのみの場合でも `lint`（ruff / typos / basedpyright）は常時実行し、コミット間の債務蓄積を遮断（~20秒の最小コスト）。
- **`CONTRIBUTING.md` への「変更の blast-radius 表」と「Contributing 101」追記**:
  - 変更対象（docsのみ / テンプレートpayloadのみ / 質問票本体）ごとの必要な検証ステップを明文化。

#### 3. 独立リポジトリ化とアイデンティティ確立（P1）の実装方針
- **リポジトリ移行手順**:
  - リポジトリ新設（例: `github.com/<org>/<new-name>`）。
  - `git checkout --orphan main-standalone` によるクリーンな履歴での独立、または GitHub Support への detach 依頼（過去 Issue 履歴を維持したい場合）。
  - `NOTICE` ファイルを新設し、DiamondLightSource / python3-pip-skeleton / copier-template の系譜と Apache-2.0 ライセンスを明記。
  - リポジトリメタデータ（`pyproject.toml`, `CITATION.cff`, `codemeta.json`, `README.md`）のプロジェクト名と URL を統一。
  - GitHub Secrets（`EXAMPLE_DEPLOY_KEY`, `PYPI_API_TOKEN`）、Pages、Branch Protection rulesets（署名コミット・リニア履歴・CI必須チェック）の再設定。

#### 4. キラー機能・プリセット（P4）の実装方針
- **`presets/mcp-server.yml` の新設**:
  - `project_type: cli`, `include_mcp: true`, `mcp_transport: stdio`, `use_recommended_security: true` 等の構成。
  - `tests/test_presets.py` に `test_preset_renders[mcp-server]` を追加し、sentinel ファイルをアサート。
- **`marimo` ノートブックの統合**: → **既存レイヤー + ギャップ 3 件を修正済み
  （2026-10-04）**。`data_science` の `experiment` extra に marimo 同梱済み
  だったが、(1) `notebooks/` に seed が無かった → `notebooks/explore.py` を
  追加（kaggle の `src/notebook/explore.py` に倣い data/raw 起点の
  polars 探索）、(2) `notebook` task の `jupyter lab` に必要な `jupyterlab`
  が experiment extra に無かった → `EXPERIMENT_PAIRS` と deptry DEP002
  許可リストに追加、(3) per-file-ignores が kaggle の
  `src/notebook/explore.py` 一点張りだった → `_shared/pyproject-analysis-lint`
  （旧 kaggle-lint）に一般化し `**/notebook{,s}/**` に適用。

---

### 37.4 対外アピール・エバンジェリズムの実践プロセス（Outreach & Evangelism Process）

#### ステップ 1: リブランディング＆v1.0.0 ローンチ時の告知プロセス（Day 1）
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

#### ステップ 2: エコシステム・リスト・ポッドキャストへの掲載申請プロセス（Day 2〜14）
1. **GitHub オーガニック掲載（Awesome リスト等）**:
   - **`vinta/awesome-python`**: `Project Templates` カテゴリへの PR。既存の cookiecutter や copier-uv と並び、「SMT-verified multi-domain template」として追加。
   - **`copier-org/awesome-copier`**: 公式の Copier テンプレート一覧への PR。
   - **`astral-sh/uv` コミュニティ**: uv の Discussions（Show & Tell）や Discord の `#showcase` チャンネルでの紹介。
2. **Python 系ニュースレター・ポッドキャストへの推薦送信**:
   - **Python Weekly / PyCoder's Weekly**: 記事 URL（Z3記事やドリフト検知記事）の推薦フォームから送信。
   - **Python Bytes Podcast**: Michael Kennedy / Brian Okken へのトピック提案（「Copier template with Z3 verification and AGENTS.md」は彼らの好むユニークな切り口）。

#### ステップ 3: 難民層・移行層へのピンポイント訴求プロセス（Week 2〜4）
1. **`cookiecutter-hypermodern-python` 難民の救済**:
   - `docs/how-to/migrate-from-hypermodern.md` を作成。
   - Poetry → uv、Flake8/Black → Ruff、mypy → basedpyright、Cookiecutter → Copier（更新可能）への対比表を明示。
   - Claudio Jolowicz 氏の元リポジトリの Issue / Discussions（代替を探しているスレッド）において、中立的かつ敬意を払った形で「2026年版の後継アプローチ」として言及・案内。
2. **AIコーディングエージェント開発者へのアプローチ**:
   - Cursor / Claude Code / Cline / Roo Code / omp のコミュニティや X (Twitter) で、「AIエージェントにプロジェクトを作らせる・自走させる際のベストプラクティス基盤」として `AGENTS.md` と ethics レジストリの仕組みを解説。
   - 「AIが勝手にライセンス違反の依存を入れたり、暗号化の古い規約を入れないようにリポジトリで強制する」という実務的価値を強調。

#### ステップ 4: 成果の定着・フィードバックループ（Week 4 以降）
1. **Showcase（採用実績）の構築**:
   - 自分のプロジェクト（MCPサーバー、CLIツール、競プロリポジトリ）を本テンプレートで生成し、`README.md` に「採用例」として掲載。
   - 外部ユーザーのリポジトリに「Adopt」を提案する PR（またはサンプルリポジトリ）を作成し、感謝とともに Showcase への掲載許可を得る。
   - `[![Built with foundry](https://img.shields.io/badge/built%20with-foundry-blue)](https://github.com/ConstitutiveTemplates/foundry)]` バッジの配布。
2. **初動の Issue / PR 体制と contributor ladder**:
   - 新規スターやフォーク、Issue が立った際は 24時間以内に丁寧に応答。
   - `good first issue`（倫理ドラフトの追加、タイポ修正、ドキュメント改善）に最初の貢献があった場合、即座にレビューして merge し、`CONTRIBUTORS.md` に記載してリテンションを高める。

## §40 検討: 「多くの人にメンテされる基本ツール」への改善点（2026-10-05 レビュー）

§37 / `notes/PLAN-widespread-adoption.md` と重複しない指摘のみ。優先順。

- [x] **main CI を緑に戻す** → **緑化確認（2026-10-13、run 38385087549）**:
  全 required checks green（lint/hygiene/docs/test/test-meta/example update）。
  過程で発見・修正した 3 件: (a) legal-check 8 テスト分の台帳 drift
  （tiers.json + test-loop.md 再記録）→ test-meta 赤 → 解消、(b) 自分の
  コミット文 `docs(todo+how-to)` の scope 記法が conventional 違反
  （`+` 不可）→ メッセージ分割。(c) gen_docs の tier-ledger 表 drift
  （verification.md `--write`）。なお旧 HUMAN_TODO の `PYPI_API_TOKEN`
  のみは引き続き未設定 — ただし `_pypi.yml` は OIDC trusted publishing
  方式のため、PyPI 側で pending-publisher 登録 + `release` environment
  作成が済めば token なしで tag push 公開が可能。token が要るのは
  手動/初回 bootstrap 経路のみで、PyPI アカウントを持つ人間が
  pypi.org で発行する必要がある
- [x] **初の外部 PR #9（AK-Lmn）の扱い**: ✅ 2026-10-06 に解決。fork 削除済みで
      merge 不可だったため内容を共著クレジット付きで #23 として再作成し merge、
      #9 は superseded として close、issue #5 も close 済み。
- [x] **設計原則とロードマップを英語化し GitHub 上へ** → `docs/explanations/design-principles.md` 新設 + GOVERNANCE の参照を差し替え(2026-10-05)。残作業の Issues/Milestones 移行は人間: GOVERNANCE.md の
      メンテナ条件が日本語の TODO.md「設計原則」を参照しており、海外の人が
      メンテナになる経路が実質閉じている。設計原則 →
      `docs/explanations/design-principles.md`（英語）、残作業 → Issues /
      Milestones / Projects、TODO.md は履歴アーカイブへ
- [x] **レイヤー単位のオーナー制**: CODEOWNERS 層分割 + GOVERNANCE にオーナー不在→experimental 降格規則と昇格パスを追記(2026-10-05): CODEOWNERS をレイヤー（ros2 / micropython /
      online_judge / bot / ctf / ethics …）単位に分け `docs/reference/support.md`
      のティアと連動。**オーナー不在のレイヤーは `experimental` に降格**する
      規則と、triager → レイヤーオーナー → コアメンテナの昇格パスを GOVERNANCE に明記
- [x] **内部メモを公開リポから分離** → **着地（2026-10-13）**: private リポ
      `kasi-x/daimonion-internal` を新設し、`notes/outreach/`・`copier-fork/`・
      `notes/upstream-drafts/`・`notes/COPIER_UPSTREAM.md`・`HUMAN_TODO.md` を
      移設（ポインタは `notes/INTERNAL.md`）。`periodic.yml` の `patch-rot`
      job はローカル patch ファイルではなく公開 fork `kasi-x/copier` の
      4 ブランチ diff を pin タグ v9.18.1 へ適用検査する方式に切替
      （4/4 が現在も apply 可をローカル検証済み）
- [x] **変更速度を追える速さに**（PR 経由の習慣は 2026-10-05 から実施中 — 本日の変更は
      すべて PR #9-17 として経由）: 残る人間判断は定期リリースの周期（例: 月 1）と
      リリース前の凍結期間の設定
- [x] **CLI を製品の中心に**: `docs/tutorials/installation.md` に new/adopt/update を semver 保証の公開インターフェースと明記(2026-10-05): `daimonion new / adopt / update` を semver で守る
      公開インターフェースと宣言し、内部の質問票は自由に変えられるようにする
- [x] **update 成功率を公開指標に**: `update-rehearsal` の結果を docs 上の（2026-10-05 実装: --json → step summary + artifact + `auto/update-rehearsal` 自動PR、`support.md` に generated rehearsal 節 + README バッジ）
      ダッシュボードとして出す（例: 「全 272 葉でタグ間 update 成功率 100%」）。
      Z3 の技術記事より利用者に効く信頼の証拠
- [x] **ethics 層を独立コミュニティとして育てる**: §38 の分離をさらに進め、
      法規制コンテンツの正誤責任と更新負担をテンプレート本体から切り離す。
      ✅ 2026-10-06 に実施（PR #22 + codex/law-map 側の README / CONTRIBUTING 更新）。
      codex を記事の Source of Truth、law-map を法務 RFC の窓口とし、daimonion は
      「wiring（どのプロジェクトにどう配るか）」のみに専念する形をドキュメント化。
- [ ] **copier upstream への貢献を信頼獲得の経路に**(パッチ 4 本 + discussion 草案 2 本は push 済み。PR/Discussion の投稿は upstream AI_POLICY により人間作業): F1–F7 パッチの upstream 化。
  **現状（2026-10-13）**: 投稿は引き続き人間のみ（copier AI_POLICY は
  「Autonomous agents must not be used to create or submit contributions」
  と明言し、PR 本文は人の言葉が必須）。技術的準備は全て完了:
  4 ブランチ（`f3-missing-batch`/`f5-stale-tag-warning`/`f6-trust-discoverability`/
  `f7-pretend-summary`）は `kasi-x/copier` に pushed、草稿 14 件は
  `kasi-x/daimonion-internal/notes/upstream-drafts/` へ移設済み、
  patch-rot job は 4/4 の v9.18.1 適用を週次検証中。残作業は人間の文章
  による投稿とレビュー対応のみ

## §43 再評価: 現行設計の妥当性と見直し条件（2026-10-11）

§28–42 と現行実装を照合した結果、主要原則を一括で覆す根拠はない。一方、
「設計文書と実動作がずれている箇所」と「利用者価値をまだ測れていない前提」は
再検討に値する。変更はまず小さな観測・文書修正で判断し、実績なしに大規模改築しない。

### 優先して判断する

- [x] **対象外構成の拒否方法を実契約に合わせる**: ✅ 2026-10-11。
  `docs/explanations/design-principles.md` を実装の fail-closed 動作に
  書き直し（非対応要求は選択肢として宣伝せず、preset/CLI の不正値は
  生成前に拒否して代替を案内。旧 web_django トラップ選択肢の撤去を
  明記、再導入条件も記録）。実装（8 型 + `test_django_is_not_a_project_type`
  の拒否）は変更なし。

- [x] **全プロジェクトへの `AGENTS.md` 常時生成を利用者価値で再評価**:
  ✅ 2026-10-11 評価実施。主要型（library=license-drift+pqc-fips /
  online_judge=contest-integrity / micropython=PKI 節）を実レンダで確認し、
  ethics appendix に AGENTS.md 以外の配布経路が無いことを確定
  → **(a) 常時生成を維持**。分離 (b) / 条件再導入 (c) は「agent 未利用
  リポジトリでノイズ」という実害報告が集まるまで open に残し、その旨を
  design-principles.md の該当節に記録。ユーザー報告の収集は人間作業
  （運用中のフィードバック）として残る — 現時点で一律 OFF はしない
  原則どおり。

### 閾値が来たら判断する（現時点では維持）

- **全葉 fast 検証と 30 秒予算**: 全 witness の render/lint は構成空間を機械的に
  閉じる中核。`tests/matrix/tiers.json` の最終測定は 18.6 秒（2026-09-20）で予算内。
  サンプリングへ移るのは検出保証を落とすため、先回りでは採用しない。将来 `test-fast`
  が予算を継続超過したら、(1) §41 の利用実績ベースで best_effort の組合せを絞る、
  (2) 直交する不変条件の合成で重複 render を減らす、(3) 全葉の Z3 充足性と実出力検査を
  別 tier に分ける、の順で再評価する。サンプル化は「全葉出力を CI で毎回検証する」
  主張を撤回する判断と一緒に行い、ランダムな CI 分割で全数保証があるように見せない。

### 維持する判断（反証が出るまで）

- **「推奨 1 本 + No でカスタム」**: 選択肢カタログの増殖を避けながら詳細回答を
  残している。ユーザーが推奨構成から必要な変更へ到達できない実例が出るまでは維持する。
- **既存 project_type へのレイヤー合成**: 実行環境・規約の違いを `project_type` に、
  追加機能を既存型上の layer に分ける原則は、質問票の軸と `layers.yml` の可用性宣言を
  保ち、型の二重化を防ぐ。新しい型が必要な根拠（別 build/run 環境または別の規約軸）が
  ない限り維持する。
- **広い回答空間を支える Z3 / witness 検証**: 272 葉の存在自体は保守目標にしないが、
  条件式の充足性・到達性・出力の不変条件を検査する方式は差別化の核。葉数を減らす
  判断は利用者価値と support tier の実測で行い、「数を増やす」ことを目標にしない。

**既存タスクとの重複**: support tier の実利用に基づく降格基準は §41.B に既にある。
ここでは別の support 削減タスクを追加せず、全葉検証が予算を超えた際の順序と
「サンプリングを保証と誤認させない」条件だけを明文化する。


## §45 完了: コード洗練リファクタリング wave(2026-10-12、4 エージェント並列)

外部挙動を全く変えず(生成物 byte-identical、CLI/警告/exit code 同一)に内部構造を整理。

### daimonion(tools/)
- preset 読み取り 3 実装を `tools/answers.py`(PresetError/preset_names/read_preset)に集約
- 裸 `yaml.safe_load` 7 サイトを `render_inputs.read_yaml_mapping` に統一(文言は呼出側で保持)
- support tier 走査を `support_ledger.rows_naming/base_is_promised` へ集約
- questionnaire 投影(by_name/schema/counts)を `questionnaire.py` に集約し MCP 重複を除去
- `_sha` 2 実装を `render_inputs.digest_bytes` に統一、stamp body を `batch.answers_body` に集約
- when_model tokenizer / predicates json_report / z3 build 等の長大関数を分割

### law-map
- `model.py`: `parse_iso_date`/`iter_groundings`/検査定型(`_check_one_of` 等)に集約、
  `_validate_obligation` を責務別 6 関数へ分割。directives 欠落時に enforcement 未検査だった
  潜在漏れを修正(実コーパス 15 件は全て directives 保有で観測挙動不変)
- `check.py`: probe 行生成を `format_*` 族へ集約、open-law probe を 3 関数に分割
- `cli.py`: `_print_issues`/`_print_report` で出力組立てを一元化
- `export.py`: Directives ビルダー分割、`_groundings` 重複を `obligation_groundings` に統合、dead `YEAR_0` 削除

### open-law
- `fetcher.py`: `fetch_result`/`fetch_bytes` の gate/rate-limit/wayback 二重実装を統合、
  robots/budget 計数順序の潜在不整合を修正
- `sources/base.py`: 全 12 adapter の重複ヘルパ(strip_markup/as_str/as_dict/xml_child 等)を
  基底クラスに集約し各 adapter を薄化
- `__main__.py`: fetch/text/dump の parser/wayback 配線 3 重複を統一、dead `all_topics` 削除

### good-future-codex
- `tools/validate.py`: FLAGGED 判定のマジックリテラルを定数化、ProbeFn 型エイリアス、
  check_sources/drift の URL probe を `_probe_unique_urls` に一本化、main を検証単位に分割

### 検証(親実施)
- law-map: validate 0 errors / warnings 集合同一 / check --sources skipped:6 可視化維持 / 84 passed
- codex: validate 0 warnings / --sources 0 flagged / 12 passed / `--sources` 出力 byte-identical
- open-law: 178 passed / live 層 skip 維持 / `sources` 出力一致 / ruff clean
- daimonion: test-fast 1153 passed(19.6s/30s)/ ruff+basedpyright clean / regen で witness は
  行順のみ(272 葉・3 excluded 同一)/ gen_docs --check 10 blocks in sync

## §46 完了: 質問・レイヤー・プリセットの自動 scaffold CLI + 検証体系 (2026-10-12)

272 葉の厳密な Z3 命題検証・不変条件体系に対する機能追加の心理的障壁を下げるため、
`daimonion scaffold` CLI および専用モジュール `tools/scaffold.py` を新設。

### 実装内容
- **`daimonion scaffold question <name>`**:
  - `questions/*.yml` に `when:`, `type:`, `default:`, `help:` を備えた推奨構文の質問ブロックを自動生成
  - `--when` 式の Z3 充足性（SAT）を事前検証し、タイポやデッド質問を警告
- **`daimonion scaffold layer <name>`**:
  - `include_<name>` 質問、`invariants.yml` の `include=include_<name>` 行、`template/{% if include_<name> %}...` の雛形を一括案内・生成
- **`daimonion scaffold preset <name>`**:
  - `presets/<name>.yml` の雛形生成（base project_type と推奨設定）
- **`daimonion scaffold check`**:
  - 全質問 when 式の Z3 SAT、全 12 プリセット、36 行の invariants の健全性を 1 コマンドで検証
- **テスト・Docs**:
  - `tests/test_scaffold.py`（7 テスト全緑）
  - `docs/how-to/scaffold.md` 新設、`how-to.md` および `zensical.toml` の目次に追加
  - `tests/test_cli.py` に `scaffold` サブコマンドの dispatch テストを追加

## §47 完了: AGENTS.md の軽量化と法務全文の折りたたみ分離 (2026-10-12)

生成される `AGENTS.md` の法務セクション（約 52,000 文字・数千トークン）による
AI エージェントのコンテキストウィンドウ圧迫と過剰反応を解消するため、
軽量化と詳細解説の折りたたみ分離を実施。

### 実装内容
- **要約とトリガーの直接露出**:
  - 各セクション冒頭の H1 タイトル、適用条件、要約（1–3 行の簡潔な指示）、Triggers 正規表現はそのまま常時可視
- **詳細散文の折りたたみ退避**:
  - 背景事実、判例引用、禁止パターンの詳細解説、制度変更ウォッチを `<details><summary>` ブロックに格納
  - AI エージェントは通常時は要約と Triggers のみを参照し、該当コード編集時のみ詳細を展開可能
- **検証と互換性の維持**:
  - `ETHICS_SECTIONS` の H1 タイトル検証、`test_ethics_registry.py` の 12 テスト、`test-fast`（1161 件全緑）、不変条件契約を 100% 保持

## §48 完了: law-lint 独立 Linter 新設 + gitleaks ライセンス課金の構造解消 (2026-10-13)

### law-lint（機械的法務トリガー Linter）
- **背景**: §47 で AGENTS.md を軽量化したが、エージェントが「どのセクションが
  自分の変更に関係するか」を判断する手段は文書読解に委ねられていた。
  差分を機械的に grep して該当ルールを報告する独立 Linter を新設。
- **リポジトリ**: `ConstitutiveTemplates/law-lint`（新規公開、CI 緑、
  zizmor 適合・SHA pin 済み）。依存は `pyyaml` のみ。
- **コマンド**: `law-lint diff`（git diff 対象のトリガー検出）、
  `law-lint check <path>`（ファイル/ディレクトリ走査）、`--strict`（L2 で exit 1）、
  `list-rules`。`--rules` で daimonion の `REGISTRY.yml` や codex YAML を直接ロード可能。
- **daimonion 側の連携**:
  - `AGENTS.md.jinja`: 「コミット前に `uvx --from git+https://github.com/ConstitutiveTemplates/law-lint law-lint diff`」を追記
  - `_tasks.jinja`: `legal-check` タスクを `quality_tasks` に追加
    （`agents_md_effective` ゲート、audit/license-check と同じネットワーク依存 one-off）
  - `.github-org` プロフィールの Repositories 表に law-lint を追加

### gitleaks-action のライセンス課金問題 → pin バイナリ置換
- **症状**: gitleaks-action v3 が org アカウントで `GITLEAKS_LICENSE` を要求し、
  hygiene ジョブが恒久赤（HUMAN_TODO「Secrets 再設定」の残件だった）。
- **修正**: `_hygiene.yml`（テンプレート＝リポジトリ同一ファイル）で
  `gitleaks/gitleaks-action` を削除し、`GITLEAKS_VERSION: 8.30.1` pin の
  release tarball ダウンロード + `gitleaks git --redact --config .gitleaks.toml`
  に置き換え。`workflow_call` の `GITLEAKS_LICENSE` secret 宣言と
  `ci.yml`/`ci.yml.jinja` の secret forward を撤去 — secret 自体が不要になった。
- **付随修正**:
  - `.gitleaks.toml`（テンプレ同一）に fixture パスの allowlist を追加
    （`tests/test_gitleaks_precommit.py` 履歴内ダミー値 + `tests/matrix/witnesses.jsonl`
    の `use_recommended_*` キー名誤検知）。ローカル全履歴スキャンで no leaks / exit 0 確認済み
  - `tools/check_upstream.py` の gitleaks-action 追跡を `GITLEAKS_VERSION` pin 追跡へ更新
  - `renovate.json.jinja` から gitleaks-action を除去
  - `tests/test_gitleaks_config.py`・`test_example_docs_ci.py` を新機構に更新
    （test-fast 1161 件全緑）
- **副次効果**: 「秘密情報検知が二重に停止中」だった状態のうち gitleaks 側が復旧。
  残る人間作業は `PYPI_API_TOKEN` のみ（HUMAN_TODO 更新済み）。


## §49 検討: 次期改善候補（2026-10-13 レビュー）

既存節・HUMAN_TODO と重複しない、実態確認済みのギャップと、着手条件を満たした
保留節。優先順。人間判断待ちは §35（deploy_target）・§5（MCP 本番運用、
web_api Docker 拡充と一体設計）・HUMAN_TODO（PYPI_API_TOKEN、private repo
分離、upstream F1–F7 投稿、push protection 再有効化）に既載のため割愛。

### A. 法務レイヤーの不整合（実害優先）

- [x] ~~**`legal-check` タスク未実装**~~ → **訂正（2026-10-13）**: `_tasks.jinja`
      L120 の `quality_tasks` に実装済み（`agents_md_effective` ゲート、
      `uvx ... law-lint diff --strict`）。grep が `template/` 配下のみを
      見た調査ミス。実ギャップは **AGENTS.md コマンド表への漏れ**:
      表は `agent_cmd_specs` から生成され `legal-check` が未登録のため
- [x] **完了: daimonion `legal-check` コマンド表登録** ✅ **2026-10-13 本 wave**
      （E1: `_tasks.jinja` の `agent_cmd_specs` に登録 + `tests/test_example_docs_ci.py`
      に 8 テスト追加 — 全 Taskfile に出ることと AGENTS.md 記載を `copy_project`
      レンダで検証；`audit`/`license-check` と同じネットワーク依存 one-off として
      表では inline spec なし）
- [x] **完了: law-lint `DEFAULT_RULES` と REGISTRY triggers の drift 防止** ✅ **2026-10-13 本 wave**
      （law-lint 側に `tools/check_ethics_parity.py` + 週次 `ethics-parity.yml`
      を新設 — REGISTRY active 12 行と `law-lint/rules.py` 組込みルールを
      12 対 12 でマップし、各ファイルの Triggers 正規表現と law-lint ルールの
      正規表現間でキーワード/プローブが相互にヒットすることを検証。
      `law-lint_linter/format/report.py` 直下のレポート経路は触れていないので
      本節の承諾経路とは独立）
- [x] ~~**law-map 未参照 checks 5 本の整理**~~ → **誤検出（2026-10-13）**:
      13 本全て check_refs で参照済み（例: `llm-tool-allowlist-gate` は
      `ai/llm-appsec-baseline` が参照。`grep -A3` で同一ファイル内のみを
      見た誤り）。対応不要
- [x] **完了: spec-less obligation 6 件 → 5 件 spec + contest-rules は L0 維持** ✅ **2026-10-13 本 wave**
      （E4+E5: `checks/ai/{ml-bias-mitigation,samd-clinical-evaluation}.yml`
      と `checks/privacy/european-accessibility-act.yml` +
      `checks/security/{prompt-injection-defense,public-ntp-hygiene}.yml` の
      5 本の L1 spec を新設し、各 obligation の `enforcement.level` を L0→L1 に
      引き上げて `check_refs:` を付与。`contest-rules` は venue 固有の規約確認が
      必須でコード検査の排水口がなく L0 維持を明記。`validate --warnings` の
      spec-less 警告は 6→1 に縮退、`law-map validate` は 0 errors, 84 passed）

### B. law-lint 強化

- [x] **完了: 機械可読出力** ✅ **2026-10-13 本 wave**（E2:
      `--format {human,json,sarif}` を `check|diff` に、human/json を
      `list-rules` に追加。JSON: `{summary:{findings,rules_matched,strict_fail}, findings:[...]}`、
      SARIF 2.1.0: `tool.driver.rules[]` + `results[]`、L2→error/L1→warning/L0→note。
      `--strict` の exit code 1/0 は書式によらず同一）
- [x] **完了: `.pre-commit-hooks.yaml` + 薄い GitHub Action** ✅ **2026-10-13 本 wave**（E3 一部:
      `.pre-commit-hooks.yaml` に `law-lint --strict diff --staged`（`pass_filenames:false`）、
      `action.yml` composite（`strict=true|args=diff`、SHA pin の `setup-uv` + `uvx`））
- [x] **完了: テスト拡充** ✅ **2026-10-13 本 wave**（E2: `context.py` の gate
      フォールバックを fail-closed（UserWarning 付き）に変更 + `tests/test_context.py`
      全ゲート通過/空白/不正構文/不束縛変数の境界テスト、`tests/test_cli.py` の
      `prepare --write`→`check` 自動読込/`--strict`/`--format`/`diff` 非
      git ディレクトリ/バイナリ・権限エラー時の抑止テスト。計 55 件全緑）
- [x] **完了: law-map checks spec への `triggers:` 接続** ✅ **2026-10-13**
      （law-map `bb623d7`: `src/law_map/checkspecs.py` で `triggers:` 正規表現
      リストをスキーマ検証（不正 regex は `validate` を落とす）＋全 18 spec
      に daimonion ethics 節と同語彙で付与；`external-transmission-declared`
      の未検出 YAML 破損も捕捉・修正。law-lint `5bbcc4e`:
      `Rule.from_check_spec` + `--rules` のディレクトリ受けで
      `law-lint --rules ../law-map/checks` が spec を直接消費。
      obligation → check spec → lint trigger → AGENTS.md 節のパイプライン閉結。
      law-map 94 passed / law-lint 63 passed）

### C. daimonion 本体

- [x] **§36 S5: invariants/layers の導出化**（着手条件充足）→ **計画着地
      2026-10-13**: `notes/plan-S5-derived-invariants.md`（commit `28af493e`）。
      36 葉行 + layers.yml 6 行を D（完全導出可）/ P（骨格導出・tier/markers/
      why は人間）/ H（手書き維持）に分類、`tools/gen_invariants.py
      --check/--write/--layers` と M0–M4 移行順を設計。実装は計画に従う別 wave
- [x] **§29 region 節の昇格再判断** → **判断記録済み（2026-10-13）: 保留継続**。
      region 節は 4 件で条件は数値的に充足したが、着地した 3 件目
      `region-eu-cra` は既存回答（`distribution: commercial`）で gate 可能
      だったため前提（市場ゲート節の同梱経路が要るか）が成立していない。
      `region-jp-external-transmission` / `region-eu-eaa`（audience `[web]`）は
      同梱参照（`ethics/regions.yml` + AGENTS.md ポインタ、葉 +0）で既に唯一の
      適用対象に届いており、昇格には `target_markets` 質問＝葉次元増が必要で
      対価が合わない。再トリガー条件: regions.yml チャネルを共有する
      **3 件目の市場ゲート節**の出現、または市場型質問が独立に正当化された時。
      別件: `region-kyushu-ntp` は audience ゲート型（iot→micropython 写像で
      葉 +0）で今でも昇格可能だが市場バンドル外のため本判断の対象外
- [x] **アーカイブ残 28 件の仕分け** → **仕分け済み（2026-10-13）**: §B 索引は
      人間作業中心だが「library 空依存
      の質問化（§17 L1058）」「render_project 戻り値・手書きテスト棚卸し
      （§23 L1841–1910）」「setup composite 化・未検証組合せ（§19 L1328–1348）」
      等エージェント可のものが混在。節ごとに agent-doable / human-only を
      付けて索引を更新。
      **実施結果**: agent-doable は実質 4 件（§2 OJ 追加・§5 スタンドアロン
      MCP レシピ・§5 MCP 本番運用・§19 未検証組合せ（実走確認のみ人間））で、
      他の agent-doable 7 件は着地済み（§4 Gmail・§16 由来明記・§21 fork
      作成・§15 ネスト教訓・§19 setup composite・§23 2 件）。残り ~16 件は
      人間専有（repo admin/secrets・外部投稿・設計判断）、§17 は「維持」
      決着済み。公開・運用系は本質的に人間作業

### D. エコシステム横断

- [x] **codex 逆方向 6 節の `related_sections` 配線確認** → **誤検出で解消
      （2026-10-13、law-map `2b2a453`）**: `law-map validate
      --codex` が報告する obligation 未接続節（contest-rules / ml-bias /
      prompt-injection / region-eu-eaa / kyushu-ntp / samd）のうち 4 件は
      §44 で obligation 追加済みのはず — 逆リンク未配線なら接続で警告解消。
      **実態**: 配線は全て正常（18 codex 節 ↔ 15 obligation が 1:1 解決、
      `--codex` は当初から 0 件）。警告は `_count_section_users` の
      「2 件未満で警告」ヒューリスティックの偽陽性 — codex id は一意が正常で
      単一参照は正しい形。offline 側の弱警告を撤去し `--codex` 時のみ
      検査する契約に変更。`validate --warnings` は 17→1 件（contest-rules
      spec-less の正当な通知のみ）
- [x] **完了: open-law key-free 法域 adapter 追加** ✅ **2026-10-13**
      （open-law `feat(mv)`: `asia-coverage.md` の key-free 候補を実プローブし
      mvlaw.gov.mv（Maldives AGO、robots allow、261 法）を選択 —
      lex.uz は SPA・PH Gazette は 403・Indonesia JDIH は到達不可。
      `MvLawAdapter`（fetch/search/full_text、サーバ描画経路）+ オフライン
      fixture テスト 9 件 + live-tier probe + `adapter-health.yml` + docs。
      187 passed / ruff・basedpyright clean）
- [x] **daimonion 未コミット差分の処理判断** → **コミット済み
      （2026-10-13）**: `tools/adopt*.py` 系 + テスト
      28 ファイル（+442/-627）の adopt 分解リファクタ差分が作業ツリーに残存。
      中断中なら `task test-fast` で状態確認し commit or stash。
      **実施**: `task test-fast` 1169 全緑・ruff/basedpyright clean を確認し
      `b780c44c`（refactor: lazy facade を adopt_types/adopt_revision/
      adopt_tree/adopt_run に分解）としてコミット。legal-check 表登録は
      `8f155bce` で別コミット
