---
description: 現在のroadmap・タスク・ブロッカーの状態を俯瞰する
agent: sisyphus
subtask: false
---

プロジェクト全体の状態を確認します。

roadmap.md の概要:
!`uv run python tools/score-issues.py --out /dev/null 2>&1 | tail -6`

最新スコアキャッシュ:
!`cat tools/.cache/priority-cache.json 2>/dev/null | uv run python -c "import json,sys; d=json.load(sys.stdin); [print(f'  #{i[\"id\"]:<8} [{i.get(\"project\", \"core\"):<12}] score={i[\"score\"]:>5}  {i[\"title\"][:35]}') for i in d['issues'][:8]]" 2>/dev/null || echo "（未計算 — /orchestrate を実行してください）"`

ブロッカーサマリー:
!`cat tools/.cache/blocked.json 2>/dev/null | uv run python -c "import json,sys; d=json.load(sys.stdin); s=d['summary']; print(f'  blocked={s[\"blocked_count\"]}  actionable={s[\"actionable_count\"]}'); [print(f'  [{b[\"type\"]}] #{b[\"id\"]} {b[\"title\"][:35]}') for b in d['blocked']]" 2>/dev/null || echo "（未計算）"`

この状態を踏まえて、今日の推奨アクションを一言で教えてください。
