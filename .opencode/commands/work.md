---
description: 指定されたIssue1件を実行しroadmap.mdの更新を提案する
agent: executor
subtask: false
---

Issue #$ARGUMENTS を実行します。

現在のIssue状態:
!`arg=$(echo $ARGUMENTS | xargs); for f in projects/*/tasks.md; do grep -C 8 "$arg" "$f" 2>/dev/null && echo "（ソース: $f）"; done | head -40 || echo "（grep失敗 → projects/ 配下の tasks.md を list/read ツールで直接確認してください）"`

親タスク/関連コンテキスト:
!`arg=$(echo $ARGUMENTS | xargs); parent_id=$(for f in projects/*/tasks.md; do grep "$arg" "$f" 2>/dev/null; done | grep -o 'parent:[A-Z0-9\-]*' | head -1 | cut -d: -f2); if [ -n "$parent_id" ]; then for f in projects/*/tasks.md; do grep -C 3 "$parent_id" "$f" 2>/dev/null; done; else echo "（直接の親タスクなし）"; fi`

関連README:
!`arg=$(echo $ARGUMENTS | xargs); find projects/ -name "README.md" 2>/dev/null | while read f; do grep -l "$arg" "$f" 2>/dev/null; done | head -1 | xargs cat 2>/dev/null || echo "（関連READMEなし）"`

上記の「現在のIssue状態」に表示されたタスク内容に基づいて、実装案を提示してください。
もし「現在のIssue状態」が空の場合は、projects/ ディレクトリ配下の tasks.md を read ツールで直接確認してタスク内容を把握してください。
ファイル変更は提案のみ行い、承認後に実行してください。
完了後は必ず以下のコマンドを提案してください（直接実行しないこと）：
  uv run python tools/update-roadmap.py $ARGUMENTS done
  uv run python tools/notify.py --event task_done --issue $ARGUMENTS --title "（タイトル）"
