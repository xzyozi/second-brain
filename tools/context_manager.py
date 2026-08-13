#!/usr/bin/env python3
"""
context_manager.py - エージェント間コンテキスト共有

従来は各LLMセッションが独立していたため文脈が失われていたが、
Python側で明示的に保持することでコンテキスト断絶を防ぐ。

使い方:
    from context_manager import SharedContext, ContextSerializer
    
    ctx = SharedContext()
    ctx.set_issue_id("ARCH-001")
    ctx.add_requirement("title", "Pythonオーケストレーター実装")
    ctx.add_constraint("external_modules_forbidden", True)
    
    summary = ctx.get_summary()
    print(summary)
    
    # ファイル保存
    ContextSerializer.save(ctx, Path("context.json"))
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field

logger = logging.getLogger("context_manager")


# ===========================
# データモデル
# ===========================

@dataclass
class ContextEntry:
    """コンテキストエントリ（1つの情報単位）"""
    key: str
    value: Any
    category: str  # "requirement", "constraint", "intermediate", "error"
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ===========================
# SharedContext
# ===========================

class SharedContext:
    """全エージェント間で共有するコンテキスト"""

    def __init__(self):
        self.issue_id: Optional[str] = None
        self.project_path: Optional[str] = None
        self.requirements: Dict[str, Any] = {}
        self.constraints: Dict[str, Any] = {}
        self.intermediate_results: List[ContextEntry] = []
        self.error_history: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def set_issue_id(self, issue_id: str):
        """Issue IDを設定"""
        self.issue_id = issue_id
        self._update_timestamp()
        logger.debug(f"Issue ID設定: {issue_id}")

    def set_project_path(self, project_path: str):
        """プロジェクトパスを設定"""
        self.project_path = project_path
        self._update_timestamp()
        logger.debug(f"プロジェクトパス設定: {project_path}")

    def add_requirement(self, key: str, value: Any, metadata: Optional[Dict] = None):
        """要件を追加"""
        self.requirements[key] = value
        self._add_entry(key, value, "requirement", metadata)
        logger.debug(f"要件追加: {key}")

    def add_constraint(self, key: str, value: Any, metadata: Optional[Dict] = None):
        """制約を追加"""
        self.constraints[key] = value
        self._add_entry(key, value, "constraint", metadata)
        logger.debug(f"制約追加: {key}")

    def add(self, key: str, value: Any, category: str = "intermediate", metadata: Optional[Dict] = None):
        """汎用的な情報追加（中間結果等）"""
        self._add_entry(key, value, category, metadata)
        logger.debug(f"情報追加: {key} (category={category})")

    def _add_entry(self, key: str, value: Any, category: str, metadata: Optional[Dict] = None):
        """内部用: エントリ追加"""
        entry = ContextEntry(
            key=key,
            value=value,
            category=category,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        self.intermediate_results.append(entry)
        self._update_timestamp()

    def add_error(self, phase: str, error: Exception, metadata: Optional[Dict] = None):
        """エラー履歴を記録"""
        error_entry = {
            "phase": phase,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.error_history.append(error_entry)
        self._update_timestamp()
        logger.warning(f"エラー記録: {phase} - {type(error).__name__}")

    def get_summary(self, max_length: int = 2000, include_errors: bool = True) -> str:
        """
        プロンプトに埋め込む用のサマリー文字列を生成

        Args:
            max_length: 最大文字数（トークン数制限対策）
            include_errors: エラー履歴を含めるか

        Returns:
            Markdown形式のサマリー文字列
        """
        summary_parts = []

        # ヘッダー
        summary_parts.append("# 共有コンテキスト\n")

        # Issue情報
        if self.issue_id:
            summary_parts.append(f"## Issue情報\n- Issue ID: {self.issue_id}\n")
        if self.project_path:
            summary_parts.append(f"- プロジェクトパス: {self.project_path}\n")

        # 要件
        if self.requirements:
            summary_parts.append("\n## 要件\n")
            summary_parts.append(self._format_dict(self.requirements))

        # 制約条件
        if self.constraints:
            summary_parts.append("\n## 制約条件（必須遵守）\n")
            summary_parts.append(self._format_dict(self.constraints))

        # 中間結果のサマリー
        if self.intermediate_results:
            summary_parts.append(f"\n## 処理履歴\n- 合計 {len(self.intermediate_results)} ステップ実行済み\n")

            # 最新5件の中間結果を表示
            recent_results = self.intermediate_results[-5:]
            summary_parts.append("\n### 最近の処理:\n")
            for entry in recent_results:
                summary_parts.append(f"- [{entry.category}] {entry.key}: {self._truncate(str(entry.value), 100)}\n")

        # エラー履歴
        if include_errors and self.error_history:
            summary_parts.append(f"\n## エラー履歴\n- 合計 {len(self.error_history)} 件のエラー\n")
            for error in self.error_history[-3:]:  # 最新3件
                summary_parts.append(f"- [{error['phase']}] {error['error_type']}: {error['error_message'][:100]}\n")

        # メタ情報
        summary_parts.append(f"\n## メタ情報\n- 作成: {self.metadata['created_at']}\n- 更新: {self.metadata['updated_at']}\n")

        # 結合してトリミング
        full_summary = "".join(summary_parts)
        if len(full_summary) > max_length:
            logger.debug(f"サマリーを{max_length}文字にトリミング（元: {len(full_summary)}文字）")
            return full_summary[:max_length] + "\n\n... (以降省略)"

        return full_summary

    def _format_dict(self, data: Dict[str, Any], indent: str = "- ") -> str:
        """辞書をMarkdownリスト形式に整形"""
        lines = []
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                lines.append(f"{indent}{key}: {json.dumps(value, ensure_ascii=False)}\n")
            else:
                lines.append(f"{indent}{key}: {value}\n")
        return "".join(lines)

    def _truncate(self, text: str, max_length: int) -> str:
        """文字列を指定長で切り詰め"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _update_timestamp(self):
        """更新タイムスタンプを記録"""
        self.metadata["updated_at"] = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """dict形式に変換（ファイル保存用）"""
        return {
            "issue_id": self.issue_id,
            "project_path": self.project_path,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "intermediate_results": [asdict(entry) for entry in self.intermediate_results],
            "error_history": self.error_history,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SharedContext':
        """dict形式から復元"""
        ctx = cls()
        ctx.issue_id = data.get("issue_id")
        ctx.project_path = data.get("project_path")
        ctx.requirements = data.get("requirements", {})
        ctx.constraints = data.get("constraints", {})

        # intermediate_resultsの復元
        ctx.intermediate_results = [
            ContextEntry(**entry_data)
            for entry_data in data.get("intermediate_results", [])
        ]

        ctx.error_history = data.get("error_history", [])
        ctx.metadata = data.get("metadata", {})

        logger.debug(f"コンテキスト復元: Issue={ctx.issue_id}, エントリ数={len(ctx.intermediate_results)}")
        return ctx

    def clear_intermediate_results(self):
        """中間結果をクリア（メモリ節約用）"""
        cleared_count = len(self.intermediate_results)
        self.intermediate_results = []
        logger.info(f"中間結果をクリア: {cleared_count}件削除")

    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            "issue_id": self.issue_id,
            "total_entries": len(self.intermediate_results),
            "requirements_count": len(self.requirements),
            "constraints_count": len(self.constraints),
            "errors_count": len(self.error_history),
            "categories": self._count_by_category(),
            "created_at": self.metadata.get("created_at"),
            "updated_at": self.metadata.get("updated_at")
        }

    def _count_by_category(self) -> Dict[str, int]:
        """カテゴリ別のエントリ数をカウント"""
        counts: Dict[str, int] = {}
        for entry in self.intermediate_results:
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts


