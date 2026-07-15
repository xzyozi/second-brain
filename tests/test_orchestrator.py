#!/usr/bin/env python3
"""
test_orchestrator.py - IssueOrchestratorのテスト
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# tools/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.orchestrator import (
    IssueOrchestrator,
    Requirements,
    Constraints,
    ImplementationPlan,
    GeneratedCode,
    TestResult,
    ExecutionResult,
    OrchestratorError,
    AgentCallError,
    ConstraintViolationError,
    TestFailureError
)


class TestRequirements:
    """Requirementsデータクラスのテスト"""

    def test_requirements_creation(self):
        """Requirements作成テスト"""
        req = Requirements(
            issue_id="ARCH-001",
            title="テストIssue",
            description="テスト説明",
            project_path=Path("."),
            related_files=[Path("test.py")],
            priority="high"
        )

        assert req.issue_id == "ARCH-001"
        assert req.title == "テストIssue"
        assert req.priority == "high"
        assert req.parent_id is None


class TestConstraints:
    """Constraintsデータクラスのテスト"""

    def test_constraints_creation(self):
        """Constraints作成テスト"""
        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys", "os"],
            file_encoding="utf-8",
            line_ending="LF",
            cooldown_days=3
        )

        assert constraints.external_modules_forbidden is True
        assert len(constraints.allowed_imports) == 2
        assert constraints.file_encoding == "utf-8"

    def test_constraints_defaults(self):
        """Constraintsデフォルト値テスト"""
        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=[]
        )

        assert constraints.file_encoding == "utf-8"
        assert constraints.line_ending == "LF"
        assert constraints.cooldown_days == 3


class TestIssueOrchestrator:
    """IssueOrchestratorのテスト"""

    def test_initialization(self, tmp_path):
        """初期化テスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        assert orchestrator.root_dir == tmp_path

    def test_gather_requirements_no_tasks_file(self, tmp_path):
        """tasks.mdが存在しない場合のエラーテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with pytest.raises(OrchestratorError, match="tasks.md が見つかりません"):
            orchestrator._gather_requirements("ARCH-001")

    def test_gather_requirements_success(self, tmp_path):
        """要件収集の成功テスト"""
        # tasks.md を作成
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
# タスクリスト

## 未着手
- [ ] [ARCH-001] Pythonオーケストレーター実装  <!-- priority:critical -->
- [ ] [ARCH-002] 別のタスク  <!-- priority:high -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        requirements = orchestrator._gather_requirements("ARCH-001")

        assert requirements.issue_id == "ARCH-001"
        assert "Pythonオーケストレーター実装" in requirements.title
        assert requirements.priority == "critical"
        assert requirements.project_path == tmp_path

    def test_gather_requirements_issue_not_found(self, tmp_path):
        """存在しないIssue IDのエラーテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("# タスクリスト\n\n- [ ] [ARCH-001] テスト", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with pytest.raises(OrchestratorError, match="が tasks.md に見つかりません"):
            orchestrator._gather_requirements("NONEXISTENT-999")

    def test_gather_requirements_with_parent_and_blockedby_ok(self, tmp_path):
        """parent_idおよび完了済みのblockedby依存関係を持つ要件収集のテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
# タスクリスト
- [x] [ARCH-001] 先行タスク  <!-- priority:high -->
- [ ] [ARCH-002] 後続タスク  <!-- priority:medium parent:ARCH-003 blockedby:#ARCH-001 -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        requirements = orchestrator._gather_requirements("ARCH-002")

        assert requirements.issue_id == "ARCH-002"
        assert requirements.parent_id == "ARCH-003"

    def test_gather_requirements_blockedby_incomplete(self, tmp_path):
        """未完了のblockedby依存関係がある場合にエラーとなるテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
# タスクリスト
- [ ] [ARCH-001] 先行タスク（未完了）  <!-- priority:high -->
- [ ] [ARCH-002] 後続タスク  <!-- priority:medium blockedby:#ARCH-001 -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with pytest.raises(OrchestratorError, match="is blocked by incomplete dependency: ARCH-001"):
            orchestrator._gather_requirements("ARCH-002")

    def test_gather_requirements_multiple_blockedby_incomplete(self, tmp_path):
        """複数のblockedbyのうち、1つでも未完了のものがあればエラーになるテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
# タスクリスト
- [x] [ARCH-001] 先行タスクA（完了）  <!-- priority:high -->
- [ ] [ARCH-002] 先行タスクB（未完了）  <!-- priority:high -->
- [ ] [ARCH-003] 後続タスク  <!-- priority:medium blockedby:#ARCH-001 blockedby:#ARCH-002 -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with pytest.raises(OrchestratorError, match="is blocked by incomplete dependency: ARCH-002"):
            orchestrator._gather_requirements("ARCH-003")

    def test_gather_requirements_multiple_blockedby_ok(self, tmp_path):
        """複数のblockedbyがすべて完了している場合は正常に動作するテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
# タスクリスト
- [x] [ARCH-001] 先行タスクA（完了）  <!-- priority:high -->
- [x] [ARCH-002] 先行タスクB（完了）  <!-- priority:high -->
- [ ] [ARCH-003] 後続タスク  <!-- priority:medium blockedby:#ARCH-001 blockedby:#ARCH-002 -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        requirements = orchestrator._gather_requirements("ARCH-003")

        assert requirements.issue_id == "ARCH-003"

    def test_verify_constraints(self, tmp_path):
        """制約検証テスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        requirements = Requirements(
            issue_id="ARCH-001",
            title="テスト",
            description="説明",
            project_path=tmp_path,
            related_files=[],
            priority="high"
        )

        constraints = orchestrator._verify_constraints(requirements)

        assert isinstance(constraints, Constraints)
        assert constraints.file_encoding == "utf-8"
        assert constraints.line_ending == "LF"
        assert isinstance(constraints.allowed_imports, list)

    @patch('tools.agent_client.AgentClient.call_agent')
    def test_generate_implementation_plan(self, mock_call_agent, tmp_path):
        """実装指示書生成テスト"""
        # モックの設定
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.parsed_data = {
            "implementation_plan": "テスト実装指示書内容",
            "files_mentioned": ["tools/example.py"]
        }
        mock_call_agent.return_value = mock_response

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        requirements = Requirements(
            issue_id="ARCH-001",
            title="テスト",
            description="説明",
            project_path=tmp_path,
            related_files=[],
            priority="high"
        )
        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=["sys"]
        )

        impl_plan = orchestrator._generate_implementation_plan(requirements, constraints)

        assert isinstance(impl_plan, ImplementationPlan)
        assert impl_plan.content == "テスト実装指示書内容"
        assert len(impl_plan.files_to_create) == 1
        assert impl_plan.files_to_create[0] == Path("tools/example.py")

    @patch('tools.agent_client.AgentClient.call_agent')
    def test_generate_code(self, mock_call_agent, tmp_path):
        """コード生成テスト"""
        # モックの設定
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.parsed_data = {
            "generated_files": {
                "tools/example.py": "# Code content"
            }
        }
        mock_call_agent.return_value = mock_response

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        impl_plan = ImplementationPlan(
            content="テスト指示書",
            files_to_create=[Path("test.py")],
            files_to_edit=[],
            test_strategy="pytest"
        )
        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=["sys"]
        )

        generated_code = orchestrator._generate_code(impl_plan, constraints)

        assert isinstance(generated_code, GeneratedCode)
        assert isinstance(generated_code.files, dict)
        assert "tools/example.py" in generated_code.files

    def test_write_files(self, tmp_path):
        """ファイル書き込みテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        generated_code = GeneratedCode(
            files={
                str(tmp_path / "test1.py"): "# Test file 1\nprint('test1')\n",
                str(tmp_path / "subdir" / "test2.py"): "# Test file 2\nprint('test2')\n"
            },
            metadata={}
        )

        written_files = orchestrator._write_files(tmp_path, generated_code)

        assert len(written_files) == 2
        assert (tmp_path / "test1.py").exists()
        assert (tmp_path / "subdir" / "test2.py").exists()

        # 内容確認
        content1 = (tmp_path / "test1.py").read_text(encoding="utf-8")
        assert "Test file 1" in content1

    def test_run_tests_success(self, tmp_path):
        """テスト実行成功のテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with patch('subprocess.run') as mock_run:
            # pytestが成功するケース
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="5 passed in 0.5s\n",
                stderr=""
            )

            test_result = orchestrator._run_tests(tmp_path, [])

            assert test_result.passed is True
            assert test_result.failed_tests == 0
            assert test_result.error_log == ""

    def test_run_tests_failure(self, tmp_path):
        """テスト実行失敗のテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with patch('subprocess.run') as mock_run:
            # pytestが失敗するケース
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="3 passed, 2 failed\n",
                stderr="AssertionError: test failed\n"
            )

            test_result = orchestrator._run_tests(tmp_path, [])

            assert test_result.passed is False
            assert test_result.failed_tests == 1
            assert "AssertionError" in test_result.error_log

    def test_run_tests_timeout(self, tmp_path):
        """テストタイムアウトのテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("pytest", 120)

            test_result = orchestrator._run_tests(tmp_path, [])

            assert test_result.passed is False
            assert "timeout" in test_result.error_log.lower()

    @patch('tools.agent_client.AgentClient.call_agent')
    def test_execute_issue_dry_run(self, mock_call_agent, tmp_path):
        """Issue実行（ドライラン）テスト"""
        # tasks.md を準備
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
- [ ] [TEST-001] テストIssue  <!-- priority:high -->
""", encoding="utf-8")

        # モックの設定
        mock_response_executor = MagicMock()
        mock_response_executor.success = True
        mock_response_executor.parsed_data = {
            "implementation_plan": "テスト実装指示書内容",
            "files_mentioned": ["tools/example.py"]
        }
        
        mock_response_coder = MagicMock()
        mock_response_coder.success = True
        mock_response_coder.parsed_data = {
            "generated_files": {
                "tools/example.py": "# Code content"
            }
        }
        
        mock_call_agent.side_effect = [mock_response_executor, mock_response_coder]

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        result = orchestrator.execute_issue("TEST-001", dry_run=True)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.issue_id == "TEST-001"
        assert result.context_data["mode"] == "dry_run"
        assert result.test_result is None

    @patch('tools.agent_client.AgentClient.call_agent')
    def test_execute_issue_with_test_failure(self, mock_call_agent, tmp_path):
        """テスト失敗時のIssue実行テスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""
- [ ] [TEST-002] テストIssue  <!-- priority:high -->
""", encoding="utf-8")

        # モックの設定
        mock_response_executor = MagicMock()
        mock_response_executor.success = True
        mock_response_executor.parsed_data = {
            "implementation_plan": "テスト実装指示書内容",
            "files_mentioned": ["tools/example.py"]
        }
        
        mock_response_coder = MagicMock()
        mock_response_coder.success = True
        mock_response_coder.parsed_data = {
            "generated_files": {
                "tools/example.py": "# Code content"
            }
        }
        
        mock_call_agent.side_effect = [mock_response_executor, mock_response_coder]

        orchestrator = IssueOrchestrator(root_dir=tmp_path)

        # テストが失敗するようにモック
        with patch.object(orchestrator, '_run_tests') as mock_test:
            mock_test.return_value = TestResult(
                passed=False,
                total_tests=5,
                failed_tests=2,
                error_log="Test failed",
                duration=1.0
            )

            result = orchestrator.execute_issue("TEST-002", dry_run=False)

            assert result.success is False
            assert result.error_log is not None
            assert "Test failed" in str(result.error_log) or "TestFailureError" in str(result.error_log)

    def test_merge_python_code(self, tmp_path):
        """ASTマージ機能のテスト"""
        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        
        # 既存コード (GrepEngineなどが定義されている)
        existing_code = """import os
import sys

class GrepResult:
    def __init__(self, file_path):
        self.file_path = file_path

class GrepEngine:
    def search(self):
        return 0
"""

        # Coderから返ってきた新規コード (別のSearchEngineのみ定義、GrepEngineなどが消失)
        new_code = """import os
from another_lib import Parser

class SearchEngine:
    def execute(self):
        pass
"""

        # マージを実行
        merged_code = orchestrator._merge_python_code(existing_code, new_code)

        # 検証: 新規クラス SearchEngine と、既存クラス GrepResult, GrepEngine が共存していること
        assert "class SearchEngine" in merged_code
        assert "class GrepResult" in merged_code
        assert "class GrepEngine" in merged_code
        # インポートもマージされていること
        assert "from another_lib import Parser" in merged_code
        assert "import sys" in merged_code


