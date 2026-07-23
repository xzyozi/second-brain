#!/usr/bin/env python3
"""
test_llm_scenarios.py - シナリオ定義ベースのLLM統合テスト

tests/scenarios/*.json にシナリオを定義し、pytest.mark.parametrize で
エージェント・シナリオごとに自動的にテストが生成される。

実行方法:
    # LLMテストなし（スキップ）
    uv run pytest tests/test_llm_scenarios.py -v

    # LLMテスト有効
    uv run pytest tests/test_llm_scenarios.py --run-llm -v

    # 特定シナリオのみ実行
    uv run pytest tests/test_llm_scenarios.py --run-llm -v -k "real_task_context"
"""

import json
import pytest
from pathlib import Path
from tools.agent_client import AgentClient
from tools.eval_ccr import ConstraintComplianceValidator

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _load_scenarios(filename: str) -> list[dict]:
    """シナリオJSONファイルを読み込む"""
    path = SCENARIOS_DIR / filename
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_ids(scenarios: list[dict]) -> list[str]:
    """pytest パラメトライズ用のIDリストを返す"""
    return [s["id"] for s in scenarios]


# ── シナリオデータのロード ───────────────────────────────────────────────────
EXECUTOR_SCENARIOS = _load_scenarios("executor_scenarios.json")
CODER_SCENARIOS    = _load_scenarios("coder_scenarios.json")


# ── 共通アサーション関数 ──────────────────────────────────────────────────────
def _assert_scenario(scenario: dict, response, agent_name: str):
    """シナリオ定義に基づいて response をアサーションする"""
    a = scenario.get("assertions", {})

    # 成功フラグ
    if a.get("success", True):
        assert response.success is True, (
            f"[{scenario['id']}] エージェント {agent_name} の呼び出しが失敗しました\n"
            f"raw_output: {response.raw_output[:300]}"
        )

    # parsed_data に必須キーが存在するか
    for key in a.get("parsed_data_keys", []):
        assert key in response.parsed_data, (
            f"[{scenario['id']}] parsed_data に '{key}' が存在しません\n"
            f"parsed_data keys: {list(response.parsed_data.keys())}"
        )

    # executor: implementation_plan の長さチェック
    if "implementation_plan_min_length" in a:
        plan = response.parsed_data.get("implementation_plan", "")
        assert len(plan) >= a["implementation_plan_min_length"], (
            f"[{scenario['id']}] implementation_plan が短すぎます（{len(plan)} 文字）"
        )

    # executor: implementation_plan に特定キーワードが含まれるか（OR条件）
    if "implementation_plan_contains_any" in a:
        plan = response.parsed_data.get("implementation_plan", "")
        keywords = a["implementation_plan_contains_any"]
        assert any(kw in plan for kw in keywords), (
            f"[{scenario['id']}] implementation_plan に {keywords} のいずれも含まれていません\n"
            f"plan (先頭200文字): {plan[:200]}"
        )

    # executor: implementation_plan に含まれてはいけないキーワード（禁止ワード）
    if "implementation_plan_not_contains" in a:
        plan = response.parsed_data.get("implementation_plan", "")
        for kw in a["implementation_plan_not_contains"]:
            assert kw not in plan, (
                f"[{scenario['id']}] implementation_plan に禁止ワード '{kw}' が含まれています"
            )

    # coder: コードブロック数の最小値チェック
    if "code_blocks_min_count" in a:
        blocks = response.parsed_data.get("code_blocks", [])
        assert len(blocks) >= a["code_blocks_min_count"], (
            f"[{scenario['id']}] code_blocks が {a['code_blocks_min_count']} 件以上必要ですが "
            f"{len(blocks)} 件でした"
        )

    # coder: generated_files のキー存在チェック
    if "generated_files_contains_key" in a:
        gen = response.parsed_data.get("generated_files", {})
        expected_key = a["generated_files_contains_key"]
        assert expected_key in gen, (
            f"[{scenario['id']}] generated_files に '{expected_key}' が存在しません\n"
            f"generated_files keys: {list(gen.keys())}"
        )

    # coder: generated_files の最小件数チェック（0 の場合はスキップ）
    if "generated_files_min_count" in a and a["generated_files_min_count"] > 0:
        gen = response.parsed_data.get("generated_files", {})
        assert len(gen) >= a["generated_files_min_count"], (
            f"[{scenario['id']}] generated_files が {a['generated_files_min_count']} 件以上必要ですが "
            f"{len(gen)} 件でした"
        )

    # coder: code_blocks のいずれかに特定キーワードが含まれるか（OR条件）
    if "code_contains_any" in a:
        blocks = response.parsed_data.get("code_blocks", [])
        all_code = "\n".join(blocks)
        keywords = a["code_contains_any"]
        assert any(kw in all_code for kw in keywords), (
            f"[{scenario['id']}] 生成コードに {keywords} のいずれも含まれていません\n"
            f"code (先頭300文字): {all_code[:300]}"
        )

    # coder: CCR (Constraint Compliance Rate) 制約遵守率の自動評価
    if "ccr_rules" in a:
        blocks = response.parsed_data.get("code_blocks", [])
        all_code = "\n\n".join(blocks)
        
        # まず全体で試行し、SyntaxError の場合はブロック単体で試行
        validator = ConstraintComplianceValidator(all_code)
        if not validator.tree and blocks:
            for b in blocks:
                v = ConstraintComplianceValidator(b)
                if v.tree:
                    validator = v
                    break

        ccr_summary = validator.evaluate_rules(a["ccr_rules"])
        
        min_score = a.get("min_ccr_score", 80.0)
        actual_score = ccr_summary["ccr_score"]
        
        failed_details = [
            f"  - {r['rule']}: {r['message']}"
            for r in ccr_summary["results"] if not r["passed"]
        ]
        failed_str = "\n".join(failed_details)
        
        assert actual_score >= min_score, (
            f"[{scenario['id']}] CCR (制約遵守率) が基準値({min_score}%)を下回りました: {actual_score:.1f}%\n"
            f"不適合項目:\n{failed_str if failed_str else 'なし'}"
        )


