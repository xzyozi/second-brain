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


def test_add_task_cli_brackets(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path

    script_path = Path(__file__).parent.parent / "tools" / "add-task.py"
    monkeypatch.chdir(tmp_path)

    # 1. 親タスクが書き込まれたダミーの tasks.md を配置する
    project_dir = tmp_path / "projects" / "test_proj"
    project_dir.mkdir(parents=True, exist_ok=True)
    tasks_md = project_dir / "tasks.md"
    tasks_md.write_text(
        "# タスクリスト\n\n## 未着手\n- [ ] [TFG-001] 親タスク\n\n## 進行中\n\n## 完了\n",
        encoding="utf-8"
    )

    # 2. 括弧付きの ID `--parent [TFG-001]` を指定して実行
    cmd = [
        "uv", "run", "python", str(script_path),
        "projects/test_proj",
        "サブタスク内容",
        "--parent", "[TFG-001]",
        "--priority", "high"
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    # 3. 親タスクの直下に正しく挿入されたか確認
    updated_content = tasks_md.read_text(encoding="utf-8")
    assert "  - [ ] サブタスク内容" in updated_content
    assert "parent:TFG-001" in updated_content  # メタデータ内でも括弧が除去されて normalized されていること

