#!/usr/bin/env python3
"""
check-blockers.py  ―  Layer 2 / Step 2
roadmap.md を解析し、ブロッカー6分類を正規表現で確定的に検出。
LLM を一切使用しない決定的スクリプト。

使い方:
  python3 tools/check-blockers.py [--roadmap roadmap.md] [--out tools/.cache/blocked.json]
"""

import re
import json
import argparse
import datetime
from pathlib import Path

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
        "patterns":    [r"blockedby:\s*#\d+"],
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
        m = re.match(r"^## \[?#?(\d+)\]?\s+(.+)", block)
        if not m:
            continue
        iid, title = m.group(1), m.group(2).strip()

        # 完了済みは除外
        if re.search(r"status:\s*(done|closed|cancelled)", block, re.IGNORECASE):
            continue

        all_ids.append(iid)
        hits = detect_blockers(iid, title, block)
        if hits:
            blocked_all.extend(hits)
            blocked_ids.add(iid)

    actionable = [i for i in all_ids if i not in blocked_ids]
    return blocked_all, actionable


def main():
    parser = argparse.ArgumentParser(description="ブロッカー判定（Layer 2 / Step 2）")
    parser.add_argument("--roadmap", default="roadmap.md")
    parser.add_argument("--out",     default="tools/.cache/blocked.json")
    args = parser.parse_args()

    roadmap_path = Path(args.roadmap)
    if not roadmap_path.exists():
        print(f"[check-blockers] ERROR: {roadmap_path} が見つかりません")
        raise SystemExit(1)

    text = roadmap_path.read_text(encoding="utf-8")
    blocked, actionable = parse_and_check(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "blocked":      blocked,
        "actionable":   actionable,
        "summary": {
            "blocked_count":    len(set(b["id"] for b in blocked)),
            "actionable_count": len(actionable),
            "by_type": {
                rule["type"]: len([b for b in blocked if b["type"] == rule["type"]])
                for rule in BLOCKER_RULES
            },
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    print(f"[check-blockers] blocked={payload['summary']['blocked_count']}  "
          f"actionable={len(actionable)} → {out_path}")
    for b in blocked:
        print(f"  [{b['type']}] #{b['id']} {b['title'][:40]:<40}  → {b['detail']}")
    print(f"  実行可能: {actionable}")


if __name__ == "__main__":
    main()
