"""
test_record_failure.py  ―  record-failure.py の動作検証テスト
"""

import subprocess
import pytest
from pathlib import Path


def test_record_failure_escape(tmp_path, monkeypatch):
    # record-failure.py のパス
    script_path = Path(__file__).parent.parent / "tools" / "record-failure.py"

    # テスト用の一時フォルダを作成し、カレントディレクトリを移動する（docs/knowledgeの出力先制御）
    monkeypatch.chdir(tmp_path)

    # 実行パラメータ
    agent = "test-agent"
    phase = "test-phase"
    issue = "This is a | test | issue with\nnewline"
    action = "Fix | the | action with\nnewline"

    # スクリプトを呼び出す
    cmd = [
        "uv", "run", "python", str(script_path),
        "--agent", agent,
        "--phase", phase,
        "--issue", issue,
        "--action", action
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # 生成されたマークダウンファイルの存在確認
    failure_file = tmp_path / "docs" / "knowledge" / "failures.md"
    assert failure_file.exists()

    content = failure_file.read_text(encoding="utf-8")

    # パイプおよび改行が適切にエスケープされて1行に収まっているか検証
    assert "This is a \\| test \\| issue with newline" in content
    assert "Fix \\| the \\| action with newline" in content
    assert "test-agent" in content
    assert "test-phase" in content
