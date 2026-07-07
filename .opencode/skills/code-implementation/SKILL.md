---
name: code-implementation
description: |
  確定した仕様に基づいてコードを実装・修正する際の規約とチェックリスト。
  「実装して」「コードを書いて」「修正して」「リファクタして」といった依頼で使用する。
---

# Code Implementation Skill

## いつ使うか
- coder エージェントがファイルの新規作成・編集を行う直前

## 実装前チェックリスト（必ず確認してから着手する）

1. `.opencode/skills/execute-issue/scripts/get_issue.py <id>` の出力、
   または projects/<name>/README.md で仕様を再確認したか
2. projects/<name>/tasks.md で該当タスクが「未着手」であることを確認したか
3. 既存コードのスタイル・命名規則と整合しているか

## 実装時のルール

- **一度に変更するファイルは最大3ファイルまで。** それ以上は分割して提案する。
- 新規ファイルは `projects/<name>/src/` 配下に作成する。
- テストコードは `projects/<name>/tests/` 配下に作成する。
- `tools/*.py`（共有スクリプト）は無許可で変更しない。変更が必要な場合は
  理由を明示して人間に確認を求める。
- 外部パッケージを新規に追加する場合は、Python標準ライブラリで代替できないか
  先に検討する（ポータビリティ確保のため）。

## 出力フォーマット

```
【実装提案】
変更ファイル:
  - projects/<name>/src/xxx.py（新規）
  - projects/<name>/tests/test_xxx.py（新規）

変更内容:
  （箇条書き3行以内）

動作確認方法:
  python3 -m pytest projects/<name>/tests/

この内容で書き込みを承認しますか？
```

## 完了時のアクション

```bash
python3 tools/update-roadmap.py <issue_id> done --note "実装完了"
python3 tools/notify.py --event task_done --issue <issue_id> --title "<タイトル>"
```

## 関連スキル
- 完了報告後は notify-event Skill を使う
- 仕様確認には execute-issue Skill の get_issue.py を使う