# ===========================
# ContextSerializer
# ===========================

class ContextSerializer:
    """コンテキストのファイル保存・読み込み"""

    @staticmethod
    def save(context: SharedContext, filepath: Path):
        """コンテキストをJSONファイルに保存"""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"コンテキスト保存: {filepath}")

    @staticmethod
    def load(filepath: Path) -> SharedContext:
        """JSONファイルからコンテキストを読み込み"""
        if not filepath.exists():
            raise FileNotFoundError(f"コンテキストファイルが見つかりません: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        context = SharedContext.from_dict(data)
        logger.info(f"コンテキスト読み込み: {filepath}")
        return context

    @staticmethod
    def save_summary(context: SharedContext, filepath: Path):
        """サマリーをMarkdownファイルに保存"""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        summary = context.get_summary(max_length=10000)  # サマリーは長めに

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(summary)

        logger.info(f"サマリー保存: {filepath}")


# ===========================
# テスト用CLI
# ===========================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    # テスト実行
    ctx = SharedContext()
    ctx.set_issue_id("ARCH-001")
    ctx.set_project_path("/path/to/project")

    ctx.add_requirement("title", "Pythonオーケストレーター実装")
    ctx.add_requirement("description", "Agent制御をPython側で行う")

    ctx.add_constraint("external_modules_forbidden", True)
    ctx.add_constraint("file_encoding", "utf-8")

    ctx.add("phase1_completed", True, category="intermediate")
    ctx.add("executor_response", "実装指示書生成完了", category="intermediate")

    try:
        raise ValueError("テストエラー")
    except ValueError as e:
        ctx.add_error("test_phase", e)

    print("\n" + "=" * 60)
    print("SharedContext テスト")
    print("=" * 60)

    print("\n■ サマリー:")
    print(ctx.get_summary())

    print("\n■ 統計情報:")
    stats = ctx.get_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # ファイル保存テスト
    test_file = Path("test_context.json")
    ContextSerializer.save(ctx, test_file)
    print(f"\n✓ ファイル保存: {test_file}")

    # 読み込みテスト
    ctx2 = ContextSerializer.load(test_file)
    print(f"✓ ファイル読み込み: Issue={ctx2.issue_id}")

    # クリーンアップ
    test_file.unlink()
    print(f"✓ テストファイル削除")

    print("=" * 60)
