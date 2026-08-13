import pytest
from tools.task_parser import parse_comment_metadata, parse_tasks_file, parse_roadmap_file, TaskItem

def test_parse_comment_metadata():
    # 正常ケース
    comment = "priority:high estimate:4h blockedby:#TFG-005 parent:ARCH-001"
    meta = parse_comment_metadata(comment)
    assert meta["priority"] == "high"
    assert meta["estimate"] == "4h"
    assert meta["blockedby"] == ["#TFG-005"]
    assert meta["parent"] == "ARCH-001"

    # 複数 blockedby のケース
    comment_multi = "priority:medium blockedby:#TFG-005 blockedby:#TFG-007"
    meta_multi = parse_comment_metadata(comment_multi)
    assert meta_multi["blockedby"] == ["#TFG-005", "#TFG-007"]

    # カンマ区切り blockedby のケース
    comment_comma = "blockedby:#TFG-005,#TFG-006,#TFG-007"
    meta_comma = parse_comment_metadata(comment_comma)
    assert meta_comma["blockedby"] == ["#TFG-005", "#TFG-006", "#TFG-007"]

def test_parse_tasks_file():
    text = """
- [ ] [TFG-001] タスク1  <!-- priority:high estimate:2h -->
- [/] タスク2  <!-- priority:medium estimate:1d blockedby:#TFG-001 -->
- [x] [TFG-003] タスク3  <!-- priority:low added:2026-07-01 -->
"""
    tasks = parse_tasks_file(text, "TFG", "test_project")
    assert len(tasks) == 3
    
    assert tasks[0].id == "TFG-001"
    assert tasks[0].title == "タスク1"
    assert tasks[0].status == "open"
    assert tasks[0].priority == "high"
    assert tasks[0].estimate == "2h"
    
    assert tasks[1].id == "TFG-1"  # 自動採番
    assert tasks[1].title == "タスク2"
    assert tasks[1].status == "in-progress"
    assert tasks[1].blockedby == ["#TFG-001"]
    
    assert tasks[2].id == "TFG-003"
    assert tasks[2].status == "done"
    assert tasks[2].updated == "2026-07-01"

def test_parse_roadmap_file():
    text = """
## [#TFG-001] ロードマップ1
- status: in-progress
- priority-high
- estimate: 4h
- updated: 2026-07-15
- blockedby: #TFG-000

## [TFG-002] ロードマップ2
- status: open
- priority-medium
- blockedby: #TFG-001,#TFG-003
- parent: [ARCH-001]
"""
    tasks = parse_roadmap_file(text)
    assert len(tasks) == 2
    
    assert tasks[0].id == "TFG-001"
    assert tasks[0].title == "ロードマップ1"
    assert tasks[0].status == "in-progress"
    assert tasks[0].priority == "high"
    assert tasks[0].estimate == "4h"
    assert tasks[0].updated == "2026-07-15"
    assert tasks[0].blockedby == ["TFG-000"]
    
    assert tasks[1].id == "TFG-002"
    assert tasks[1].status == "open"
    assert tasks[1].priority == "medium"
    assert tasks[1].blockedby == ["TFG-001", "TFG-003"]
    assert tasks[1].parent == "ARCH-001"
