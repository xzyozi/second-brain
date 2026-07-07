#!/usr/bin/env python3
"""
prompt_builder.py - エージェント別プロンプト構築

`.opencode/agents/` 配下のテンプレートに、実行時情報（要件、制約、コンテキスト）を
統合してエージェント別に最適化されたプロンプトを動的構築する。

使い方:
    from prompt_builder import PromptBuilder
    from context_manager import SharedContext
    
    builder = PromptBuilder()
    
    prompt = builder.build_implementation_prompt(
        requirements, constraints, context
    )
    print(prompt)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger("prompt_builder")


# ===========================
# データモデル（orchestrator.pyと共通）
# ===========================

@dataclass
class Requirements:
    """Issue要件"""
    issue_id: str
    title: str
    description: str
    project_path: Path
    related_files: List[Path]
    priority: str
    parent_id: Optional[str] = None


@dataclass
class Constraints:
    """制約条件"""
    external_modules_forbidden: bool
    allowed_imports: List[str]
    file_encoding: str = "utf-8"
    line_ending: str = "LF"
    cooldown_days: int = 3


@dataclass
class ImplementationPlan:
    """実装指示書"""
    content: str
    files_to_create: List[Path]
    files_to_edit: List[Path]
    test_strategy: str


# ===========================
# PromptBuilder
# ===========================

class PromptBuilder:
    """エージェント別プロンプト構築"""

    def __init__(self, agents_dir: Path = Path(".opencode/agents")):
        """
        Args:
            agents_dir: エージェント定義ファイル（.md）が格納されたディレクトリ
        """
        self.agents_dir = agents_dir
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """エージェント定義ファイル（.md）をテンプレートとして読み込み"""
        templates = {}

        if not self.agents_dir.exists():
            logger.warning(f"エージェントディレクトリが存在しません: {self.agents_dir}")
            return templates

        for md_file in self.agents_dir.glob("*.md"):
            agent_name = md_file.stem
            try:
                templates[agent_name] = md_file.read_text(encoding='utf-8')
                logger.debug(f"テンプレート読み込み: {agent_name} ({len(templates[agent_name])}文字)")
            except Exception as e:
                logger.error(f"テンプレート読み込みエラー ({agent_name}): {e}")

        logger.info(f"テンプレート読み込み完了: {len(templates)}個")
        return templates

    def build_implementation_prompt(
        self,
        requirements: Requirements,
        constraints: Constraints,
        context_summary: Optional[str] = None
    ) -> str:
        """
        Executor用の実装指示書生成プロンプトを構築

        Args:
            requirements: Issue要件
            constraints: 制約条件
            context_summary: 共有コンテキストのサマリー（オプション）

        Returns:
            構築されたプロンプト文字列
        """
        logger.info("実装指示書生成プロンプト構築中（Executor用）")

        # ベーステンプレート（executor.md）を取得
        base_template = self.templates.get("executor", "")

        # プロンプト構築
        prompt = f"""
{base_template}

---

# 実行指示

## Issue情報
- **Issue ID**: {requirements.issue_id}
- **タイトル**: {requirements.title}
- **説明**: {requirements.description}
- **優先度**: {requirements.priority}
- **プロジェクトパス**: {requirements.project_path}

## 関連ファイル
{self._format_file_list(requirements.related_files)}

## 制約条件（必須遵守）
{self._format_constraints(constraints)}

## 共有コンテキスト
{context_summary if context_summary else "（コンテキストなし）"}

---

## 出力指示

上記情報を元に、「**実装指示書**」を生成してください。

### 実装指示書に含めるべき内容:
1. **作成・編集すべきファイルパスのリスト**
   - 各ファイルについて、新規作成か既存編集かを明記
   - ファイルパスは相対パスで記述（例: `tools/example.py`）

2. **各ファイルで実装すべき内容の詳細**
   - 関数・クラスの責務
   - 入出力の仕様
   - エラーハンドリング方針

3. **テストケースの作成方針**
   - どのようなテストケースが必要か
   - テストファイル名とテスト対象

### 出力フォーマット:
Markdown形式で「## 実装指示書」セクションを作成してください。

例:
```
## 実装指示書

### 作成・編集ファイル
- [ ] 新規作成: `tools/example.py` - 例示機能の実装
- [ ] 編集: `tests/test_example.py` - テストケース追加

### 実装詳細
...
```
"""

        logger.debug(f"プロンプト構築完了: {len(prompt)}文字")
        return prompt

    def build_coding_prompt(
        self,
        impl_plan: ImplementationPlan,
        constraints: Constraints,
        context_summary: Optional[str] = None
    ) -> str:
        """
        Coder用のコード生成プロンプトを構築

        Args:
            impl_plan: 実装指示書
            constraints: 制約条件
            context_summary: 共有コンテキストのサマリー（オプション）

        Returns:
            構築されたプロンプト文字列
        """
        logger.info("コード生成プロンプト構築中（Coder用）")

        # ベーステンプレート（coder.md）を取得
        base_template = self.templates.get("coder", "")

        # プロンプト構築
        prompt = f"""
{base_template}

