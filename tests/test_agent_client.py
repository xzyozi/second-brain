#!/usr/bin/env python3
"""
test_agent_client.py - AgentClientのテスト
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess
import sys
import json

# tools/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.agent_client import (
    AgentClient,
    AgentResponse,
    AgentCallError,
    ResponseParseError
)


class TestAgentResponse:
    """AgentResponseデータクラスのテスト"""

    def test_agent_response_creation(self):
        """AgentResponse作成テスト"""
        response = AgentResponse(
            raw_output="Test output",
            parsed_data={"key": "value"},
            success=True,
            error_message=None,
            execution_time=1.5,
            agent_name="executor",
            timestamp="2026-07-06T12:00:00"
        )

        assert response.raw_output == "Test output"
        assert response.parsed_data["key"] == "value"
        assert response.success is True
        assert response.execution_time == 1.5
        assert response.agent_name == "executor"


class TestAgentClient:
    """AgentClientのテスト"""

    def test_initialization(self):
        """初期化テスト"""
        client = AgentClient(timeout=120, opencode_bin="opencode")
        assert client.timeout == 120
        assert client.opencode_bin == "opencode"
        assert len(client.call_history) == 0

    def test_initialization_defaults(self):
        """デフォルト値での初期化テスト"""
        client = AgentClient()
        assert client.timeout == 300
        assert client.opencode_bin == "opencode"

    @patch('subprocess.run')
    def test_call_agent_success(self, mock_run):
        """エージェント呼び出し成功テスト"""
        # subprocess.runのモック設定
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""
## 実装指示書

以下のファイルを作成してください:
- tools/example.py
""",
            stderr=""
        )

        client = AgentClient()
        response = client.call_agent("executor", "Issue ARCH-001を実装")

        assert response.success is True
        assert response.agent_name == "executor"
        assert "implementation_plan" in response.parsed_data
        assert len(client.call_history) == 1

    @patch('subprocess.run')
    def test_call_agent_with_context(self, mock_run):
        """コンテキスト付きエージェント呼び出しテスト"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="## 実装指示書\n\nテスト",
            stderr=""
        )

        client = AgentClient()
        context_summary = "Issue: ARCH-001\n要件: テスト実装"

        response = client.call_agent(
            "executor",
            "実装してください",
            context_summary=context_summary
        )

        assert response.success is True
        # subprocess.runが呼ばれたことを確認
        assert mock_run.called

    @patch('subprocess.run')
    def test_call_agent_timeout(self, mock_run):
        """タイムアウトエラーのテスト"""
        mock_run.side_effect = subprocess.TimeoutExpired("opencode", 300)

        client = AgentClient(timeout=1)

        with pytest.raises(AgentCallError, match="タイムアウト"):
            client.call_agent("executor", "テストプロンプト", max_retries=1)

    @patch('subprocess.run')
    def test_call_agent_retry_on_failure(self, mock_run):
        """リトライ機能のテスト"""
        # 1回目: 失敗、2回目: 成功
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "opencode"),
            MagicMock(
                returncode=0,
                stdout="## 実装指示書\n\nテスト",
                stderr=""
            )
        ]

        client = AgentClient()
        response = client.call_agent("executor", "テスト", max_retries=3)

        assert response.success is True
        assert mock_run.call_count == 2  # 1回目失敗、2回目成功

    @patch('subprocess.run')
    def test_call_agent_max_retries_exceeded(self, mock_run):
        """最大リトライ回数超過のテスト"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "opencode")

        client = AgentClient()

        with pytest.raises(AgentCallError, match="呼び出しに失敗しました"):
            client.call_agent("executor", "テスト", max_retries=2)

        assert mock_run.call_count == 2

    def test_parse_response_executor(self):
        """Executor応答のパーステスト"""
        client = AgentClient()

        raw_output = """
# エージェント応答

## 実装指示書

以下のファイルを作成してください:
- [ ] 新規作成: tools/example.py - 例示機能
- [ ] 編集: tests/test_example.py - テスト追加

### 実装詳細
example関数を実装します。
"""

        parsed = client._parse_response(raw_output, "executor")

        assert "implementation_plan" in parsed
        assert "example関数" in parsed["implementation_plan"]
        assert "files_mentioned" in parsed
        assert len(parsed["files_mentioned"]) > 0

    def test_parse_response_coder(self):
        """Coder応答のパーステスト"""
        client = AgentClient()

        raw_output = """
# コード生成結果

```python
# filepath: tools/example.py
def example():
    print("Hello")
```

```python
# filepath: tests/test_example.py
def test_example():
    assert True
```
"""

        parsed = client._parse_response(raw_output, "coder")

        assert "code_blocks" in parsed
        assert len(parsed["code_blocks"]) == 2
        assert "generated_files" in parsed
        assert "tools/example.py" in parsed["generated_files"]
        assert "tests/test_example.py" in parsed["generated_files"]

    def test_parse_response_with_error(self):
        """エラー含む応答のパーステスト"""
        client = AgentClient()

        raw_output = """
処理中...
ERROR: ファイルが見つかりません
ERROR: 処理を中断しました
"""

        parsed = client._parse_response(raw_output, "executor")

        assert "error" in parsed
        assert "ファイルが見つかりません" in parsed["error"]

    def test_parse_executor_response_no_section(self):
        """実装指示書セクションがない場合のテスト"""
        client = AgentClient()

        raw_output = "単なるテキスト応答です。"

        parsed = client._parse_executor_response(raw_output)

        assert "implementation_plan" in parsed
        # フォールバック: 先頭1000文字
        assert len(parsed["implementation_plan"]) > 0
        assert parsed["files_mentioned"] == []

    def test_parse_coder_response_no_code_blocks(self):
        """コードブロックがない場合のテスト"""
        client = AgentClient()

        raw_output = "コードは生成できませんでした。"

        parsed = client._parse_coder_response(raw_output)

        assert "code_blocks" in parsed
        assert len(parsed["code_blocks"]) == 0
        assert "generated_files" in parsed
        assert len(parsed["generated_files"]) == 0

    def test_extract_markdown_sections(self):
        """Markdownセクション抽出テスト"""
        client = AgentClient()

        text = """
# ヘッダー1
内容1

## ヘッダー2
内容2

### ヘッダー3
内容3
"""

        sections = client._extract_markdown_sections(text)

        assert "ヘッダー1" in sections
        assert "ヘッダー2" in sections
        assert "ヘッダー3" in sections
        assert "内容1" in sections["ヘッダー1"]

    def test_extract_code_blocks(self):
        """コードブロック抽出テスト"""
        client = AgentClient()

        text = """
```python
def hello():
    print("Hello")
```

```javascript
console.log("test");
```

```
plain text
```
"""

        code_blocks = client._extract_code_blocks(text)

        assert len(code_blocks) == 3
        assert code_blocks[0]["language"] == "python"
        assert code_blocks[1]["language"] == "javascript"
        assert code_blocks[2]["language"] == "text"
        assert "def hello" in code_blocks[0]["code"]

    def test_validate_response_executor_valid(self):
        """Executor応答の検証（有効）テスト"""
        client = AgentClient()

        parsed_data = {
            "implementation_plan": "有効な実装指示書",
            "files_mentioned": ["test.py"]
        }

        assert client._validate_response(parsed_data, "executor") is True

    def test_validate_response_executor_invalid(self):
        """Executor応答の検証（無効）テスト"""
        client = AgentClient()

        # 実装指示書が空
        parsed_data = {
            "implementation_plan": "",
            "files_mentioned": []
        }

        assert client._validate_response(parsed_data, "executor") is False

    def test_validate_response_coder_valid(self):
        """Coder応答の検証（有効）テスト"""
        client = AgentClient()

        parsed_data = {
            "code_blocks": ["def test(): pass"],
            "generated_files": {"test.py": "code"}
        }

        assert client._validate_response(parsed_data, "coder") is True

    def test_validate_response_coder_invalid(self):
        """Coder応答の検証（無効）テスト"""
        client = AgentClient()

        # コードブロックが空
        parsed_data = {
            "code_blocks": [],
            "generated_files": {}
        }

        assert client._validate_response(parsed_data, "coder") is False

    def test_validate_response_with_error(self):
        """エラー含む応答の検証テスト"""
        client = AgentClient()

        parsed_data = {
            "error": "エラーが発生しました",
            "implementation_plan": "内容"
        }

        assert client._validate_response(parsed_data, "executor") is False

    def test_get_call_history(self):
        """呼び出し履歴取得テスト"""
        client = AgentClient()
        client.call_history = [
            {"agent_name": "executor", "success": True},
            {"agent_name": "coder", "success": True}
        ]

        history = client.get_call_history()
        assert len(history) == 2
        assert history[0]["agent_name"] == "executor"

    def test_save_call_history(self, tmp_path):
        """呼び出し履歴保存テスト"""
        client = AgentClient()
        client.call_history = [
            {"agent_name": "executor", "attempt": 1, "success": True}
        ]

        filepath = tmp_path / "history.json"
        client.save_call_history(filepath)

        assert filepath.exists()
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["agent_name"] == "executor"


class TestAgentCallError:
    """AgentCallErrorのテスト"""

    def test_agent_call_error_creation(self):
        """AgentCallError作成テスト"""
        error = AgentCallError("エージェント呼び出しに失敗しました")
        assert "エージェント呼び出し" in str(error)


class TestResponseParseError:
    """ResponseParseErrorのテスト"""

    def test_response_parse_error_creation(self):
        """ResponseParseError作成テスト"""
        error = ResponseParseError("応答のパースに失敗しました")
        assert "パース" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
