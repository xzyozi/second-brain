---
name: priority-scoring
description: |
  roadmap.md の全Issueをスコアリングし、ブロッカーを検出して実行可能なIssueの優先順位を算出する。
  「今日何から着手すべきか」「優先度を教えて」「実行計画を出して」といった依頼で使用する。
  LLMはスコア計算やブロッカー判定をJSONで直接出力しようとせず、必ず本スキルのスクリプトを実行して結果を読むこと。
---

# Priority Scoring Skill

## いつ使うか
- 「今日の優先度」「次に何をすべきか」「実行計画」という依頼を受けたとき
- `/orchestrate` コマンドから呼び出されたとき

## 手順（必ずこの順番で実行する）

1. 以下のスクリプトを1回実行する。roadmap.md のスコアリングとブロッカー判定を
   一括で行い、人間可読なサマリーを標準出力に返す。

   ```bash
   python3 .opencode/skills/priority-scoring/scripts/run_pipeline.py
   ```

2. 出力された `[ACTIONABLE]` セクションの中から、スコア上位3件を選ぶ。
   `[BLOCKED]` セクションのIssueは選んではいけない。

3. 以下のフォーマットで実行計画を提示する。それ以外の文章を加えないこと。

   ```
   【本日の実行計画】
   1位: #XX「タイトル」（スコア: XX.X）→ 理由1文
   2位: #YY「タイトル」（スコア: YY.Y）→ 理由1文
   3位: #ZZ「タイトル」（スコア: ZZ.Z）→ 理由1文

   ブロック中: N件
     - #AA「タイトル」: [B1] 仕様未確定

   承認したら /work XX から開始します。よろしいですか？
   ```

## 禁止事項
- スコアの数値をLLM自身の推論で計算してはいけない。必ずスクリプトの出力を使う。
- `run_pipeline.py` 以外の方法（生のcatやgrep）でroadmap.mdを直接解析しようとしないこと。
  フォーマット崩れの原因になる。

## 関連ファイル
- 呼び出すスクリプト: `scripts/run_pipeline.py`
- 実際の計算ロジック: `tools/score-issues.py`, `tools/check-blockers.py`（プロジェクト共有スクリプト）
- 入力: `roadmap.md`（プロジェクトルート）
