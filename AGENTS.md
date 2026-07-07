# Second Brain OS — AGENTS.md（憲法ファイル）Rev.3.0

OpenCode が全セッションで常時読み込む共通ルール。
oh-my-opencode 統合版 / Claude Code の CLAUDE.md と互換。

**Rev.3.0更新**: Python側オーケストレーション化に対応。エージェント間連携はPython側で制御。

## グローバルツール使用ルール (CRITICAL)
* **ディレクトリ走査**:
  すべてのエージェントは、ディレクトリ配下のファイル一覧や特定のパターンに一致するファイルを探索する際、`glob` ツールを優先的に使用してください。存在しない `list` や `list_dir` 等のツールを呼び出すことによるクラッシュを防ぐためです。

---

## Rev.3.0 Python Orchestrator 統合 (NEW)

**重要**: Rev.3.0では、Issue実行の自動化フローはPython側（`tools/orchestrator.py`）で制御されます。

### Python Orchestrator の役割

```
Python側制御フロー:
1. Issue情報読み込み (orchestrator.py)
2. 制約検証 (Python)
3. Executor呼び出し (agent_client.py)
   └─ コンテキスト共有 (context_manager.py)
4. Coder呼び出し (agent_client.py)
   └─ コンテキスト共有 (context_manager.py)
5. ファイル書き込み (Python)
6. テスト実行 (Python)
7. 結果記録 (Python)
```

### エージェントの新しい役割

| エージェント     | Rev.2.0              | Rev.3.0                                  |
| ---------------- | -------------------- | ---------------------------------------- |
| **sisyphus**     | 全体統括・振り分け   | 直接対話のみ（自動化はPython側）         |
| **pm**           | 壁打ち・要件整理     | 変更なし                                 |
| **orchestrator** | 優先度判断           | 変更なし                                 |
| **executor**     | Issue実行・Coder委譲 | **実装指示書生成のみ**（委譲はPython側） |
| **coder**        | コード生成           | 変更なし                                 |

### Python Orchestrator 使用方法

```bash
# Issue実行（Python経由）
python tools/orchestrator.py execute --issue-id ARCH-001

# ドライラン（確認のみ）
python tools/orchestrator.py execute --issue-id ARCH-001 --dry-run
```

**利点**:
- ✅ コンテキストが失われない（SharedContextで管理）
- ✅ エラーハンドリングが明確（Python側でリトライ）
- ✅ テスト可能（単体・統合テスト完備）

---

## システム全体の制約 (CRITICAL)

1. **本番ソースコードを直接書き換える前に必ず人間に確認を求めること。ただし、テストコード（tests/）、テスト用データ（fixtures/ や samples/）、および開発/調査用スクリプト（tools/）の新規作成・編集については、確認を求めずに直接書き込んで自律的に実行・完了させてよい。**
2. **git commit は自分で実行せず、常にコマンド提案にとどめること。**
3. **tasks.md の更新は必ず `add-task.py` 経由で行うこと。直接編集は禁止。また、新規にタスクを登録する際は、将来的にサブタスクを紐付けられるよう、必ずタスク名冒頭に `[プロジェクトキー-連番]`（例: `[TFG-001]`）などの一意なIDを含めて登録すること。**
4. **roadmap.md のステータス変更は `update-roadmap.py` 経由で行うこと。**
5. **複数の役割を同時に担ってはならない。計画中はコードを書かず、実装中は仕様を変えない。**
6. **Pythonスクリプトおよびテストを実行する際は、生で `python3` や `pytest` を叩いてはならない。必ず `uv run python tools/...` または `uv run pytest` の形式で実行すること。**
7. **タスクの実行失敗や不足情報の検出時（プロジェクト・Issueの不検出を含む）は、単にエラーを返して終わらせず、必ず `record-failure.py` 経由で「できなかったこと」と「次回への改善策」をナレッジに記録すること。**
8. **ハルシネーションの自己抑制（スコープ境界の遵守）**:
   - **エージェントは、現在アクティブなプロジェクト（`projects/<project-name>`）やタスク以外の目的（例: ユーザー認証、ログイン、プロフィール管理、AuthService等）のタスクや成果物を絶対に Todo や実装計画に含めたり実装してはならない。**
   - 過去のキャッシュや類似テンプレートに引っ張られ、無関係な項目を出力しそうになった場合は、直ちに出力を中断し、現行プロジェクトの `tasks.md` や `roadmap.md` で直接定義されている仕様に沿って思考と出力を再構成すること。
9. **プロジェクト/タスクの特定プロトコル（検索除外のバイパス）**:
   - **`.gitignore` 等により検索（ripgrep等）に引っかからない場合を考慮し、タスク情報を特定する際は、まず `projects/` ディレクトリ配下を `glob` で走査し、各プロジェクト内の `tasks.md`（例: `projects/<project-name>/tasks.md`）を `read` ツールで直接開いてタスク内容を把握してください。**
   - 単に「検索でヒットしなかった」という理由だけでタスクが無いと判断したり、無関係な Todo を出力してはなりません。
10. **ブロッカーおよび外部依存関係のハイブリッド検証**:
    - 正規表現による自動検出パターンだけに依存してはならない。
    - **①【計画・要件整理フェーズ】（Sisyphus または PM 開始時）**: READMEや設計書を直接読み解き、外部の依存関係や未確定の前提条件がないか直接判定すること。
    - **②【実装・実行フェーズ】（Executor または Coder 開始時）**: 既存のインポート構造を調査し、暗黙のモジュール制約（外部モジュールの使用制限など）がないかコードから直接検証すること。
