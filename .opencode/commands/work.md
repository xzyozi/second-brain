---
description: 指定されたIssue1件を実行しroadmap.mdの更新を提案する
agent: executor
subtask: false
---

Issue #$ARGUMENTS を実行します。

現在のIssue状態:
!`(grep -A 25 "## \[#$ARGUMENTS\]\|## #$ARGUMENTS\b\|## $ARGUMENTS " roadmap.md 2>/dev/null || grep -C 3 "$ARGUMENTS" projects/*/tasks.md 2>/dev/null) | head -28 || echo "Issue $ARGUMENTS が見つかりません"`

関連README:
!`find projects/ -name "README.md" | xargs grep -l "#$ARGUMENTS" 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo "（関連READMEなし）"`

実装案を提示してください。ファイル変更は提案のみ行い、承認後に実行してください。
完了後は必ず以下のコマンドを提案してください（直接実行しないこと）：
  python3 tools/update-roadmap.py $ARGUMENTS done
  python3 tools/notify.py --event task_done --issue $ARGUMENTS --title "（タイトル）"
