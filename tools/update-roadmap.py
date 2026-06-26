#!/usr/bin/env python3
"""
update-roadmap.py  ―  Issue ステータスを安全に更新する
LLM が直接 roadmap.md を書き換える代わりに、このスクリプトに委譲する。

使い方:
  python3 tools/update-roadmap.py <issue_id> <status> [--note "コメント"]
  python3 tools/update-roadmap.py 12 done
  python3 tools/update-roadmap.py 12 blocked --note "B1: API仕様未確定"
"""

import re
import sys
import argparse
import datetime
from pathlib import Path

VALID_STATUSES = {"open", "in-progress", "done", "blocked", "cancelled"}
ROADMAP = Path("roadmap.md")


def update_issue(text: str, iid: str, new_status: str, note: str | None) -> tuple[str, bool]:
    """Issue ブロックの status: と updated: を書き換えた新しいテキストを返す"""
    pattern = re.compile(
        r"(^## \[?#?" + re.escape(iid) + r"\]?.+$.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return text, False

    block_old = m.group(0)
    block_new = block_old

    today = datetime.date.today().isoformat()

    # status: 行を更新（なければ追加）
    if re.search(r"^- status:", block_new, re.MULTILINE):
        block_new = re.sub(
            r"^(- status:)\s*\w.*$",
            f"- status: {new_status}",
            block_new, flags=re.MULTILINE
        )
    else:
        # 最初の箇条書き行の前に挿入
        block_new = re.sub(
            r"^(- )",
            f"- status: {new_status}\n- ",
            block_new, count=1, flags=re.MULTILINE
        )

    # updated: を今日に更新（なければ追加）
    if re.search(r"^- updated:", block_new, re.MULTILINE):
        block_new = re.sub(
            r"^(- updated:)\s*[\d\-]+",
            f"- updated: {today}",
            block_new, flags=re.MULTILINE
        )
    else:
        block_new = block_new.rstrip() + f"\n- updated: {today}\n"

    # --note がある場合は末尾に追記
    if note:
        block_new = block_new.rstrip() + f"\n- note: {note}\n"

    new_text = text[:m.start()] + block_new + text[m.end():]
    return new_text, True


def main():
    parser = argparse.ArgumentParser(description="Issue ステータス更新（LLM非使用）")
    parser.add_argument("issue_id", help="更新対象の Issue 番号（例: 12）")
    parser.add_argument("status",   choices=sorted(VALID_STATUSES), help="新しいステータス")
    parser.add_argument("--roadmap", default="roadmap.md")
    parser.add_argument("--note",    default=None, help="任意のコメント")
    args = parser.parse_args()

    roadmap_path = Path(args.roadmap)
    if not roadmap_path.exists():
        print(f"[update-roadmap] ERROR: {roadmap_path} が見つかりません")
        sys.exit(1)

    original = roadmap_path.read_text(encoding="utf-8")
    updated, changed = update_issue(original, args.issue_id, args.status, args.note)

    if not changed:
        print(f"[update-roadmap] ERROR: Issue #{args.issue_id} が見つかりませんでした")
        sys.exit(1)

    # バックアップを残してから書き込む
    backup = roadmap_path.with_suffix(".md.bak")
    backup.write_text(original, encoding="utf-8")
    roadmap_path.write_text(updated, encoding="utf-8")

    note_str = f" / note: {args.note}" if args.note else ""
    print(f"[update-roadmap] #{args.issue_id} → {args.status}{note_str}  (backup: {backup})")


if __name__ == "__main__":
    main()
