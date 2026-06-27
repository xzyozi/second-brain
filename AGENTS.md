# Second Brain OS — AGENTS.md（憲法ファイル）

OpenCode が全セッションで常時読み込む共通ルール。
oh-my-opencode 統合版 / Claude Code の CLAUDE.md と互換。

---

## システム全体の制約 (CRITICAL)

1. **ファイルを直接書き換える前に必ず人間に確認を求めること。**
2. **git commit は自分で実行せず、常にコマンド提案にとどめること。**
3. **tasks.md の更新は必ず `add-task.py` 経由で行うこと。直接編集は禁止。**
4. **roadmap.md のステータス変更は `update-roadmap.py` 経由で行うこと。**
5. **複数の役割を同時に担ってはならない。計画中はコードを書かず、実装中は仕様を変えない。**
6. **Pythonスクリプトおよびテストを実行する際は、生で `python3` や `pytest` を叩いてはならない。必ず `uv run python tools/...` または `uv run pytest` の形式で実行すること。**

---

## エージェント役割マップ（oh-my-opencode 統合版）

| エージェント     | 役割・担当                         | モデル        | write | bash | web |
|--------------|----------------------------------|-------------|-------|------|-----|
| **sisyphus** | 全体統括・タスク分解・エージェント振り分け | 7B-16k      | ❌    | ✅(read) | ❌ |
| **pm**       | 壁打ち・要件整理・README構造化       | 7B-16k      | ❌    | ❌   | ❌ |
| **orchestrator** | 優先度スコア読取・実行計画提示     | 7B-16k      | ❌    | ✅(read) | ❌ |
| **executor** | 承認済みIssueの1件実行             | 7B-16k      | ✅    | ✅   | ❌ |
| **coder**    | 実装・コード生成・レビュー           | 14B         | ✅    | ✅   | ❌ |

---

## Sisyphus ルーティングルール

Sisyphus はすべての入口。以下のルールで他エージェントへ振り分ける。

| 入力の性質                              | 振り先         |
|--------------------------------------|-------------|
| 新規プロジェクト発足・要件整理・壁打ち     | `pm`        |
| 「今日何から着手すべきか」「優先度を確認」  | `orchestrator` |
| 承認済みIssueの実行・ファイル変更        | `executor`  |
| コード実装・レビュー・リファクタリング     | `coder`     |
| 上記に当てはまらない複合タスク           | Sisyphus 自身が対応 |

### Sisyphus の出力フォーマット（振り分け時）
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
uv run python tools/add-task.py projects/<name> "タスク内容" --priority high

# Issue ステータス更新
uv run python tools/update-roadmap.py <issue_id> done

# 通知送信
uv run python tools/notify.py --event task_done --issue <id> --title "<title>"
```

---

## 自動発火プロトコル

| トリガー               | コマンド / エージェント            |
|---------------------|-------------------------------|
| 新規プロジェクト発足    | `/new-proj <name>` → pm       |
| 優先度判断             | `/orchestrate` → orchestrator |
| Issue実行             | `/work <id>` → executor       |
| 複合指示・振り分け      | `ocs "<指示>"` → sisyphus     |
| 実装作業               | `ocb "<指示>"` → coder        |
