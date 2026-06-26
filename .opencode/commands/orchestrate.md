---
description: スコアリング→ブロッカー判定→実行計画提示を一括実行する
agent: orchestrator
subtask: false
---

スコアリングとブロッカー判定を実行します。

スコアリング結果:
!`python3 tools/score-issues.py 2>&1 && echo "---" && cat tools/.cache/priority-cache.json`

ブロッカー判定結果:
!`python3 tools/check-blockers.py 2>&1 && echo "---" && cat tools/.cache/blocked.json`

上記のJSONを読み込み、【本日の実行計画】を提示してください。
actionable リストのうち priority-cache.json のスコア上位3件を選択してください。
