#!/usr/bin/env python3
"""
score-issues.py  ―  Layer 2 / Step 1
roadmap.md を解析し、4軸スコアを計算して priority-cache.json に書き出す。
LLM を一切使用しない決定的スクリプト。

使い方:
  uv run python tools/score-issues.py [--roadmap roadmap.md] [--out tools/.cache/priority-cache.json]
"""

import re
import json
import argparse
import datetime
import sys
from pathlib import Path
import os
import logging

# loggerの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("score-issues")

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
    deps = len(re.findall(r"blockedby:\s*#?[A-Z0-9\-]+", block, re.IGNORECASE))
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
        m = re.match(r"^## \[?#?([A-Z0-9\-]+)\]?\s+(.+)", block)
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


def parse_tasks_file(text: str, project_key: str, project_name: str) -> list[dict]:
    """
    tasks.md のフォーマット想定:
      - [ ] [EC-001] タイトル  <!-- priority:high estimate:4h added:2026-06-27 -->
      - [/] タイトル  <!-- priority:medium estimate:2h added:2026-06-26 blockedby:#8 -->
    """
    issues = []
    task_index = 1
    lines = text.splitlines()

    for line in lines:
        m_task = re.match(r"^\s*-\s*\[([ x/])\]\s+(.*)", line)
        if not m_task:
            continue
        
        status_char = m_task.group(1)
        rest = m_task.group(2).strip()

        # 完了済みはスキップ
        if status_char == "x":
            continue
        
        status = "in-progress" if status_char == "/" else "open"

        # コメント部分 (<!-- ... -->) の抽出
        m_comment = re.search(r"<!--\s*(.*?)\s*-->", rest)
        comment_content = ""
        if m_comment:
            comment_content = m_comment.group(1)
            title_part = rest[:m_comment.start()].strip()
        else:
            title_part = rest

        # メタデータのデフォルト値
        priority = "none"
        estimate = ""
        updated = ""
        extra_lines = []

        if comment_content:
            m_p = re.search(r"priority:(\w+)", comment_content)
            if m_p:
                priority = m_p.group(1)
            
            m_e = re.search(r"estimate:([^\s]+)", comment_content)
            if m_e:
                estimate = m_e.group(1)
            
            m_a = re.search(r"added:([\d\-]+)", comment_content)
            if m_a:
                updated = m_a.group(1)
            
            m_u = re.search(r"updated:([\d\-]+)", comment_content)
            if m_u:
                updated = m_u.group(1)
            
            m_b = re.search(r"blockedby:([^\s]+)", comment_content)
            if m_b:
                extra_lines.append(f"- blockedby: {m_b.group(1)}")

            # 親タスクID の抽出
            m_parent = re.search(r"parent:([^\s]+)", comment_content)

            # 各種ブロッカーワードの透過的転送
            for kw in ["仕様未確定", "要確認", "TBD", "spec?", "unclear", "not defined",
                       "waiting", "review", "external", "vendor", "resource", "予算未確定"]:
                if kw in comment_content:
                    extra_lines.append(f"- {kw}: info")

        # タイトルから [KEY-123] 形式のID抽出を試みる
        m_id = re.match(r"^\[?([A-Z0-9\-]+)\]?\s*(.*)", title_part)
        if m_id:
            iid = m_id.group(1)
            title = m_id.group(2).strip()
        else:
            iid = f"{project_key}-{task_index}"
            title = title_part
            task_index += 1

        # 既存のパース・評価ロジックを再利用するため、一時的にロードマップ形式のブロックテキストに変換
        block_text = f"## [{iid}] {title}\n"
        block_text += f"- status: {status}\n"
        block_text += f"- priority-{priority}\n"
        if estimate:
            block_text += f"- estimate: {estimate}\n"
        if updated:
            block_text += f"- updated: {updated}\n"
        for extra in extra_lines:
            block_text += f"{extra}\n"

        # 共通の解析ロジックを走らせるため、この1ブロックを parse_issues に渡す
        parsed_list = parse_issues(block_text)
        if parsed_list:
            item = parsed_list[0]
            item["project"] = project_name
            # 親タスクIDがあればバインド
            if m_parent:
                item["parent"] = m_parent.group(1)
            issues.append(item)

    return issues


def main():
    parser = argparse.ArgumentParser(description="Issue スコアリング（Layer 2 / Step 1）")
    parser.add_argument("--roadmap", default="roadmap.md")
    parser.add_argument("--out",     default="tools/.cache/priority-cache.json")
    args = parser.parse_args()

    all_issues = []

    # 1. 母艦 roadmap.md のパース
    roadmap_path = Path(args.roadmap)
    if roadmap_path.exists():
        text = roadmap_path.read_text(encoding="utf-8")
        issues = parse_issues(text)
        for i in issues:
            i["project"] = "core"
        all_issues.extend(issues)
    else:
        logger.warning(f"roadmap.md が見つかりません: {roadmap_path}")

    # 2. 衛星プロジェクトのパース
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
                    proj_issues = parse_tasks_file(tasks_text, proj_key, proj_name)
                    all_issues.extend(proj_issues)
            except Exception as e:
                logger.error(f"プロジェクト {proj_json_path.parent.name} の解析失敗: {e}")

    # 全プロジェクト横断でソート
    all_issues.sort(key=lambda x: x["score"], reverse=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total":        len(all_issues),
        "issues":       all_issues,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    logger.info(f"{len(all_issues)} issues scored → {out_path}")
    for i in all_issues[:10]:
        axes = i["axes"]
        proj_str = f"[{i['project']}]"
        logger.info(f"  #{i['id']:<8} {proj_str:<12} score={i['score']:>5}  "
                    f"P={axes['P']} F={axes['F']} E={axes['E']} D={axes['D']}  {i['title'][:40]}")


if __name__ == "__main__":
    main()
