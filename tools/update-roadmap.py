#!/usr/bin/env python3
"""
update-roadmap.py  ―  Issue ステータスを安全に更新する
LLM が直接 roadmap.md や tasks.md を書き換える代わりに、このスクリプトに委譲する。

使い方:
  uv run python tools/update-roadmap.py <issue_id> <status> [--note "コメント"]
  uv run python tools/update-roadmap.py TFG-002 done
  uv run python tools/update-roadmap.py 12 blocked --note "B1: API仕様未確定"
"""

import re
import sys
import argparse
import datetime
from pathlib import Path

VALID_STATUSES = {"open", "in-progress", "done", "blocked", "cancelled"}


def update_issue(text: str, iid: str, new_status: str, note: str | None) -> tuple[str, bool]:
    """Issue ブロックの見出し形式 (## [ID] または ## ID) の status: と updated: を書き換えた新しいテキストを返す"""
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
            block_new, count=1, flags=re.MULTILINE
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


def update_issue_list_format(text: str, iid: str, new_status: str, note: str | None) -> tuple[str, bool]:
    """チェックリスト形式 (- [ ] [ID]) のステータスとメタデータを更新した新しいテキストを返す"""
    status_map = {
        "done": "x",
        "in-progress": "/",
        "open": " ",
        "blocked": " ",
        "cancelled": "-"
    }
    char = status_map.get(new_status, " ")

    # ターゲット行を探す (例: - [ ] [TFG-002] タイトル <!-- metadata -->)
    pattern = re.compile(
        r"^(\s*-\s*\[)([ x/-]*)(\]\s*\[" + re.escape(iid) + r"\].*)$",
        re.MULTILINE
    )
    m = pattern.search(text)
    if not m:
        return text, False

    line = m.group(0)
    new_line = m.group(1) + char + m.group(3)

    # コメント内のメタデータ (<!-- ... -->) の更新
    comment_pattern = re.compile(r"<!--\s*(.*?)\s*-->")
    cm = comment_pattern.search(new_line)
    today = datetime.date.today().isoformat()

    if cm:
        meta_content = cm.group(1)
        # updated: を更新または追加
        if "updated:" in meta_content:
            meta_content = re.sub(r"updated:[^\s]+", f"updated:{today}", meta_content)
        else:
            meta_content += f" updated:{today}"

        # note: を更新または追加
        if note:
            if "note:" in meta_content:
                meta_content = re.sub(r"note:[^\s]+", f"note:{note}", meta_content)
            else:
                meta_content += f" note:{note}"

        new_line = new_line[:cm.start()] + f"<!-- {meta_content.strip()} -->" + new_line[cm.end():]
    else:
        # コメント自体がない場合は末尾に追加
        meta = f"updated:{today}"
        if note:
            meta += f" note:{note}"
        new_line = new_line.rstrip() + f"  <!-- {meta} -->"

    new_text = text[:m.start()] + new_line + text[m.end():]
    return new_text, True


def main():
    parser = argparse.ArgumentParser(description="Issue ステータス更新（LLM非使用）")
    parser.add_argument("issue_id", help="更新対象の Issue 番号（例: TFG-002）")
    parser.add_argument("status",   choices=sorted(VALID_STATUSES), help="新しいステータス")
    parser.add_argument("--roadmap", default=None, help="明示的なロードマップファイルのパス")
    parser.add_argument("--note",    default=None, help="任意のコメント")
    args = parser.parse_args()

    is_explicit = args.roadmap is not None
    roadmap_path_str = args.roadmap or "roadmap.md"
    roadmap_path = Path(roadmap_path_str)

    target_files = []
    if is_explicit:
        if not roadmap_path.exists():
            print(f"[update-roadmap] ERROR: {roadmap_path} が見つかりません")
            sys.exit(1)
        target_files.append(roadmap_path)
    else:
        # デフォルト動作：まず roadmap.md を候補にし、さらに projects/*/tasks.md も候補にする
        if roadmap_path.exists():
            target_files.append(roadmap_path)
        # projects/*/tasks.md を探す
        for p in Path("projects").glob("*/tasks.md"):
            target_files.append(p)


    updated_file = None
    original_content = None
    updated_content = None

    for target in target_files:
        original = target.read_text(encoding="utf-8")
        
        # 1. 見出し形式の更新を試みる
        updated, changed = update_issue(original, args.issue_id, args.status, args.note)
        if changed:
            updated_file = target
            original_content = original
            updated_content = updated
            break
            
        # 2. リスト形式の更新を試みる
        updated, changed = update_issue_list_format(original, args.issue_id, args.status, args.note)
        if changed:
            updated_file = target
            original_content = original
            updated_content = updated
            break

    if not updated_file:
        print(f"[update-roadmap] ERROR: Issue #{args.issue_id} が見つかりませんでした")
        sys.exit(1)

    # バックアップを残してから書き込む
    backup = updated_file.with_suffix(updated_file.suffix + ".bak")
    backup.write_text(original_content, encoding="utf-8")
    updated_file.write_text(updated_content, encoding="utf-8")

    note_str = f" / note: {args.note}" if args.note else ""
    print(f"[update-roadmap] #{args.issue_id} → {args.status}{note_str} in {updated_file} (backup: {backup})")


if __name__ == "__main__":
    main()
