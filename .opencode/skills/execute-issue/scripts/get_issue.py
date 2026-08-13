#!/usr/bin/env python3
"""
get_issue.py  ―  execute-issue Skill 用ヘルパースクリプト

指定された Issue ID の情報を roadmap.md から安全に抽出し、
関連する README.md・現在のブロッカー状態も合わせて返す。

設計意図:
  LLMに「grep '#12' roadmap.md」のような即興のbashコマンドを
  組み立てさせると、Issue番号の桁違い一致（#1 が #12 にもマッチする等）
  で誤動作しやすい。正規表現の境界処理をスクリプト側で保証する。

依存: Python標準ライブラリのみ
使い方:
  python3 .opencode/skills/execute-issue/scripts/get_issue.py <issue_id>
"""

import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ROADMAP = ROOT / "roadmap.md"
CACHE = ROOT / "tools" / ".cache"
PROJECTS = ROOT / "projects"


def extract_issue_block(text: str, issue_id: str) -> str | None:
    """Issue番号の完全一致で1ブロックだけを取り出す（#1 が #12 に誤爆しない）"""
    pattern = re.compile(
        r"(^## \[?#?" + re.escape(issue_id) + r"\]?(?!\d)[^\n]*$.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(0).strip() if m else None


def find_related_readmes(issue_id: str) -> list[str]:
    """Issue番号への言及があるREADME.mdを探す"""
    hits = []
    if not PROJECTS.exists():
        return hits
    for readme in PROJECTS.glob("*/README.md"):
        content = readme.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"#" + re.escape(issue_id) + r"(?!\d)", content):
            hits.append(str(readme.relative_to(ROOT)))
    return hits


def check_blocked_status(issue_id: str) -> dict | None:
    blocked_path = CACHE / "blocked.json"
    if not blocked_path.exists():
        return None
    data = json.loads(blocked_path.read_text(encoding="utf-8"))
    for b in data.get("blocked", []):
        if b["id"] == issue_id:
            return b
    return None


def main():
    if len(sys.argv) != 2:
        print("使い方: get_issue.py <issue_id>", file=sys.stderr)
        sys.exit(1)

    issue_id = sys.argv[1]

    if not ROADMAP.exists():
        print(f"[ERROR] roadmap.md が見つかりません: {ROADMAP}")
        sys.exit(1)

    text = ROADMAP.read_text(encoding="utf-8")
    block = extract_issue_block(text, issue_id)

    if block is None:
        print(f"[ERROR] Issue #{issue_id} が roadmap.md に見つかりません")
        sys.exit(1)

    blocked_info = check_blocked_status(issue_id)

    if blocked_info:
        print(f"[BLOCKED] Issue #{issue_id} はブロック中です")
        print(f"  分類: [{blocked_info['type']}] {blocked_info['label']}")
        print(f"  詳細: {blocked_info['detail']}")
        print(f"  対応: {blocked_info['action']}")
        print()
        print("--- Issue内容 ---")
        print(block)
        return   # ブロック中でも内容自体は見せる（人間が判断できるように）

    print(f"[ACTIONABLE] Issue #{issue_id} は実行可能です")
    print()
    print("--- Issue内容 ---")
    print(block)

    readmes = find_related_readmes(issue_id)
    if readmes:
        print()
        print("--- 関連README ---")
        for r in readmes:
            print(f"  {r}")
            content = (ROOT / r).read_text(encoding="utf-8", errors="ignore")
            print("  " + "\n  ".join(content.splitlines()[:20]))  # 冒頭20行のみ


if __name__ == "__main__":
    main()