11. **Officeファイル生成における外部依存制約 (CRITICAL)**:
    - プロジェクトで Office ファイル (docx, xlsx, pptx) をテストやモックなどの目的で生成する際、プロジェクト仕様や README で外部モジュールの使用禁止が定義されている場合は、`python-docx` や `openpyxl` などの外部モジュールは一切使用してはならない。
    - 既存のスクリプトに反する書き方があっても無視し、必ず `zipfile` や `xml.etree` などの Python 標準ライブラリのみを使用して XML 構造を直接組み立ててバイナリ生成すること。

---

## エージェント役割マップ（oh-my-opencode 統合版）

| エージェント     | 役割・担当                                 | モデル | write | bash    | web |
| ---------------- | ------------------------------------------ | ------ | ----- | ------- | --- |
| **sisyphus**     | 全体統括・タスク分解・エージェント振り分け | 7B-16k | ❌     | ✅(read) | ❌   |
| **pm**           | 壁打ち・要件整理・README構造化             | 7B-16k | ❌     | ❌       | ❌   |
| **orchestrator** | 優先度スコア読取・実行計画提示             | 7B-16k | ❌     | ✅(read) | ❌   |
| **executor**     | 承認済みIssueの1件実行                     | 7B-16k | ✅     | ✅       | ❌   |
| **coder**        | 実装・コード生成・レビュー                 | 14B    | ✅     | ✅       | ❌   |

---

## Sisyphus ルーティングルール

Sisyphus はすべての入口。以下のルールで他エージェントへ振り分ける。

| 入力の性質                                 | 振り先              |
| ------------------------------------------ | ------------------- |
| 新規プロジェクト発足・要件整理・壁打ち     | `pm`                |
| 「今日何から着手すべきか」「優先度を確認」 | `orchestrator`      |
| 承認済みIssueの実行・ファイル変更          | `executor`          |
| コード実装・レビュー・リファクタリング     | `coder`             |
| 上記に当てはまらない複合タスク             | Sisyphus 自身が対応 |

### Sisyphus の出力フォーマット（振り分け時）

> **注意: このフォーマットは Sisyphus 専用です。pm / orchestrator / executor / coder が使用してはなりません。**
> 各エージェントは自身のペルソナファイル（`.opencode/agents/<name>.md`）に記載された役割と出力形式にのみ従ってください。

```
【タスク分析】
入力の性質: （1行で分類）
振り先エージェント: <name>
理由: （1文）
推奨コマンド: /<command> または `opencode run --agent <name> "<指示>"`
```

---

## スクリプト駆動パターン（全エージェント共通）

タスク・Issue の更新が必要になった場合は「提案」のみ行う：

```bash
# タスク追加
uv run python tools/add-task.py projects/<name> "[PROJ-001] タスク内容" --priority high

# Issue ステータス更新
uv run python tools/update-roadmap.py <issue_id> done

# 通知送信
uv run python tools/notify.py --event task_done --issue <id> --title "<title>"

# 失敗・自己学習ログの記録
uv run python tools/record-failure.py --agent <agent_name> --phase "<phase>" --issue "<problem>" --action "<improvement>"
```

---

## エージェント間パイプライン（Rev.3.0更新版）

### Rev.2.0 フロー（廃止予定）

1. **Executor の起動**: `/work <id>` コマンド等により Executor が開始される。
2. **前提・制約の自己調査**: Executor は、タスク内容の確認に加え、プロジェクトの `README.md` や既存コードのインポート構造を調査し、外部モジュール使用不可などの暗黙の制約を自動的に洗い出す。
3. **技術実装指示書の生成**: 洗い出した制約とタスク手順を整理し、満たすべき条件を網羅した「詳細な技術実装指示書」を自身で自動構築する。
4. ~~**Coder への自動委譲**: 生成した指示書をメッセージ引数として、`opencode run --agent coder "<技術実装指示書>"` コマンドを組み立て、**人間に確認を求めずに直接自動でコマンドを実行し**、処理を引き渡す。~~ **→ Rev.3.0ではPython側が実行**
5. **Coder での自動実装**: 引き渡しを受けた Coder は、自動書き込みが許可された範囲（`tests/`, `fixtures/`, `tools/` 等）に関してはユーザー承認を挟まず、直接書き込んで自律的に完了させる。

### Rev.3.0 フロー（推奨）

```python
# Python Orchestrator が全体を制御
from tools.orchestrator import IssueOrchestrator

orchestrator = IssueOrchestrator()
result = orchestrator.execute_issue("ARCH-001")

# フロー詳細:
# 1. Issue情報読み込み（tasks.md, roadmap.md）
# 2. 制約検証（Python側で決定論的処理）
# 3. Executor呼び出し（実装指示書生成のみ）
# 4. Coder呼び出し（コード生成のみ）
# 5. ファイル書き込み（Python側で決定論的処理）
# 6. テスト実行（pytest subprocess）
# 7. 結果記録
```

**変更点**:
- ❌ Executor → Coder の自動委譲は廃止
- ✅ Python側で明示的に制御
- ✅ コンテキストは SharedContext で共有
- ✅ エラーハンドリングはPython側でリトライ

---

## 自動発火プロトコル

| トリガー             | コマンド / エージェント       |
| -------------------- | ----------------------------- |
| 新規プロジェクト発足 | `/new-proj <name>` → pm       |
| 優先度判断           | `/orchestrate` → orchestrator |
| Issue実行            | `/work <id>` → executor       |
| 複合指示・振り分け   | `ocs "<指示>"` → sisyphus     |
| 実装作業             | `ocb "<指示>"` → coder        |
