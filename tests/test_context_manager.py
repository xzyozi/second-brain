#!/usr/bin/env python3
"""
test_context_manager.py - SharedContextのテスト
"""

import pytest
from pathlib import Path
from datetime import datetime
import sys
import json

# tools/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.context_manager import SharedContext, ContextSerializer, ContextEntry


class TestSharedContext:
    """SharedContextの基本機能テスト"""

    def test_initialization(self):
        """初期化テスト"""
        ctx = SharedContext()
        assert ctx.issue_id is None
        assert ctx.project_path is None
        assert len(ctx.requirements) == 0
        assert len(ctx.constraints) == 0
        assert len(ctx.intermediate_results) == 0
        assert len(ctx.error_history) == 0

    def test_set_issue_id(self):
        """Issue ID設定テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        assert ctx.issue_id == "ARCH-001"

    def test_set_project_path(self):
        """プロジェクトパス設定テスト"""
        ctx = SharedContext()
        ctx.set_project_path("/path/to/project")
        assert ctx.project_path == "/path/to/project"

    def test_add_requirement(self):
        """要件追加テスト"""
        ctx = SharedContext()
        ctx.add_requirement("title", "テストタイトル")
        ctx.add_requirement("description", "テスト説明")

        assert ctx.requirements["title"] == "テストタイトル"
        assert ctx.requirements["description"] == "テスト説明"
        assert len(ctx.intermediate_results) == 2

    def test_add_constraint(self):
        """制約追加テスト"""
        ctx = SharedContext()
        ctx.add_constraint("external_modules_forbidden", True)
        ctx.add_constraint("file_encoding", "utf-8")

        assert ctx.constraints["external_modules_forbidden"] is True
        assert ctx.constraints["file_encoding"] == "utf-8"
        assert len(ctx.intermediate_results) == 2

    def test_add_generic(self):
        """汎用的な情報追加テスト"""
        ctx = SharedContext()
        ctx.add("phase1_result", "success", category="intermediate")
        ctx.add("executor_output", "指示書生成完了", category="executor")

        assert len(ctx.intermediate_results) == 2
        assert ctx.intermediate_results[0].key == "phase1_result"
        assert ctx.intermediate_results[0].category == "intermediate"

    def test_add_error(self):
        """エラー追加テスト"""
        ctx = SharedContext()

        try:
            raise ValueError("テストエラー")
        except ValueError as e:
            ctx.add_error("test_phase", e, metadata={"retry": 1})

        assert len(ctx.error_history) == 1
        assert ctx.error_history[0]["phase"] == "test_phase"
        assert ctx.error_history[0]["error_type"] == "ValueError"
        assert "テストエラー" in ctx.error_history[0]["error_message"]

    def test_get_summary_basic(self):
        """サマリー生成の基本テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        ctx.add_requirement("title", "テストIssue")
        ctx.add_constraint("file_encoding", "utf-8")

        summary = ctx.get_summary()

        assert "ARCH-001" in summary
        assert "テストIssue" in summary
        assert "utf-8" in summary
        assert "## 要件" in summary
        assert "## 制約条件" in summary

    def test_get_summary_with_max_length(self):
        """サマリーの最大長制限テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")

        # 大量のデータを追加
        for i in range(100):
            ctx.add(f"key_{i}", f"value_{i}" * 100, category="test")

        summary = ctx.get_summary(max_length=500)
        assert len(summary) <= 500 + 100  # "... (以降省略)" の分

    def test_to_dict_and_from_dict(self):
        """dict変換・復元テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        ctx.set_project_path("/project")
        ctx.add_requirement("title", "テスト")
        ctx.add_constraint("encoding", "utf-8")
        ctx.add("intermediate", "data")

        # dict変換
        ctx_dict = ctx.to_dict()
        assert ctx_dict["issue_id"] == "ARCH-001"
        assert ctx_dict["project_path"] == "/project"
        assert "title" in ctx_dict["requirements"]

        # 復元
        ctx2 = SharedContext.from_dict(ctx_dict)
        assert ctx2.issue_id == "ARCH-001"
        assert ctx2.project_path == "/project"
        assert ctx2.requirements["title"] == "テスト"
        assert ctx2.constraints["encoding"] == "utf-8"
        assert len(ctx2.intermediate_results) == 3

    def test_clear_intermediate_results(self):
        """中間結果クリアテスト"""
        ctx = SharedContext()
        ctx.add("key1", "value1")
        ctx.add("key2", "value2")
        ctx.add("key3", "value3")

        assert len(ctx.intermediate_results) == 3

        ctx.clear_intermediate_results()
        assert len(ctx.intermediate_results) == 0

    def test_get_statistics(self):
        """統計情報取得テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        ctx.add_requirement("title", "テスト")
        ctx.add_requirement("description", "説明")
        ctx.add_constraint("encoding", "utf-8")
        ctx.add("key1", "value1", category="test")
        ctx.add("key2", "value2", category="test")

        try:
            raise RuntimeError("テストエラー")
        except RuntimeError as e:
            ctx.add_error("test_phase", e)

        stats = ctx.get_statistics()
        assert stats["issue_id"] == "ARCH-001"
        assert stats["total_entries"] == 5
        assert stats["requirements_count"] == 2
        assert stats["constraints_count"] == 1
        assert stats["errors_count"] == 1
        assert "requirement" in stats["categories"]
        assert "test" in stats["categories"]


class TestContextSerializer:
    """ContextSerializerのテスト"""

    def test_save_and_load(self, tmp_path):
        """保存・読み込みテスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        ctx.add_requirement("title", "テストIssue")
        ctx.add_constraint("encoding", "utf-8")

        # 保存
        filepath = tmp_path / "test_context.json"
        ContextSerializer.save(ctx, filepath)
        assert filepath.exists()

        # 読み込み
        ctx2 = ContextSerializer.load(filepath)
        assert ctx2.issue_id == "ARCH-001"
        assert ctx2.requirements["title"] == "テストIssue"
        assert ctx2.constraints["encoding"] == "utf-8"

    def test_save_summary(self, tmp_path):
        """サマリー保存テスト"""
        ctx = SharedContext()
        ctx.set_issue_id("ARCH-001")
        ctx.add_requirement("title", "テストIssue")

        filepath = tmp_path / "summary.md"
        ContextSerializer.save_summary(ctx, filepath)

        assert filepath.exists()
        content = filepath.read_text(encoding='utf-8')
        assert "ARCH-001" in content
        assert "テストIssue" in content

    def test_load_nonexistent_file(self):
        """存在しないファイルの読み込みテスト"""
        with pytest.raises(FileNotFoundError):
            ContextSerializer.load(Path("/nonexistent/file.json"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
