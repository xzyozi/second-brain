"""
test_add_task.py  ―  add-task.py の内部関数のユニットテスト
"""

import pytest


def test_find_parent_line_index(add_task_mod):
    lines = [
        "- [ ] [TFG-001] 親タスクA\n",
        "  - [ ] 子タスクA1\n",
        "- [ ] タスクB\n",
    ]
    # 存在するID
    assert add_task_mod.find_parent_line_index(lines, "TFG-001") == 0
    # 存在しないID
    assert add_task_mod.find_parent_line_index(lines, "TFG-002") == -1


def test_find_insert_position_after_parent(add_task_mod):
    # パターン1: サブタスクがまだ無い場合 -> 親の直後
    lines = [
        "- [ ] [TFG-001] 親タスクA\n",
        "- [ ] タスクB\n",
    ]
    assert add_task_mod.find_insert_position_after_parent(lines, 0) == 1

    # パターン2: 既にサブタスクがある場合 -> 既存サブタスク群の末尾の次
    lines = [
        "- [ ] [TFG-001] 親タスクA\n",
        "  - [ ] 子タスクA1\n",
        "  - [ ] 子タスクA2\n",
        "- [ ] タスクB\n",
    ]
    assert add_task_mod.find_insert_position_after_parent(lines, 0) == 3

    # パターン3: 空行や別のインデント構造
    lines = [
        "- [ ] [TFG-001] 親タスクA\n",
        "  - [ ] 子タスクA1\n",
        "\n",
        "  - [ ] 子タスクA2\n",
        "- [ ] タスクB\n",
    ]
    assert add_task_mod.find_insert_position_after_parent(lines, 0) == 4
