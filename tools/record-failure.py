#!/usr/bin/env python3
"""
record-failure.py  ―  エージェントが遭遇した失敗や解決できなかった内容をナレッジベースに追記する
Ollama等ローカルLLMが次回起動時に同じ過ちを繰り返さないための自律的学習ログ。

使い方:
  uv run python tools/record-failure.py --agent pm --phase "プロジェクト走査" --issue "projects/配下が見つからない" --action "..."
"""

import sys
import argparse
import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="失敗・自己学習ログの記録")
    parser.add_argument("--agent",     required=True, help="発生したエージェント名（例: pm, coder）")
    parser.add_argument("--phase",     required=True, help="発生フェーズ（例: プロジェクト走査, スコアリング）")
    parser.add_argument("--issue",     required=True, help="発生した問題・できなかったこと")
    parser.add_argument("--action",    required=True, help="次回への改善アクション・対策")
    args = parser.parse_args()

    kb_dir = Path("docs/knowledge")
    kb_dir.mkdir(parents=True, exist_ok=True)
    failures_md = kb_dir / "failures.md"

    # ファイルがなければ初期化
    if not failures_md.exists():
        failures_md.write_text(
            "# 失敗・自己学習ログ（Knowledge Items）\n\n"
            "<!-- auto-managed by record-failure.py -->\n"
            "エージェントが直面した失敗や解決できなかったタスクと、その解決策を記録します。\n\n"
            "| 日時 | エージェント | フェーズ | 発生した問題 | 次回への改善策 |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n",
            encoding="utf-8"
        )

    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # パイプ文字の退避
    issue_escaped = args.issue.replace("|", "\\|").replace("\n", " ")
    action_escaped = args.action.replace("|", "\\|").replace("\n", " ")

    new_row = f"| {today} | {args.agent} | {args.phase} | {issue_escaped} | {action_escaped} |\n"

    with open(failures_md, "a", encoding="utf-8") as f:
        f.write(new_row)

    print(f"[record-failure] 失敗事例を記録しました: {args.issue[:30]}...")


if __name__ == "__main__":
    main()
