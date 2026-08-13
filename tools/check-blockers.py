#!/usr/bin/env python3
"""
check-blockers.py  ―  Layer 2 / Step 2
roadmap.md を解析し、ブロッカー6分類を正規表現で確定的に検出。
LLM を一切使用しない決定的スクリプト。

使い方:
  uv run python tools/check-blockers.py [--roadmap roadmap.md] [--out tools/.cache/blocked.json]
"""

import re
import json
import argparse
import datetime
import sys
from pathlib import Path
import os
import logging
# プロジェクトのルートディレクトリをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.task_parser import parse_tasks_file as parser_parse_tasks

# loggerの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("check-blockers")

# ── ブロッカー6分類の定義 ────────────────────────────────────────
BLOCKER_RULES: list[dict] = [
    {
        "type":        "B1",
        "label":       "仕様不明確",
        "patterns":    [r"仕様未確定", r"要確認", r"\bTBD\b", r"spec\?", r"unclear", r"not defined"],
        "action":      "LLMに質問事項を列挙させ、人間の確認後に再着手する",
        "auto_skip":   True,
    },
    {
        "type":        "B2",
        "label":       "依存Issue未完了",
        "patterns":    [r"blockedby:\s*#?[A-Z0-9\-]+"],
        "action":      "先行Issueのスコアを繰り上げ・先に実行する",
        "auto_skip":   True,
    },
    {
        "type":        "B3",
        "label":       "技術的調査未完",
        "patterns":    [r"\[ \]\s*技術調査", r"spike:\s*open", r"research:\s*pending", r"調査未完"],
        "action":      "調査タスクを最優先に昇格して実行する",
        "auto_skip":   True,
    },
    {
        "type":        "B4",
        "label":       "レビュー待ち",
        "patterns":    [r"waiting.*review", r"PR.*open", r"review:\s*pending", r"レビュー待ち"],
        "action":      "人間への通知のみ・スキップ",
        "auto_skip":   True,
    },
    {
        "type":        "B5",
        "label":       "外部依存待ち",
        "patterns":    [r"waiting.*external", r"\bvendor\b", r"third.party", r"外部待ち", r"API待ち"],
        "action":      "スキップ・優先度を最低に引き下げる",
        "auto_skip":   True,
    },
    {
        "type":        "B6",
        "label":       "リソース不足",
        "patterns":    [r"resource:\s*missing", r"requires.*budget", r"予算未確定", r"リソース不足"],
        "action":      "人間への通知のみ・スキップ",
        "auto_skip":   True,
    },
]


def detect_blockers(iid: str, title: str, block: str) -> list[dict]:
    """1 Issue ブロック内に対してすべてのルールを試行し、合致したものを返す"""
    found = []
    for rule in BLOCKER_RULES:
        for pat in rule["patterns"]:
            m = re.search(pat, block, re.IGNORECASE)
            if m:
                detail = m.group(0).strip()
                found.append({
                    "id":     iid,
                    "title":  title,
                    "type":   rule["type"],
                    "label":  rule["label"],
                    "detail": detail,
                    "action": rule["action"],
                })
                break   # 同ルール内での重複マッチを避ける
    return found


def parse_and_check(text: str) -> tuple[list[dict], list[str]]:
    """roadmap.md 全体を解析し (blocked_list, actionable_ids) を返す"""
    blocked_all: list[dict] = []
    blocked_ids: set[str]   = set()
    all_ids:     list[str]  = []

    for block in re.split(r"(?=^## )", text, flags=re.MULTILINE):
        m = re.match(r"^## \[?#?([A-Z0-9\-]+)\]?\s+(.+)", block)
        if not m:
            continue
        iid, title = m.group(1), m.group(2).strip()

        # 完了済みは除外
        if re.search(r"status:\s*(done|closed|cancelled)", block, re.IGNORECASE):
            continue

        all_ids.append(iid)
        hits = detect_blockers(iid, title, block)
        if hits:
            for h in hits:
                h["project"] = "core"
            blocked_all.extend(hits)
            blocked_ids.add(iid)

    actionable = [i for i in all_ids if i not in blocked_ids]
    return blocked_all, actionable


