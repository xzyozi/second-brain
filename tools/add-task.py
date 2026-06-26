#!/usr/bin/env python3
"""
add-task.py  ―  tasks.md へタスクを安全に追記する
LLM が直接 tasks.md を編集する代わりに呼び出す安全装置。

使い方:
  python3 tools/add-task.py projects/<name> "タスク内容"
  python3 tools/add-task.py projects/my-app "ユーザー認証APIを実装する" --priority high
"""

import re
import sys
import argparse
import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="タスク追記（LLM非使用）")
    parser.add_argument("project_dir",  help="対象プロジェクトのパス（例: projects/my-app）")
    parser.add_argument("task",         help="追記するタスク内容")
    parser.add_argument("--priority",   default="medium",
                        choices=["critical", "high", "medium", "low", "none"])
    parser.add_argument("--estimate",   default=None, help="工数見積もり（例: 2h, 1d）")
    args = parser.parse_args()

    tasks_path = Path(args.project_dir) / "tasks.md"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)

    # 既存ファイルがなければヘッダー付きで作成
    if not tasks_path.exists():
        tasks_path.write_text(
            f"# タスクリスト\n\n<!-- auto-managed by add-task.py -->\n\n"
            f"## 未着手\n\n## 進行中\n\n## 完了\n",
            encoding="utf-8",
        )

    content = tasks_path.read_text(encoding="utf-8")

    today    = datetime.date.today().isoformat()
    estimate = f" estimate:{args.estimate}" if args.estimate else ""
    new_line = (
        f"- [ ] {args.task}  "
        f"<!-- priority:{args.priority}{estimate} added:{today} -->\n"
    )

    # "## 未着手" セクションの直後に挿入
    if "## 未着手" in content:
        content = content.replace("## 未着手\n", f"## 未着手\n{new_line}", 1)
    else:
        content += f"\n{new_line}"

    tasks_path.write_text(content, encoding="utf-8")
    print(f"[add-task] '{args.task}' → {tasks_path}  (priority:{args.priority})")


if __name__ == "__main__":
    main()
