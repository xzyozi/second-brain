#!/usr/bin/env python3
"""
run_pipeline.py  ―  priority-scoring Skill 用ラッパースクリプト

score-issues.py と check-blockers.py を連続実行し、
LLM が読みやすい「プレーンテキストのサマリー」だけを標準出力に返す。

設計意図:
  LLM に生のJSONを渡して解釈させると、複雑な構造を読み違えたり
  出力フォーマットが崩れたりしやすい（ローカル7B級モデルで特に顕著）。
  このスクリプトが最終的な解釈しやすいテキストまで加工することで、
  LLMの仕事を「テキストを読んで計画を1画面にまとめる」だけに限定する。

依存: Python標準ライブラリのみ（subprocess, json, pathlib）
使い方:
  python3 .opencode/skills/priority-scoring/scripts/run_pipeline.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]   # .opencode/skills/priority-scoring/scripts/ から5階層上
TOOLS = ROOT / "tools"
CACHE = ROOT / "tools" / ".cache"


def run_step(script_name: str) -> bool:
    result = subprocess.run(
        [sys.executable, str(TOOLS / script_name)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[ERROR] {script_name} が失敗しました:\n{result.stderr}", file=sys.stderr)
        return False
    return True


def main():
    # Step 1: スコアリング
    if not run_step("score-issues.py"):
        print("[FATAL] スコアリングに失敗しました。roadmap.md のフォーマットを確認してください。")
        sys.exit(1)

    # Step 2: ブロッカー判定
    if not run_step("check-blockers.py"):
        print("[FATAL] ブロッカー判定に失敗しました。")
        sys.exit(1)

    # 結果をマージして読みやすいテキストに変換
    score_data = json.loads((CACHE / "priority-cache.json").read_text(encoding="utf-8"))
    block_data = json.loads((CACHE / "blocked.json").read_text(encoding="utf-8"))

    blocked_ids = {b["id"] for b in block_data["blocked"]}

    print(f"[SUMMARY] 総Issue数={score_data['total']}  "
          f"実行可能={len(block_data['actionable'])}  "
          f"ブロック中={block_data['summary']['blocked_count']}")
    print()

    print("[ACTIONABLE]  ※ スコア降順・ブロック中のものは含まない")
    shown = 0
    for issue in score_data["issues"]:
        if issue["id"] in blocked_ids:
            continue
        print(f"  #{issue['id']:>4}  score={issue['score']:>5}  {issue['title']}")
        shown += 1
        if shown >= 10:   # 上位10件までに絞ってコンテキストを節約
            break
    print()

    if block_data["blocked"]:
        print("[BLOCKED]")
        for b in block_data["blocked"]:
            print(f"  #{b['id']:>4}  [{b['type']}] {b['label']:<12}  {b['title']}  → {b['detail']}")
    else:
        print("[BLOCKED]  なし")


if __name__ == "__main__":
    main()
