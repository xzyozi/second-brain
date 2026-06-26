---
description: 新規プロジェクトのキックオフ壁打ちを開始する
agent: pm
subtask: false
---

新規プロジェクト「$ARGUMENTS」が発足しました。

現在のプロジェクト一覧:
!`ls projects/ 2>/dev/null || echo "（まだプロジェクトはありません）"`

AGENTS.md の「自動発火プロトコル」に従い、
質問1（Why）から1問ずつヒアリングを開始してください。
3問終了後、projects/$ARGUMENTS/README.md への書き出しコマンドを提案してください。
