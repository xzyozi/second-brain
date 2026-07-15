#!/usr/bin/env python3
import sys
import re
import argparse
import datetime
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="既存タスクのメタデータ修正")
    parser.add_argument("project_dir",  help="対象プロジェクトのパス（例: projects/my-app）")
    parser.add_argument("task_id",      help="更新対象のタスクID（例: TFG-002）")
    parser.add_argument("--priority",   default=None, choices=["critical", "high", "medium", "low", "none"])
    parser.add_argument("--estimate",   default=None, help="工数見積もり（例: 2h, 1d）")
    args = parser.parse_args()

    tasks_path = Path(args.project_dir) / "tasks.md"
    if not tasks_path.exists():
        print(f"Error: {tasks_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    content = tasks_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    
    target_idx = -1
    pattern = re.compile(r"\[" + re.escape(args.task_id) + r"\]")
    for i, line in enumerate(lines):
        if pattern.search(line):
            target_idx = i
            break
            
    if target_idx == -1:
        print(f"Error: Task {args.task_id} not found in {tasks_path}.", file=sys.stderr)
        sys.exit(1)
        
    line = lines[target_idx]
    
    # コメント部分の抽出
    m_comment = re.search(r"<!--\s*(.*?)\s*-->", line)
    if not m_comment:
        print(f"Error: Metadata comment not found in task line: {line.strip()}", file=sys.stderr)
        sys.exit(1)
        
    comment_content = m_comment.group(1)
    
    # メタデータのパースと更新
    meta = {}
    for item in re.split(r"\s+", comment_content.strip()):
        if ":" in item:
            k, v = item.split(":", 1)
            meta[k] = v
            
    # 値の更新
    if args.priority:
        meta["priority"] = args.priority
    if args.estimate:
        meta["estimate"] = args.estimate
        
    meta["updated"] = datetime.date.today().isoformat()
    
    # 新しいコメント文字列の生成
    meta_str = " ".join(f"{k}:{v}" for k, v in meta.items())
    new_comment = f"<!-- {meta_str} -->"
    
    # 行の置換
    new_line = line[:m_comment.start()] + new_comment + line[m_comment.end():]
    lines[target_idx] = new_line
    
    # ファイルへの書き戻し
    tasks_path.write_text("".join(lines), encoding="utf-8")
    print(f"Successfully updated task {args.task_id} in {tasks_path}: priority={meta.get('priority')}, estimate={meta.get('estimate')}")

if __name__ == "__main__":
    main()
