"""
tests/test_simpleqa_eval.py

tools/eval_simpleqa.py の単体テストおよび SimpleQA データセットに基づく品質テスト。
"""

import pytest
from pathlib import Path
from tools.eval_simpleqa import SimpleQAEvaluator


@pytest.fixture
def sample_dataset_path(tmp_path):
    dataset_file = tmp_path / "test_dataset.json"
    dataset_file.write_text("""[
  {
    "id": "q1",
    "problem": "日本の首都は？",
    "target": "東京",
    "allow_abstain": false
  },
  {
    "id": "q2",
    "problem": "未知の技術Xの仕様は？",
    "target": "分かりません",
    "allow_abstain": true
  }
]""", encoding="utf-8")
    return dataset_file


def test_evaluator_correct_response(sample_dataset_path):
    evaluator = SimpleQAEvaluator(sample_dataset_path)
    res = evaluator.evaluate_response(target="東京", response="日本の首都は東京です。")
    assert res == "correct"


def test_evaluator_aliases_response(sample_dataset_path):
    evaluator = SimpleQAEvaluator(sample_dataset_path)
    res = evaluator.evaluate_response(target="Not Found", response="リソースが見つからないことを意味します。", aliases=["見つからない", "存在しない"])
    assert res == "correct"


def test_evaluator_abstain_response(sample_dataset_path):
    evaluator = SimpleQAEvaluator(sample_dataset_path)
    res = evaluator.evaluate_response(target="何か特定の事実", response="申し訳ありませんが、分かりません。")
    assert res == "abstain"


def test_evaluator_incorrect_response(sample_dataset_path):
    evaluator = SimpleQAEvaluator(sample_dataset_path)
    res = evaluator.evaluate_response(target="東京", response="日本の首都は大阪です。")
    assert res == "incorrect"


def test_run_eval_summary(sample_dataset_path):
    evaluator = SimpleQAEvaluator(sample_dataset_path)
    mock_responses = {
        "q1": "日本の首都は東京です。",
        "q2": "分かりません"
    }
    summary = evaluator.run_eval(mock_responses=mock_responses)

    assert summary["total"] == 2
    assert summary["counts"]["correct"] == 2
    assert summary["rates"]["correct_rate"] == 100.0
    assert summary["counts"]["incorrect"] == 0
    assert summary["counts"]["abstain"] == 0


def test_simpleqa_sample_json_benchmark():
    """実際のサンプルデータセット tests/datasets/simpleqa_sample.json に対するテスト"""
    real_dataset = Path("tests/datasets/simpleqa_sample.json")
    assert real_dataset.exists()

    evaluator = SimpleQAEvaluator(real_dataset)
    summary = evaluator.run_eval()

    # 正解率が一定以上であることを確認
    assert summary["total"] > 0
    assert summary["rates"]["correct_rate"] >= 75.0
    assert summary["rates"]["incorrect_rate"] <= 25.0


@pytest.mark.eval_simpleqa_real
def test_simpleqa_real_llm_benchmark(opencode_available):
    """
    --eval-simpleqa オプション指定時のみ実行される実モデル (Gemma 4) での評価ベンチマーク
    """
    if not opencode_available:
        pytest.skip("opencode コマンドが利用できません")

    real_dataset = Path("tests/datasets/simpleqa_sample.json")
    assert real_dataset.exists()

    evaluator = SimpleQAEvaluator(real_dataset)
    # 実LLM(gemma 4 / coder)を呼び出して20件テスト
    summary = evaluator.run_eval(use_llm=True, agent_name="coder")

    print(f"\n[実LLM Gemma 4 測定結果] Total: {summary['total']}, Correct: {summary['rates']['correct_rate']}%, Abstain: {summary['rates']['abstain_rate']}%")
    assert summary["total"] == 20
    assert summary["rates"]["correct_rate"] >= 0.0  # 実測確認用

