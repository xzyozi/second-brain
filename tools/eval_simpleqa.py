"""
tools/eval_simpleqa.py

SimpleQAなどの標準データセットに基づくエージェント評価・集計スクリプト。
モデル/エージェントの正確性 (Correct)、ハルシネーション (Incorrect)、回答拒否 (Abstain) を判定・集計する。
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("eval_simpleqa")

# 回答辞退/不明を示す代表的なキーワード
ABSTAIN_KEYWORDS = ["分かりません", "不明", "知らん", "情報がありません", "答えることができません", "unknown", "don't know", "i don't know"]

class SimpleQAEvaluator:
    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"データセットファイルが見つかりません: {dataset_path}")
        self.data = json.loads(self.dataset_path.read_text(encoding="utf-8"))

    def evaluate_response(self, target: str, response: str, allow_abstain: bool = False) -> str:
        """
        モデルのレスポンスを評価し、'correct', 'incorrect', 'abstain' のいずれかを返す。
        """
        response_lower = response.strip().lower()
        target_lower = target.strip().lower()

        # 1. 回答拒否 (Abstain) の判定
        is_abstain = any(kw in response_lower for kw in ABSTAIN_KEYWORDS)
        
        # ターゲット自体が Abstain/不明 を要求している場合
        if allow_abstain or any(kw in target_lower for kw in ABSTAIN_KEYWORDS):
            if is_abstain or target_lower in response_lower:
                return "correct"

        if is_abstain:
            return "abstain"

        # 2. 正解 (Correct) の判定（ターゲット文字列が回答に含まれているか）
        if target_lower in response_lower:
            return "correct"

        # 3. 誤答 / ハルシネーション (Incorrect)
        return "incorrect"

    def run_eval(self, mock_responses: Dict[str, str] = None) -> Dict[str, Any]:
        """
        全問題に対して評価を実行する。
        mock_responsesが与えられた場合はそれを使用し、無ければダミー実行を行う。
        """
        results = []
        counts = {"correct": 0, "incorrect": 0, "abstain": 0}

        for item in self.data:
            item_id = item.get("id")
            problem = item.get("problem")
            target = item.get("target")
            allow_abstain = item.get("allow_abstain", False)

            if mock_responses and item_id in mock_responses:
                response = mock_responses[item_id]
            else:
                # デフォルトのシミュレーション回答
                response = target if "火星" not in problem else "分かりません"

            status = self.evaluate_response(target, response, allow_abstain=allow_abstain)
            counts[status] += 1

            results.append({
                "id": item_id,
                "problem": problem,
                "target": target,
                "response": response,
                "status": status
            })

        total = len(self.data)
        summary = {
            "total": total,
            "counts": counts,
            "rates": {
                "correct_rate": round(counts["correct"] / total * 100, 2) if total > 0 else 0,
                "incorrect_rate": round(counts["incorrect"] / total * 100, 2) if total > 0 else 0,
                "abstain_rate": round(counts["abstain"] / total * 100, 2) if total > 0 else 0
            },
            "details": results
        }
        return summary

    def print_report(self, summary: Dict[str, Any]):
        print("\n========================================")
        print(" SimpleQA Evaluation Summary Report")
        print("========================================")
        print(f"Total Questions : {summary['total']}")
        print(f"- Correct       : {summary['counts']['correct']} ({summary['rates']['correct_rate']}%)")
        print(f"- Incorrect     : {summary['counts']['incorrect']} ({summary['rates']['incorrect_rate']}%)")
        print(f"- Abstain       : {summary['counts']['abstain']} ({summary['rates']['abstain_rate']}%)")
        print("========================================\n")


def main():
    parser = argparse.ArgumentParser(description="SimpleQA データセット評価スクリプト")
    parser.add_argument("--dataset", type=str, default="tests/datasets/simpleqa_sample.json", help="データセットファイルパス")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    evaluator = SimpleQAEvaluator(dataset_path)
    summary = evaluator.run_eval()
    evaluator.print_report(summary)


if __name__ == "__main__":
    main()
