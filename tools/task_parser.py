#!/usr/bin/env python3
"""
task_parser.py - tasks.md や roadmap.md のパース処理を共通化・堅牢化するモジュール
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class TaskItem:
    id: str
    title: str
    status: str  # "open" | "in-progress" | "done"
    priority: str = "none"
    estimate: str = ""
    updated: str = ""
    parent: Optional[str] = None
    blockedby: List[str] = field(default_factory=list)
    extra_blockers: List[str] = field(default_factory=list)
    raw_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """従来の辞書フォーマットとの互換性を持つ辞書を返す"""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "estimate": self.estimate,
            "updated": self.updated,
            "parent": self.parent,
            "blockedby": self.blockedby,
            "extra_blockers": self.extra_blockers,
        }

def parse_comment_metadata(comment_content: str) -> Dict[str, Any]:
    """
    タスクコメント (例: priority:high estimate:4h blockedby:#TFG-005) から
    メタデータを堅牢に抽出する。
    """
    meta: Dict[str, Any] = {}
    # キー:値 (値はスペース以外の連続する文字)
    pairs = re.findall(r"(\w+):([^\s]+)", comment_content)
    for k, v in pairs:
        k_lower = k.lower()
        if k_lower == "blockedby":
            if "blockedby" not in meta:
                meta["blockedby"] = []
            # カンマ区切りの場合も分解して取り込む
            for item in v.split(","):
                item_clean = item.strip()
                if item_clean:
                    meta["blockedby"].append(item_clean)
        else:
            meta[k_lower] = v
    return meta

def parse_tasks_file(text: str, project_key: str, project_name: str) -> List[TaskItem]:
    """
    tasks.md 形式のテキストをパースして TaskItem のリストを返す
    """
    tasks = []
    task_index = 1
    lines = text.splitlines()

    for line in lines:
        m_task = re.match(r"^\s*-\s*\[([ x/])\]\s+(.*)", line)
        if not m_task:
            continue
        
        status_char = m_task.group(1)
        rest = m_task.group(2).strip()

        # 完了状態の文字列判定
        if status_char == "x":
            status = "done"
        elif status_char == "/":
            status = "in-progress"
        else:
            status = "open"

        # コメント部分 (<!-- ... -->) の抽出
        m_comment = re.search(r"<!--\s*(.*?)\s*-->", rest)
        comment_content = ""
        if m_comment:
            comment_content = m_comment.group(1)
            title_part = rest[:m_comment.start()].strip()
        else:
            title_part = rest

        # メタデータ抽出
        priority = "none"
        estimate = ""
        updated = ""
        blockedby = []
        parent = None
        extra_blockers = []

        if comment_content:
            meta = parse_comment_metadata(comment_content)
            priority = meta.get("priority", "none")
            estimate = meta.get("estimate", "")
            updated = meta.get("updated", meta.get("added", ""))
            blockedby = meta.get("blockedby", [])
            parent = meta.get("parent")

            # 各種ブロッカーワードの抽出
            for kw in ["仕様未確定", "要確認", "TBD", "spec?", "unclear", "not defined",
                       "waiting", "review", "external", "vendor", "resource", "予算未確定"]:
                if kw in comment_content:
                    extra_blockers.append(kw)

        # タイトルから [KEY-123] 形式のID抽出を試みる
        m_id = re.match(r"^\[?([A-Z0-9\-]+)\]?\s*(.*)", title_part)
        if m_id:
            iid = m_id.group(1)
            title = m_id.group(2).strip()
        else:
            iid = f"{project_key}-{task_index}"
            title = title_part
            task_index += 1

        tasks.append(TaskItem(
            id=iid,
            title=title,
            status=status,
            priority=priority,
            estimate=estimate,
            updated=updated,
            parent=parent,
            blockedby=blockedby,
            extra_blockers=extra_blockers,
            raw_content=line
        ))

    return tasks

def parse_roadmap_file(text: str) -> List[TaskItem]:
    """
    roadmap.md 形式のテキストをパースして TaskItem のリストを返す
    """
    tasks = []
    # ## [#N] または ## #N または ## N のいずれにも対応
    blocks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    for block in blocks:
        m = re.match(r"^## \[?#?([A-Z0-9\-]+)\]?\s+(.+)", block)
        if not m:
            continue
        iid, title = m.group(1), m.group(2).strip()

        # ステータス判定
        m_status = re.search(r"status:\s*([a-zA-Z\-]+)", block, re.IGNORECASE)
        status = m_status.group(1).lower() if m_status else "open"

        # 優先度
        p_match = re.search(r"priority[:\-](\w+)", block, re.IGNORECASE)
        priority = p_match.group(1).lower() if p_match else "none"

        # 工数
        m_e = re.search(r"estimate:\s*([^\s]+)", block, re.IGNORECASE)
        estimate = m_e.group(1) if m_e else ""

        # 日付
        m_u = re.search(r"updated:\s*([\d\-]+)", block, re.IGNORECASE)
        updated = m_u.group(1) if m_u else ""

        # 依存
        blockedby_matches = re.findall(r"blockedby:\s*([^\s]+)", block, re.IGNORECASE)
        blockedby = []
        for b in blockedby_matches:
            # カンマ区切りの可能性も考慮
            for item in b.split(","):
                item_clean = item.strip("#[] ")
                if item_clean:
                    blockedby.append(item_clean)

        # 親タスク
        m_parent = re.search(r"parent:\s*([^\s]+)", block, re.IGNORECASE)
        parent = m_parent.group(1).strip("[]") if m_parent else None

        # ブロッカーワード
        extra_blockers = []
        for kw in ["仕様未確定", "要確認", "TBD", "spec?", "unclear", "not defined",
                   "waiting", "review", "external", "vendor", "resource", "予算未確定"]:
            if re.search(rf"\b{re.escape(kw)}\b|{re.escape(kw)}", block, re.IGNORECASE):
                extra_blockers.append(kw)

        tasks.append(TaskItem(
            id=iid,
            title=title,
            status=status,
            priority=priority,
            estimate=estimate,
            updated=updated,
            parent=parent,
            blockedby=blockedby,
            extra_blockers=extra_blockers,
            raw_content=block
        ))

    return tasks
