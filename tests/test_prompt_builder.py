#!/usr/bin/env python3
"""
test_prompt_builder.py - PromptBuilderのテスト
"""

import pytest
from pathlib import Path
import sys

# tools/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.prompt_builder import (
    PromptBuilder,
    Requirements,
    Constraints,
    ImplementationPlan
)


class TestPromptBuilder:
    """PromptBuilderのテスト"""

    def test_initialization_no_templates(self, tmp_path):
        """テンプレートディレクトリが存在しない場合の初期化テスト"""
        agents_dir = tmp_path / "nonexistent"
        builder = PromptBuilder(agents_dir=agents_dir)

        assert len(builder.templates) == 0

    def test_initialization_with_templates(self, tmp_path):
        """テンプレート読み込みテスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # テンプレートファイル作成
        (agents_dir / "executor.md").write_text("# Executor Template", encoding="utf-8")
        (agents_dir / "coder.md").write_text("# Coder Template", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        assert len(builder.templates) == 2
        assert "executor" in builder.templates
        assert "coder" in builder.templates
        assert "Executor Template" in builder.templates["executor"]

    def test_build_implementation_prompt_basic(self, tmp_path):
        """実装指示書プロンプト構築の基本テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "executor.md").write_text("# Executor\n\nYou are an executor agent.", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        requirements = Requirements(
            issue_id="ARCH-001",
            title="Pythonオーケストレーター実装",
            description="Agent制御をPython側で行う",
            project_path=Path("/project"),
            related_files=[Path("tools/orchestrator.py")],
            priority="critical"
        )

        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=["sys", "os", "pathlib"],
            file_encoding="utf-8",
            line_ending="LF"
        )

        prompt = builder.build_implementation_prompt(requirements, constraints)

        # プロンプトの内容確認
        assert "ARCH-001" in prompt
        assert "Pythonオーケストレーター実装" in prompt
        assert "critical" in prompt
        assert "## 実装指示書" in prompt
        assert "sys" in prompt
        assert "Executor" in prompt  # テンプレートが含まれている

    def test_build_implementation_prompt_with_context(self, tmp_path):
        """コンテキスト付き実装指示書プロンプト構築テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "executor.md").write_text("# Executor Template", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        requirements = Requirements(
            issue_id="ARCH-002",
            title="テストIssue",
            description="テスト説明",
            project_path=Path("."),
            related_files=[],
            priority="high"
        )

        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys"]
        )

        context_summary = "Issue: ARCH-002\n要件: テスト機能の実装"

        prompt = builder.build_implementation_prompt(
            requirements,
            constraints,
            context_summary=context_summary
        )

        assert "ARCH-002" in prompt
        assert context_summary in prompt
        assert "外部モジュール使用: 禁止" in prompt

    def test_build_implementation_prompt_with_parent_id(self, tmp_path):
        """parent_idが含まれる場合の実装指示書プロンプト構築テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "executor.md").write_text("# Executor Template", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        requirements = Requirements(
            issue_id="ARCH-002",
            title="テストIssue",
            description="テスト説明",
            project_path=Path("."),
            related_files=[],
            priority="high",
            parent_id="ARCH-001"
        )

        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys"]
        )

        prompt = builder.build_implementation_prompt(
            requirements,
            constraints
        )

        assert "ARCH-002" in prompt
        assert "**親Issue ID**: ARCH-001" in prompt

    def test_build_coding_prompt_basic(self, tmp_path):
        """コード生成プロンプト構築の基本テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "coder.md").write_text("# Coder\n\nYou are a coding agent.", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        impl_plan = ImplementationPlan(
            content="tools/orchestrator.py を実装してください。\nIssueOrchestratorクラスを作成します。",
            files_to_create=[Path("tools/orchestrator.py")],
            files_to_edit=[Path("tests/test_orchestrator.py")],
            test_strategy="pytest で単体テスト"
        )

        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=["sys", "os"],
            file_encoding="utf-8",
            line_ending="LF"
        )

        prompt = builder.build_coding_prompt(impl_plan, constraints)

        assert "tools/orchestrator.py" in prompt
        assert "IssueOrchestratorクラス" in prompt
        assert "pytest で単体テスト" in prompt
        assert "# filepath:" in prompt
        assert "Coder" in prompt  # テンプレートが含まれている

    def test_build_coding_prompt_with_context(self, tmp_path):
        """コンテキスト付きコード生成プロンプト構築テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "coder.md").write_text("# Coder Template", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        impl_plan = ImplementationPlan(
            content="実装指示書の内容",
            files_to_create=[Path("tools/example.py")],
            files_to_edit=[],
            test_strategy="テスト戦略"
        )

        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys"]
        )

        context_summary = "要件: example機能の実装"

        prompt = builder.build_coding_prompt(
            impl_plan,
            constraints,
            context_summary=context_summary
        )

        assert "実装指示書の内容" in prompt
        assert context_summary in prompt
        assert "外部モジュール: 使用禁止" in prompt

    def test_build_review_prompt(self, tmp_path):
        """コードレビュープロンプト構築テスト"""
        builder = PromptBuilder(agents_dir=tmp_path / "agents")

        code_content = """
def example():
    print("Hello, World!")
"""

        requirements = Requirements(
            issue_id="ARCH-001",
            title="例示機能",
            description="説明",
            project_path=Path("."),
            related_files=[],
            priority="high"
        )

        prompt = builder.build_review_prompt(code_content, requirements)

        assert "ARCH-001" in prompt
        assert "例示機能" in prompt
        assert "def example" in prompt
        assert "レビュー観点" in prompt

    def test_format_file_list_empty(self):
        """空のファイルリスト整形テスト"""
        builder = PromptBuilder()

        formatted = builder._format_file_list([])
        assert "ファイル指定なし" in formatted

    def test_format_file_list_with_files(self):
        """ファイルリスト整形テスト"""
        builder = PromptBuilder()

        files = [Path("tools/test1.py"), Path("tests/test2.py")]
        formatted = builder._format_file_list(files)

        assert "tools/test1.py" in formatted
        assert "tests/test2.py" in formatted
        assert formatted.count("-") == 2  # 2つのリスト項目

    def test_format_constraints(self):
        """制約条件整形テスト"""
        builder = PromptBuilder()

        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys", "os"],
            file_encoding="utf-8",
            line_ending="LF",
            cooldown_days=3
        )

        formatted = builder._format_constraints(constraints)

        assert "外部モジュール使用: 禁止" in formatted
        assert "sys" in formatted
        assert "os" in formatted
        assert "utf-8" in formatted
        assert "LF" in formatted
        assert "3日" in formatted

    def test_format_constraints_modules_allowed(self):
        """外部モジュール許可時の制約整形テスト"""
        builder = PromptBuilder()

        constraints = Constraints(
            external_modules_forbidden=False,
            allowed_imports=["sys"]
        )

        formatted = builder._format_constraints(constraints)

        assert "外部モジュール使用: 許可" in formatted

    def test_get_available_agents_empty(self, tmp_path):
        """利用可能エージェント取得（空）テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        builder = PromptBuilder(agents_dir=agents_dir)
        agents = builder.get_available_agents()

        assert len(agents) == 0

    def test_get_available_agents_with_templates(self, tmp_path):
        """利用可能エージェント取得テスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "executor.md").write_text("# Executor", encoding="utf-8")
        (agents_dir / "coder.md").write_text("# Coder", encoding="utf-8")
        (agents_dir / "pm.md").write_text("# PM", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)
        agents = builder.get_available_agents()

        assert len(agents) == 3
        assert "executor" in agents
        assert "coder" in agents
        assert "pm" in agents

    def test_template_with_special_characters(self, tmp_path):
        """特殊文字を含むテンプレートのテスト"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        template_content = """
