#!/usr/bin/env python3
"""
orchestrator.py - Issue実行の全体フロー制御

Rev.3.0での新規モジュール。従来はExecutorエージェント（LLM）が担当していた
「他エージェントへの委譲判断」「結果の統合」をPython側で決定論的に実行する。

使い方:
    uv run python tools/orchestrator.py execute --issue-id ARCH-001
    uv run python tools/orchestrator.py execute --issue-id ARCH-001 --dry-run
"""

import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import argparse

# プロジェクトのルートディレクトリをインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.agent_client import AgentClient
from tools.prompt_builder import PromptBuilder

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s'
)
logger = logging.getLogger("orchestrator")


# ===========================
# データモデル
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


@dataclass
class GeneratedCode:
    """生成されたコード"""
    files: Dict[str, str]  # filepath -> content
    metadata: Dict[str, Any]


@dataclass
class TestResult:
    """テスト実行結果"""
    __test__ = False
    passed: bool
    total_tests: int
    failed_tests: int
    error_log: str
    duration: float


@dataclass
class ExecutionResult:
    """Issue実行結果"""
    success: bool
    issue_id: str
    context_data: Dict[str, Any]
    error_log: Optional[str]
    files_changed: List[str]
    test_result: Optional[TestResult]


# ===========================
# エラー定義
# ===========================

class OrchestratorError(Exception):
    """Orchestrator固有のエラー基底クラス"""
    pass


class AgentCallError(OrchestratorError):
    """エージェント呼び出しエラー"""
    pass


class ConstraintViolationError(OrchestratorError):
    """制約違反エラー（外部モジュール使用等）"""
    pass


class TestFailureError(OrchestratorError):
    """テスト失敗エラー"""
    __test__ = False
    def __init__(self, test_result: TestResult):
        self.test_result = test_result
        super().__init__(f"Tests failed:\n{test_result.error_log}")


# ===========================
# IssueOrchestrator
# ===========================

