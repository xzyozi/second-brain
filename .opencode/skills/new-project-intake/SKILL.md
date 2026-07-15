---
name: new-project-intake
description: |
  新規プロジェクトの壁打ちヒアリングを行い、README.mdとtasks.mdの初期構造を生成する。
  「新しいプロジェクトを始めたい」「プロジェクトを立ち上げたい」といった依頼で使用する。
---

# New Project Intake Skill

## いつ使うか
- 「新しいプロジェクトを始めたい」という依頼を受けたとき
- `/new-proj <name>` コマンドから呼び出されたとき

## 手順（必ず1問ずつ・まとめて聞かない）

1. 以下の3問を **順番に1問ずつ** 尋ねる。相手の回答を待ってから次の質問に進む。

   - 質問1: 「このプロジェクトが解決する『誰のどんな痛み（Why）』を1行で言うと？」
   - 質問2: 「リリース初日に『これが動いていれば勝ち』と言える最小機能（MVP）は？」
   - 質問3: 「今思いつく中で、一番実装が面倒くさそうな技術的懸念は？」

2. 3つの回答が揃ったら、以下のスクリプトでプロジェクトの雛形を生成することを提案する
   （実行は人間の承認後）。

   ```bash
   python3 .opencode/skills/new-project-intake/scripts/scaffold_project.py \
     <project-name> \
     --why   "<質問1の回答>" \
     --mvp   "<質問2の回答>" \
     --risk  "<質問3の回答>"
   ```

   このスクリプトは `projects/<name>/README.md` と `projects/<name>/tasks.md` を
   決まったテンプレートで生成する。LLMが自分でMarkdownを組み立てて書き込むよりも、
   フォーマットの一貫性が保証される。

3. 生成後、必要であれば `tools/add-task.py` で初期タスクを追加することを提案する。

## 禁止事項
- 3問をまとめて質問してはいけない。
- 質問されていない情報を勝手に推測してREADMEに書き込んではいけない。
- README.md / tasks.md を直接編集で作成してはいけない。必ず scaffold_project.py を使う。

## 関連ファイル
- 呼び出すスクリプト: `scripts/scaffold_project.py`
- 追加のタスク登録: `tools/add-task.py`（プロジェクト共有スクリプト）