class TestTestFailureError:
    """TestFailureErrorのテスト"""

    def test_test_failure_error_creation(self):
        """TestFailureError作成テスト"""
        test_result = TestResult(
            passed=False,
            total_tests=10,
            failed_tests=3,
            error_log="AssertionError: Expected 5 but got 3",
            duration=2.5
        )

        error = TestFailureError(test_result)
        assert error.test_result == test_result
        assert "Tests failed" in str(error)



class TestUpdateTaskStatus:
    """_update_task_status_to_doneのテスト"""

    def test_update_task_status_to_done_in_project_path(self, tmp_path):
        """プロジェクトパス直下のtasks.mdのタスクステータスが[x]に更新されるテスト"""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""# Tasks
- [ ] [ARCH-001] タスク1  <!-- priority:medium -->
- [/] [ARCH-002] タスク2  <!-- priority:medium -->
- [x] [ARCH-003] タスク3  <!-- priority:medium -->
""", encoding="utf-8")

        orchestrator = IssueOrchestrator(root_dir=tmp_path)
        req = Requirements(
            issue_id="ARCH-002",
            title="タスク2",
            description="説明",
            project_path=tmp_path,
            related_files=[],
            priority="medium"
        )

        orchestrator._update_task_status_to_done(req)

        updated_content = tasks_md.read_text(encoding="utf-8")
        assert "- [x] [ARCH-002] タスク2" in updated_content
        assert "- [ ] [ARCH-001] タスク1" in updated_content
        assert "- [x] [ARCH-003] タスク3" in updated_content


class TestExecutionResult:
    """ExecutionResultデータクラスのテスト"""

    def test_execution_result_success(self):
        """成功時のExecutionResultテスト"""
        result = ExecutionResult(
            success=True,
            issue_id="ARCH-001",
            context_data={"phase": "completed"},
            error_log=None,
            files_changed=["tools/test.py"],
            test_result=TestResult(True, 5, 0, "", 1.0)
        )

        assert result.success is True
        assert result.issue_id == "ARCH-001"
        assert len(result.files_changed) == 1
        assert result.error_log is None

    def test_execution_result_failure(self):
        """失敗時のExecutionResultテスト"""
        result = ExecutionResult(
            success=False,
            issue_id="ARCH-002",
            context_data={},
            error_log="Something went wrong",
            files_changed=[],
            test_result=None
        )

        assert result.success is False
        assert result.error_log == "Something went wrong"
        assert result.test_result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