---

# コード生成指示

## 実装指示書
{impl_plan.content}

## 作成・編集対象ファイル
### 新規作成:
{self._format_file_list(impl_plan.files_to_create)}

### 編集:
{self._format_file_list(impl_plan.files_to_edit)}

## テスト戦略
{impl_plan.test_strategy}

## 制約条件（必須遵守）
{self._format_constraints(constraints)}

## 共有コンテキスト
{context_summary if context_summary else "（コンテキストなし）"}

---

## 出力指示

上記の実装指示書に従い、**Pythonコード**を生成してください。

### 出力形式:
各ファイルごとに、以下の形式のコードブロックで出力してください:

\```python
# filepath: tools/example.py
def example_function():
    \"\"\"関数の説明\"\"\"
    pass
\```

### 重要な注意事項:
1. **各コードブロックの先頭行に必ず `# filepath: <ファイルパス>` を記述**すること
2. **ファイルエンコーディング**: {constraints.file_encoding}
3. **改行コード**: {constraints.line_ending}
4. **外部モジュール**: {" 使用禁止" if constraints.external_modules_forbidden else "使用可能"}
5. **許可されたインポート**: {", ".join(constraints.allowed_imports)}

### コーディング規約:
- PEP 8 に準拠
- 型ヒント（Type Hints）を積極的に使用
- docstring は Google Style で記述
- エラーハンドリングを適切に実装
"""

        logger.debug(f"プロンプト構築完了: {len(prompt)}文字")
        return prompt

    def build_review_prompt(
        self,
        code_content: str,
        requirements: Requirements,
        context_summary: Optional[str] = None
    ) -> str:
        """
        コードレビュー用プロンプトを構築（将来拡張用）

        Args:
            code_content: レビュー対象のコード
            requirements: Issue要件
            context_summary: 共有コンテキストのサマリー（オプション）

        Returns:
            構築されたプロンプト文字列
        """
        logger.info("コードレビュープロンプト構築中")

        prompt = f"""
# コードレビュー指示

## レビュー対象コード
```python
{code_content[:2000]}  # 先頭2000文字
```

## 要件
- Issue ID: {requirements.issue_id}
- タイトル: {requirements.title}

## レビュー観点
1. 要件を満たしているか
2. コーディング規約に準拠しているか（PEP 8）
3. エラーハンドリングが適切か
4. テストケースが必要か

## 共有コンテキスト
{context_summary if context_summary else "（コンテキストなし）"}

---

上記コードをレビューし、指摘事項があれば列挙してください。
問題がない場合は「問題なし」と回答してください。
"""

        return prompt

    def _format_file_list(self, files: List[Path]) -> str:
        """ファイルリストをMarkdown形式に整形"""
        if not files:
            return "（ファイル指定なし）"

        lines = [f"- `{file}`" for file in files]
        return "\n".join(lines)

    def _format_constraints(self, constraints: Constraints) -> str:
        """制約条件をMarkdown形式に整形"""
        lines = [
            f"- **外部モジュール使用**: {' 禁止' if constraints.external_modules_forbidden else '許可'}",
            f"- **許可されたインポート**: {', '.join(constraints.allowed_imports)}",
            f"- **ファイルエンコーディング**: {constraints.file_encoding}",
            f"- **改行コード**: {constraints.line_ending}",
            f"- **cooldown期間**: {constraints.cooldown_days}日"
        ]
        return "\n".join(lines)

    def get_available_agents(self) -> List[str]:
        """利用可能なエージェント名のリストを取得"""
        return list(self.templates.keys())


# ===========================
# テスト用CLI
# ===========================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    builder = PromptBuilder()

    print("\n" + "=" * 60)
    print("PromptBuilder テスト")
    print("=" * 60)

    print(f"\n■ 利用可能なエージェント: {builder.get_available_agents()}")

    # テストデータ
    requirements = Requirements(
        issue_id="ARCH-001",
        title="Pythonオーケストレーター実装",
        description="Agent制御をPython側で行う",
        project_path=Path("."),
        related_files=[Path("tools/orchestrator.py")],
        priority="critical"
    )

    constraints = Constraints(
        external_modules_forbidden=False,
        allowed_imports=["sys", "os", "pathlib"],
        file_encoding="utf-8",
        line_ending="LF"
    )

    # Executor用プロンプト生成
    print("\n■ Executor用プロンプト:")
    print("-" * 60)
    executor_prompt = builder.build_implementation_prompt(requirements, constraints)
    print(executor_prompt[:500] + "\n... (省略)")

    # Coder用プロンプト生成
    impl_plan = ImplementationPlan(
        content="orchestrator.pyを実装する",
        files_to_create=[Path("tools/orchestrator.py")],
        files_to_edit=[],
        test_strategy="pytestで単体テスト"
    )

    print("\n■ Coder用プロンプト:")
    print("-" * 60)
    coder_prompt = builder.build_coding_prompt(impl_plan, constraints)
    print(coder_prompt[:500] + "\n... (省略)")

    print("\n" + "=" * 60)
