#!/usr/bin/env python3
"""
score-issues.py  ―  Layer 2 / Step 1
roadmap.md を解析し、4軸スコアを計算して priority-cache.json に書き出す。
LLM を一切使用しない決定的スクリプト。

使い方:
  python3 tools/score-issues.py [--roadmap roadmap.md] [--out tools/.cache/priority-cache.json]
"""

import re
import json
import argparse
import datetime
from pathlib import Path

# ── スコア重み ──────────────────────────────────────────────────
WEIGHTS = {"P": 3.0, "F": 2.0, "E": 1.5, "D": 2.0}
MAX_SCORE = sum(5 * w for w in WEIGHTS.values())   # 42.5

# ── 優先度ラベル → 数値 ──────────────────────────────────────────
PRIORITY_MAP = {
    "critical": 5, "urgent": 5,
    "high":     4,
    "medium":   3, "med": 3,
    "low":      2,
    "none":     1,
}

# ── 工数見積もり → h 換算 ─────────────────────────────────────────
def parse_effort_hours(block: str) -> float:
    """estimate: 2h / 1d / 30m などを時間に変換する"""
    m = re.search(r"estimate:\s*(\d+(?:\.\d+)?)\s*([mhd])", block, re.IGNORECASE)
    if not m:
        return 8.0   # デフォルト1日
    val, unit = float(m.group(1)), m.group(2).lower()
    if unit == "m":  return val / 60
    if unit == "h":  return val
    if unit == "d":  return val * 8
    return 8.0

def effort_score(hours: float) -> int:
    if hours <= 1:   return 5
    if hours <= 4:   return 4
    if hours <= 8:   return 3
    if hours <= 16:  return 2
    return 1

# ── 鮮度スコア ───────────────────────────────────────────────────
def freshness_score(block: str) -> int:
    m = re.search(r"updated:\s*(\d{4}-\d{2}-\d{2})", block)
    if not m:
        return 1   # 日付なし → 陳腐と見なす
    days = (datetime.date.today() - datetime.date.fromisoformat(m.group(1))).days
    if days <= 7:   return 5
    if days <= 30:  return 3
    if days <= 90:  return 1
    return 0

# ── 依存スコア ───────────────────────────────────────────────────
def dependency_score(block: str) -> int:
    deps = len(re.findall(r"blockedby:\s*#\d+", block, re.IGNORECASE))
    if deps == 0: return 5
    if deps == 1: return 3
    if deps == 2: return 1
    return 0

# ── Issueパーサ ──────────────────────────────────────────────────
def parse_issues(text: str) -> list[dict]:
    """
    roadmap.md のフォーマット想定:
      ## [#12] タイトル
      - priority-high
      - estimate: 4h
      - updated: 2026-06-20
      - blockedby: #8
    """
    issues = []
    # ## [#N] または ## #N または ## N のいずれにも対応
    blocks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for block in blocks:
        m = re.match(r"^## \[?#?(\d+)\]?\s+(.+)", block)
        if not m:
            continue
        iid, title = m.group(1), m.group(2).strip()

        # 完了済みはスキップ
        if re.search(r"status:\s*(done|closed|cancelled)", block, re.IGNORECASE):
            continue

        # 優先度
        p_match = re.search(r"priority[:\-](\w+)", block, re.IGNORECASE)
        p_label = p_match.group(1).lower() if p_match else "none"
        P = PRIORITY_MAP.get(p_label, 1)

        F = freshness_score(block)
        E = effort_score(parse_effort_hours(block))
        D = dependency_score(block)

        total    = P * WEIGHTS["P"] + F * WEIGHTS["F"] + E * WEIGHTS["E"] + D * WEIGHTS["D"]
        score    = round(total / MAX_SCORE * 100, 1)

        # タグ抽出（任意）
        tags = re.findall(r"#(\w+)", block)
        tags = [t for t in tags if not t.isdigit()]

        issues.append({
            "id":    iid,
            "title": title,
            "score": score,
            "axes":  {"P": P, "F": F, "E": E, "D": D},
            "raw_total": round(total, 2),
            "tags":  tags[:5],
        })

    issues.sort(key=lambda x: x["score"], reverse=True)
    return issues


def main():
    parser = argparse.ArgumentParser(description="Issue スコアリング（Layer 2 / Step 1）")
    parser.add_argument("--roadmap", default="roadmap.md")
    parser.add_argument("--out",     default="tools/.cache/priority-cache.json")
    args = parser.parse_args()

    roadmap_path = Path(args.roadmap)
    if not roadmap_path.exists():
        print(f"[score-issues] ERROR: {roadmap_path} が見つかりません")
        raise SystemExit(1)

    text   = roadmap_path.read_text(encoding="utf-8")
    issues = parse_issues(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total":        len(issues),
        "issues":       issues,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    print(f"[score-issues] {len(issues)} issues scored → {out_path}")
    for i in issues[:5]:
        axes = i["axes"]
        print(f"  #{i['id']:>4}  score={i['score']:>5}  "
              f"P={axes['P']} F={axes['F']} E={axes['E']} D={axes['D']}  {i['title'][:45]}")


if __name__ == "__main__":
    main()
