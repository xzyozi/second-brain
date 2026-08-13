#!/usr/bin/env python3
"""
add-task.py  ―  tasks.md へタスクを安全に追記する
LLM が直接 tasks.md を編集する代わりに呼び出す安全装置。

使い方:
  uv run python tools/add-task.py projects/<name> "タスク内容"
  uv run python tools/add-task.py projects/my-app "ユーザー認証APIを実装する" --priority high
  uv run python tools/add-task.py projects/my-app "サブタスク内容" --parent TFG-001 --priority high
  uv run python tools/add-task.py projects/my-app "XMLパーサー実装" --priority medium --with-verify
"""

import re
import sys
import argparse
import datetime
from pathlib import Path


def find_parent_line_index(lines: list[str], parent_id: str) -> int:
    """親タスクIDを含む行のインデックスを返す。見つからなければ -1。"""
    pattern = re.compile(r"\[" + re.escape(parent_id) + r"\]")
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return -1


def find_insert_position_after_parent(lines: list[str], parent_idx: int) -> int:
    """親タスクの直下にある既存サブタスク群の末尾位置（挿入位置）を返す。"""
    parent_line = lines[parent_idx]
    # 親行のインデント幅を取得
    parent_indent = len(parent_line) - len(parent_line.lstrip())

    insert_at = parent_idx + 1
    for i in range(parent_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            # 空行は飛ばす（ただしサブタスクブロックの途中の空行に対応）
            insert_at = i + 1
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent > parent_indent:
            # 子（サブタスク）行なので続行
            insert_at = i + 1
        else:
            # 親と同じかそれより浅いインデント → サブタスク群が終わった
            break
    return insert_at


def main():
    parser = argparse.ArgumentParser(description="タスク追記（LLM非使用）")
    parser.add_argument("project_dir",  help="対象プロジェクトのパス（例: projects/my-app）")
    parser.add_argument("task",         help="追記するタスク内容")
    parser.add_argument("--priority",   default="medium",
                        choices=["critical", "high", "medium", "low", "none"])
    parser.add_argument("--estimate",   default=None, help="工数見積もり（例: 2h, 1d）")
    parser.add_argument("--parent",     default=None, help="親タスクのID（例: TFG-001）。指定時はサブタスクとして追記")
    parser.add_argument("--blockedby",  default=None, help="依存する先行タスクのID（例: TFG-001）")
    parser.add_argument("--with-verify", action="store_true", default=False,
                        help="検証サブタスク（{ID}-v）を自動生成する")
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
    parent_id = args.parent.strip("[]") if args.parent else None
    parent_meta = f" parent:{parent_id}" if parent_id else ""

    blockedby_id = args.blockedby.strip("#[] ") if args.blockedby else None
    blockedby_meta = f" blockedby:#{blockedby_id}" if blockedby_id else ""

    if parent_id:
        # ── サブタスク追記モード ──
        indent = "  "
        new_line = (
            f"{indent}- [ ] {args.task}  "
            f"<!-- priority:{args.priority}{estimate}{parent_meta}{blockedby_meta} added:{today} -->\n"
        )

        lines = content.splitlines(keepends=True)
        parent_idx = find_parent_line_index(lines, parent_id)

        if parent_idx == -1:
            print(f"[add-task] [ERROR] 親タスク [{parent_id}] が {tasks_path} に見つかりません。", file=sys.stderr)
            sys.exit(1)

        insert_at = find_insert_position_after_parent(lines, parent_idx)
        lines.insert(insert_at, new_line)
        content = "".join(lines)
        tasks_path.write_text(content, encoding="utf-8")
        print(f"[add-task] '{args.task}' → {tasks_path}  (priority:{args.priority}, parent:{parent_id})")


    else:
        # ── 通常のフラット追記モード（従来動作） ──
        new_line = (
            f"- [ ] {args.task}  "
            f"<!-- priority:{args.priority}{estimate}{blockedby_meta} added:{today} -->\n"
        )

        if "## 未着手" in content:
            content = content.replace("## 未着手\n", f"## 未着手\n{new_line}", 1)
        else:
            content += f"\n{new_line}"

        tasks_path.write_text(content, encoding="utf-8")
        print(f"[add-task] '{args.task}' → {tasks_path}  (priority:{args.priority})")

    # ── --with-verify: 検証サブタスクの自動生成 ──
    if args.with_verify:
        _add_verify_subtask(tasks_path, args.task, args.priority, today)


def _extract_task_id(task_text: str) -> str:
    """タスク文字列から [ID] 形式のIDを抽出する。見つからなければ空文字列を返す。"""
    m = re.match(r"^\[?([A-Z][A-Z0-9]*-\d+[A-Za-z0-9-]*)\]?\s", task_text)
    if m:
        return m.group(1)
    return ""


def _add_verify_subtask(tasks_path: Path, task_text: str, priority: str, today: str):
    """検証サブタスクを tasks.md に追加する"""
    task_id = _extract_task_id(task_text)
    if not task_id:
        print(f"[add-task] [WARN] --with-verify: タスク文からIDを抽出できませんでした。検証サブタスクの自動生成をスキップします。",
              file=sys.stderr)
        return

    verify_id = f"{task_id}-v"
    verify_line = (
        f"  - [ ] [{verify_id}] {task_id} の検証  "
        f"<!-- priority:{priority} parent:{task_id} blockedby:#{task_id} type:verify added:{today} -->\n"
    )

    content = tasks_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # 親タスク行を検索し、その直下に検証サブタスクを挿入
    parent_idx = find_parent_line_index(lines, task_id)
    if parent_idx == -1:
        print(f"[add-task] [WARN] --with-verify: 親タスク [{task_id}] が見つかりません。検証サブタスクをスキップします。",
              file=sys.stderr)
        return

    insert_at = find_insert_position_after_parent(lines, parent_idx)
    lines.insert(insert_at, verify_line)
    tasks_path.write_text("".join(lines), encoding="utf-8")
    print(f"[add-task] 検証サブタスク [{verify_id}] を自動追加しました (parent:{task_id}, blockedby:#{task_id})")

if __name__ == "__main__":
    main()