# ── executor シナリオテスト ───────────────────────────────────────────────────
@pytest.mark.llm
@pytest.mark.parametrize("scenario", EXECUTOR_SCENARIOS, ids=_scenario_ids(EXECUTOR_SCENARIOS))
def test_executor_scenario(scenario, opencode_available):
    """executor エージェントのシナリオ別動作検証"""
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")

    client = AgentClient()
    try:
        response = client.call_agent(
            "executor",
            scenario["prompt"],
            context_summary=scenario.get("context_summary")
        )
        _assert_scenario(scenario, response, "executor")
    except Exception as e:
        pytest.fail(
            f"シナリオ '{scenario['id']}' の実行中に予期しないエラーが発生しました: {e}"
        )


# ── coder シナリオテスト ──────────────────────────────────────────────────────
@pytest.mark.llm
@pytest.mark.parametrize("scenario", CODER_SCENARIOS, ids=_scenario_ids(CODER_SCENARIOS))
def test_coder_scenario(scenario, opencode_available):
    """coder エージェントのシナリオ別動作検証"""
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")

    client = AgentClient()
    try:
        response = client.call_agent(
            "coder",
            scenario["prompt"],
            context_summary=scenario.get("context_summary")
        )
        _assert_scenario(scenario, response, "coder")
    except Exception as e:
        pytest.fail(
            f"シナリオ '{scenario['id']}' の実行中に予期しないエラーが発生しました: {e}"
        )


# ── E2E: Orchestrator ドライランテスト ────────────────────────────────────────
@pytest.mark.llm
def test_orchestrator_dry_run_e2e(opencode_available):
    """
    IssueOrchestrator を dry_run=True で実行し、
    executor → coder の順に呼び出されることと、ExecutionResult.success == True を確認する
    """
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")

    from unittest.mock import patch, MagicMock, call
    from tools.orchestrator import IssueOrchestrator
    from tools.agent_client import AgentResponse
    from datetime import datetime

    executor_response = AgentResponse(
        raw_output="## 実装指示書\n\n対象ファイル: src/office_parser.py\n\n実装内容の説明。",
        parsed_data={
            "implementation_plan": "対象ファイル: src/office_parser.py\n\n実装内容の説明。",
            "files_mentioned": ["src/office_parser.py"]
        },
        success=True,
        error_message=None,
        execution_time=5.0,
        agent_name="executor",
        timestamp=datetime.now().isoformat()
    )
    coder_response = AgentResponse(
        raw_output="```python\n# filepath: src/office_parser.py\ndef extract_text(filepath):\n    return ''\n```",
        parsed_data={
            "code_blocks": ["# filepath: src/office_parser.py\ndef extract_text(filepath):\n    return ''"],
            "generated_files": {"src/office_parser.py": "def extract_text(filepath):\n    return ''"}
        },
        success=True,
        error_message=None,
        execution_time=8.0,
        agent_name="coder",
        timestamp=datetime.now().isoformat()
    )

    call_sequence = [executor_response, coder_response]

    with patch.object(IssueOrchestrator, '_generate_implementation_plan', return_value=MagicMock(
        files_to_create=[], files_to_edit=[], implementation_instructions="", related_files=[]
    )) as mock_executor, \
         patch.object(IssueOrchestrator, '_generate_code', return_value=MagicMock(
             files={"src/office_parser.py": "def extract_text(filepath):\n    return ''"}
         )) as mock_coder:

        orchestrator = IssueOrchestrator(root_dir=Path("c:/Users/xzyoi/Desktop/python/second-brain"))
        result = orchestrator.execute_issue("TFG-005", dry_run=True)

        # E2E アサーション
        assert result.success is True, f"dry_run が失敗しました: {result.error_log}"
        assert result.issue_id == "TFG-005"
        assert mock_executor.called, "executor (_generate_implementation_plan) が呼ばれていません"
        assert mock_coder.called,   "coder (_generate_code) が呼ばれていません"