# Executor Agent

## Role
あなたは **Executor** です。

### 制約
- `外部モジュール` は使用禁止
- ファイルは UTF-8 で保存
"""
        (agents_dir / "executor.md").write_text(template_content, encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)
        assert "**Executor**" in builder.templates["executor"]
        assert "UTF-8" in builder.templates["executor"]

    def test_prompt_includes_all_requirements_fields(self, tmp_path):
        """プロンプトに全ての要件フィールドが含まれることを確認"""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "executor.md").write_text("", encoding="utf-8")

        builder = PromptBuilder(agents_dir=agents_dir)

        requirements = Requirements(
            issue_id="TEST-123",
            title="テストタイトル",
            description="テスト説明文",
            project_path=Path("/test/project"),
            related_files=[Path("file1.py"), Path("file2.py")],
            priority="critical",
            parent_id="PARENT-001"
        )

        constraints = Constraints(
            external_modules_forbidden=True,
            allowed_imports=["sys"]
        )

        prompt = builder.build_implementation_prompt(requirements, constraints)

        assert "TEST-123" in prompt
        assert "テストタイトル" in prompt
        assert "テスト説明文" in prompt
        assert "critical" in prompt
        assert "/test/project" in prompt


class TestRequirementsDataClass:
    """Requirementsデータクラスのテスト"""

    def test_requirements_with_parent_id(self):
        """親ID付きRequirementsテスト"""
        req = Requirements(
            issue_id="CHILD-001",
            title="子タスク",
            description="説明",
            project_path=Path("."),
            related_files=[],
            priority="medium",
            parent_id="PARENT-001"
        )

        assert req.parent_id == "PARENT-001"


class TestImplementationPlanDataClass:
    """ImplementationPlanデータクラスのテスト"""

    def test_implementation_plan_creation(self):
        """ImplementationPlan作成テスト"""
        plan = ImplementationPlan(
            content="実装指示書の内容",
            files_to_create=[Path("tools/new.py")],
            files_to_edit=[Path("tools/existing.py")],
            test_strategy="pytest による単体テスト"
        )

        assert plan.content == "実装指示書の内容"
        assert len(plan.files_to_create) == 1
        assert len(plan.files_to_edit) == 1
        assert "pytest" in plan.test_strategy


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