def parse_tasks_file(text: str, project_key: str, project_name: str) -> tuple[list[dict], list[str]]:
    """
    tasks.md からブロッカー情報と実行可能Issue IDを抽出する。
    """
    blocked_all: list[dict] = []
    blocked_ids: set[str] = set()
    all_ids: list[str] = []
    
    task_items = parser_parse_tasks(text, project_key, project_name)
    blocked_all = []
    blocked_ids = set()
    all_ids = []

    for item in task_items:
        # 完了済みはスキップ
        if item.status == "done":
            continue
            
        status = "in-progress" if item.status == "in-progress" else "open"
        priority = item.priority
        estimate = item.estimate
        updated = item.updated
        
        extra_lines = []
        for b in item.blockedby:
            dep = b if b.startswith("#") else f"#{b}"
            extra_lines.append(f"- blockedby: {dep}")
        for blocker in item.extra_blockers:
            extra_lines.append(f"- {blocker}: info")
            
        # 擬似ブロックを再構築
        block_text = f"## [{item.id}] {item.title}\n"
        block_text += f"- status: {status}\n"
        block_text += f"- priority-{priority}\n"
        if estimate:
            block_text += f"- estimate: {estimate}\n"
        if updated:
            block_text += f"- updated: {updated}\n"
        for extra in extra_lines:
            block_text += f"{extra}\n"

        all_ids.append(item.id)
        hits = detect_blockers(item.id, item.title, block_text)
        if hits:
            for h in hits:
                h["project"] = project_name
                # 親タスクIDがあればバインド
                if item.parent:
                    h["parent"] = item.parent
            blocked_all.extend(hits)
            blocked_ids.add(item.id)

    actionable = [i for i in all_ids if i not in blocked_ids]
    return blocked_all, actionable


def main():
    parser = argparse.ArgumentParser(description="ブロッカー判定（Layer 2 / Step 2）")
    parser.add_argument("--roadmap", default="roadmap.md")
    parser.add_argument("--out",     default="tools/.cache/blocked.json")
    args = parser.parse_args()

    blocked_all = []
    actionable_all = []

    # 1. 母艦 roadmap.md
    roadmap_path = Path(args.roadmap)
    if roadmap_path.exists():
        text = roadmap_path.read_text(encoding="utf-8")
        blocked, actionable = parse_and_check(text)
        blocked_all.extend(blocked)
        actionable_all.extend(actionable)
    else:
        logger.warning(f"roadmap.md が見つかりません: {roadmap_path}")

    # 2. 衛星プロジェクト
    projects_dir = Path("projects")
    if projects_dir.exists():
        for proj_json_path in sorted(projects_dir.glob("*/project.json")):
            try:
                proj_meta = json.loads(proj_json_path.read_text(encoding="utf-8"))
                proj_key = proj_meta.get("key", "")
                proj_name = proj_json_path.parent.name
                
                tasks_path = proj_json_path.parent / "tasks.md"
                if tasks_path.exists():
                    tasks_text = tasks_path.read_text(encoding="utf-8")
                    proj_blocked, proj_actionable = parse_tasks_file(tasks_text, proj_key, proj_name)
                    blocked_all.extend(proj_blocked)
                    actionable_all.extend(proj_actionable)
            except Exception as e:
                logger.error(f"プロジェクト {proj_json_path.parent.name} の解析失敗: {e}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "blocked":      blocked_all,
        "actionable":   actionable_all,
        "summary": {
            "blocked_count":    len(set(b["id"] for b in blocked_all)),
            "actionable_count": len(actionable_all),
            "by_type": {
                rule["type"]: len([b for b in blocked_all if b["type"] == rule["type"]])
                for rule in BLOCKER_RULES
            },
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    logger.info(f"blocked={payload['summary']['blocked_count']}  "
                f"actionable={len(actionable_all)} → {out_path}")
    for b in blocked_all:
        proj_str = f"[{b.get('project', 'core')}]"
        logger.info(f"  [{b['type']}] #{b['id']:<8} {proj_str:<12} {b['title'][:30]:<30}  → {b['detail']}")
    logger.info(f"  実行可能: {actionable_all}")


if __name__ == "__main__":
    main()
