---
description: execute-issue Skillを使いIssue1件を実行する
agent: executor
subtask: false
---

Issue #$ARGUMENTS を実行します。`execute-issue` Skill を使用してください。

1. `.opencode/skills/execute-issue/scripts/get_issue.py $ARGUMENTS` を実行する
2. [BLOCKED] の場合は中断して報告する
3. [ACTIONABLE] の場合は実装方針を提示し、承認を得てから進める