class IssueOrchestrator:
    """Issue実行のメインコントローラー"""

    def __init__(self, root_dir: Path = Path(".")):
        self.root_dir = root_dir
        self.agent_client = AgentClient()
        self.prompt_builder = PromptBuilder()

    def execute_issue(self, issue_id: str, max_retries: int = 2, dry_run: bool = False) -> ExecutionResult:
        """
        Issue実行のエントリポイント

        フロー:
        1. Issue情報の読み込み（roadmap.md, tasks.md）
        2. 要件収集（README、設計書の読み込み）
        3. 制約検証（外部モジュール禁止等）
        4. 実装指示書生成（ExecutorエージェントLLM呼び出し）
        5. コード生成（CoderエージェントLLM呼び出し）
        6. ファイル書き込み（Python決定論的処理）
        7. テスト実行（pytest subprocess）
        8. 結果記録

        Args:
            issue_id: 実行するIssue ID（例: "ARCH-001"）
            max_retries: エラー時の最大リトライ回数
            dry_run: Trueの場合、実際のファイル書き込みは行わない

        Returns:
            ExecutionResult: 実行結果の詳細
        """
        logger.info(f"[START] Issue実行開始: {issue_id}")

        try:
            # Phase 1: Issue情報読み込み
            logger.info(f"[Phase 1] Issue情報の読み込み: {issue_id}")
            requirements = self._gather_requirements(issue_id)

            # Phase 2: 制約検証
            logger.info(f"[Phase 2] 制約条件の検証")
            constraints = self._verify_constraints(requirements)

            # Phase 3: 実装指示書生成
            logger.info(f"[Phase 3] 実装指示書生成（Executor呼び出し）")
            impl_plan = self._generate_implementation_plan(requirements, constraints)

            # Phase 4: コード生成
            logger.info(f"[Phase 4] コード生成（Coder呼び出し）")
            generated_code = self._generate_code(impl_plan, constraints)

            if dry_run:
                logger.info("[DRY-RUN] ファイル書き込みとテスト実行をスキップ")
                return ExecutionResult(
                    success=True,
                    issue_id=issue_id,
                    context_data={"mode": "dry_run"},
                    error_log=None,
                    files_changed=list(generated_code.files.keys()),
                    test_result=None
                )

            # Phase 5: ファイル書き込み
            logger.info(f"[Phase 5] ファイル書き込み")
            write_result = self._write_files(generated_code)

            # Phase 6: テスト実行
            logger.info(f"[Phase 6] テスト実行")
            test_result = self._run_tests(requirements.project_path)

            # Phase 7: 成功判定
            if not test_result.passed:
                raise TestFailureError(test_result)

            logger.info(f"[SUCCESS] Issue実行完了: {issue_id}")
            return ExecutionResult(
                success=True,
                issue_id=issue_id,
                context_data={"requirements": asdict(requirements)},
                error_log=None,
                files_changed=write_result,
                test_result=test_result
            )

        except Exception as e:
            logger.error(f"[ERROR] Issue実行失敗: {issue_id}, エラー: {e}")
            return ExecutionResult(
                success=False,
                issue_id=issue_id,
                context_data={},
                error_log=str(e),
                files_changed=[],
                test_result=None
            )

    def _gather_requirements(self, issue_id: str) -> Requirements:
        """Issue関連の要件を収集"""
        logger.info(f"  - tasks.mdからIssue情報を読み込み")

        target_tasks_md = None
        project_path = self.root_dir

        # 1. projects/*/tasks.md を走査 (憲法ルール7準拠)
        projects_dir = self.root_dir / "projects"
        if projects_dir.exists():
            for p_dir in projects_dir.iterdir():
                if p_dir.is_dir():
                    p_tasks = p_dir / "tasks.md"
                    if p_tasks.exists():
                        content = p_tasks.read_text(encoding="utf-8")
                        if f"[{issue_id}]" in content:
                            target_tasks_md = p_tasks
                            project_path = p_dir
                            break

        # 2. 見つからない場合はルート直下の tasks.md をフォールバック
        root_tasks = self.root_dir / "tasks.md"
        if not target_tasks_md:
            if root_tasks.exists():
                content = root_tasks.read_text(encoding="utf-8")
                if f"[{issue_id}]" in content:
                    target_tasks_md = root_tasks
                    project_path = self.root_dir

        if not target_tasks_md:
            if not root_tasks.exists():
                raise OrchestratorError(f"tasks.md が見つかりません: {root_tasks}")
            raise OrchestratorError(f"Issue {issue_id} が tasks.md に見つかりません")

        content = target_tasks_md.read_text(encoding="utf-8")

        # 簡易パース（実際にはもっと堅牢にする）
        # 例: - [ ] [ARCH-001] タイトル  <!-- priority:high -->
        import re
        pattern = rf"\[{re.escape(issue_id)}\]\s+(.+?)(?:\s+<!--|$)"
        match = re.search(pattern, content)

        if not match:
            raise OrchestratorError(f"Issue {issue_id} が tasks.md に見つかりません")

        title = match.group(1).strip()
        logger.info(f"  - Issue発見: {title} (in {target_tasks_md.relative_to(self.root_dir)})")

        # 優先度抽出
        priority_match = re.search(rf"{re.escape(issue_id)}.*?priority:(\w+)", content)
        priority = priority_match.group(1) if priority_match else "medium"

        # 3. 既存のテストファイルを走査し、期待されるファイルパスを抽出 (対策B)
        related_files = []
        tests_dir = project_path / "tests"
        if tests_dir.exists():
            import re
            # クォーテーションで囲まれた .py ファイルのパスを抽出
            path_pattern = re.compile(r"['\"]([^'\"\s(]*?\.py)['\"]")
            for test_file in tests_dir.glob("test_*.py"):
                try:
                    test_content = test_file.read_text(encoding="utf-8")
                    for match_path in path_pattern.findall(test_content):
                        # プロジェクト名を含むフルパスをプロジェクト相対パスに正規化
                        # 例: projects/test_file_grep/sample/dummy_script.py -> sample/dummy_script.py
                        normalized_path = match_path
                        proj_prefix = f"projects/{project_path.name}/"
                        if normalized_path.startswith(proj_prefix):
                            normalized_path = normalized_path[len(proj_prefix):]
                        elif normalized_path.startswith(f"{project_path.name}/"):
                            normalized_path = normalized_path[len(project_path.name)+1:]
                        
                        p = Path(normalized_path)
                        # 重複を防ぎ、テスト自体は除外する
                        if p not in related_files and not p.is_absolute() and "test_" not in p.name:
                            related_files.append(p)
                except Exception as e:
                    logger.warning(f"  - テストファイル {test_file.name} のスキャン中にエラー: {e}")

        if related_files:
            logger.info(f"  - テストスキャンにより {len(related_files)} 個の関連ファイルを検出: {related_files}")

        return Requirements(
            issue_id=issue_id,
            title=title,
            description=title,  # 簡易版
            project_path=project_path,
            related_files=related_files,
            priority=priority,
            parent_id=None
        )

    def _verify_constraints(self, requirements: Requirements) -> Constraints:
        """制約条件を検証（外部モジュール禁止等）"""
        logger.info(f"  - プロジェクト制約を確認")

        # 例: pyproject.toml や README から外部モジュール禁止フラグを読む
        # 簡易版では固定値を返す
        return Constraints(
            external_modules_forbidden=False,  # プロジェクト次第
            allowed_imports=["sys", "os", "pathlib", "subprocess", "json", "dataclasses"],
            file_encoding="utf-8",
            line_ending="LF",
            cooldown_days=3
        )

    def _generate_implementation_plan(
        self, 
        requirements: Requirements,
        constraints: Constraints
    ) -> ImplementationPlan:
        """ExecutorエージェントLLMを呼び出して実装指示書を生成"""
        logger.info(f"  - Executorエージェント呼び出し")

        prompt = self.prompt_builder.build_implementation_prompt(
            requirements, constraints
        )

        response = self.agent_client.call_agent("executor", prompt)

        if not response.success:
            raise AgentCallError(f"Executor呼び出し失敗: {response.error_message}")

        data = response.parsed_data
        implementation_plan_content = data.get("implementation_plan", "")
        
        files_mentioned = [Path(f) for f in data.get("files_mentioned", [])]
        
        files_to_create = []
        files_to_edit = []
        for file in files_mentioned:
            full_path = requirements.project_path / file
            if full_path.exists():
                files_to_edit.append(file)
            else:
                files_to_create.append(file)

        return ImplementationPlan(
            content=implementation_plan_content,
            files_to_create=files_to_create,
            files_to_edit=files_to_edit,
            test_strategy="pytestで検証"
        )

    def _generate_code(
        self, 
        impl_plan: ImplementationPlan,
        constraints: Constraints
    ) -> GeneratedCode:
        """CoderエージェントLLMを呼び出してコード生成"""
        logger.info(f"  - Coderエージェント呼び出し")

        prompt = self.prompt_builder.build_coding_prompt(
            impl_plan, constraints
        )

        response = self.agent_client.call_agent("coder", prompt)

        if not response.success:
            raise AgentCallError(f"Coder呼び出し失敗: {response.error_message}")

        generated_files = response.parsed_data.get("generated_files", {})
        
        return GeneratedCode(
            files=generated_files,
            metadata={"stub": False}
        )

    def _write_files(self, generated_code: GeneratedCode) -> List[str]:
        """生成されたコードをファイルに書き込む"""
        logger.info(f"  - {len(generated_code.files)}個のファイルを書き込み")

        written_files = []
        for filepath_str, content in generated_code.files.items():
            filepath = Path(filepath_str)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8", newline="\n")
            written_files.append(str(filepath))
            logger.info(f"    ✓ {filepath}")

        return written_files

    def _run_tests(self, project_path: Path) -> TestResult:
        """pytestを実行してテスト結果を取得"""
        logger.info(f"  - pytest 実行")

        try:
            result = subprocess.run(
                ["uv", "run", "pytest", "tests/", "-v"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            # 簡易パース（実際には pytest --json などを使うべき）
            passed = result.returncode == 0
            output_lines = result.stdout.split("\n")

            # 例: "5 passed in 0.5s" のような行を探す
            summary_line = [line for line in output_lines if "passed" in line or "failed" in line]
            summary = summary_line[-1] if summary_line else ""

            logger.info(f"    テスト結果: {summary}")

            return TestResult(
                passed=passed,
                total_tests=0,  # 簡易版
                failed_tests=0 if passed else 1,
                error_log=f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}" if not passed else "",
                duration=0.0
            )

        except subprocess.TimeoutExpired:
            logger.error("    テストがタイムアウトしました")
            return TestResult(
                passed=False,
                total_tests=0,
                failed_tests=1,
                error_log="Test execution timeout",
                duration=120.0
            )
        except Exception as e:
            logger.error(f"    テスト実行エラー: {e}")
            return TestResult(
                passed=False,
                total_tests=0,
                failed_tests=1,
                error_log=str(e),
                duration=0.0
            )


# ===========================
# CLI
# ===========================

def main():
    parser = argparse.ArgumentParser(description="Issue Orchestrator - Python側エージェント制御")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # execute サブコマンド
    execute_parser = subparsers.add_parser("execute", help="Issueを実行")
    execute_parser.add_argument("--issue-id", required=True, help="実行するIssue ID")
    execute_parser.add_argument("--dry-run", action="store_true", help="実際の書き込みを行わない")
    execute_parser.add_argument("--max-retries", type=int, default=2, help="最大リトライ回数")

    args = parser.parse_args()

    if args.command == "execute":
        orchestrator = IssueOrchestrator()
        result = orchestrator.execute_issue(
            issue_id=args.issue_id,
            max_retries=args.max_retries,
            dry_run=args.dry_run
        )

        print("\n" + "=" * 60)
        print("実行結果")
        print("=" * 60)
        print(f"成功: {result.success}")
        print(f"Issue ID: {result.issue_id}")
        print(f"変更ファイル数: {len(result.files_changed)}")
        if result.error_log:
            print(f"エラー: {result.error_log}")
        if result.test_result:
            print(f"テスト: {'PASSED' if result.test_result.passed else 'FAILED'}")
        print("=" * 60)

        sys.exit(0 if result.success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
