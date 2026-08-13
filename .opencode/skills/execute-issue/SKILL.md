---
name: execute-issue
description: |
  指定されたIssue番号1件の内容を安全に取得し、実行方針を組み立てる。
  「#XXを実行して」「Issue XXに着手」「/work」といった依頼で使用する。
  LLMが正規表現やgrepを自分で組み立ててroadmap.mdをパースするのを避け、
  必ず本スキルのスクリプトでIssue情報を取得すること。
---

# Execute Issue Skill

## いつ使うか
- 「#XXを実行して」「Issue XXに着手する」という依頼を受けたとき
- `/work <id>` コマンドから呼び出されたとき

## 手順（必ずこの順番で実行する）

1. 対象Issueの情報を取得する。

   ```bash
   python3 .opencode/skills/execute-issue/scripts/get_issue.py <issue_id>
   ```

   このスクリプトは以下を1回で返す:
   - roadmap.md 内の該当Issueブロック全文
   - 関連する projects/*/README.md（Issue番号への言及があれば）
   - 現在のブロッカー状態（ブロック中なら警告を出す）

2. `[BLOCKED]` と表示された場合は、実行を中断し人間に報告する。
   ブロッカーが解除されるまで着手してはいけない。

3. `[ACTIONABLE]` の場合、Issue内容を踏まえて実装方針を提示する。
   - ドキュメント作業のみ → 変更案を提示して人間の承認を待つ
   - コード実装が必要 → coder エージェントへの振り分けを提案する
     `opencode run --agent coder "<具体的な実装指示>"`

4. 作業完了後は以下のコマンドを提案する（自分で実行しない）:

   ```bash
   python3 tools/update-roadmap.py <issue_id> done --note "<完了内容>"
   python3 tools/notify.py --event task_done --issue <issue_id> --title "<タイトル>"
   ```

## 制約
- 複数のIssueを同時に進めてはいけない。常に1件のみ。
- ファイル変更は必ず「提案 → 人間の承認」の順序を守ること。

## 関連ファイル
- 呼び出すスクリプト: `scripts/get_issue.py`
- Issue状態更新: `tools/update-roadmap.py`（プロジェクト共有スクリプト）
- 通知: `tools/notify.py`（プロジェクト共有スクリプト）
