#!/usr/bin/env python3
"""
scaffold_project.py  ―  new-project-intake Skill 用ヘルパースクリプト

3問のヒアリング結果を受け取り、README.md / tasks.md の雛形を
決まったテンプレートで生成する。

設計意図:
  LLMに毎回自由形式でMarkdownを組み立てさせると、見出しの表記揺れや
  構造の欠落が発生しやすい。テンプレートをスクリプト側で固定することで、
  後続の score-issues.py 等が期待する構造との整合性も保ちやすくなる。

依存: Python標準ライブラリのみ
使い方:
  python3 scaffold_project.py <name> --why "..." --mvp "..." --risk "..."
"""

import argparse
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PROJECTS = ROOT / "projects"

README_TEMPLATE = """# {name}

## Why（解決する課題）
{why}

## MVP（最小機能）
{mvp}

## 技術的懸念
{risk}

## ステータス
- 発足日: {date}
- フェーズ: 企画

---
*このファイルは new-project-intake Skill により生成されました。*
"""

TASKS_TEMPLATE = """# タスクリスト（{name}）

<!-- auto-managed by tools/add-task.py -->

## 未着手

## 進行中

## 完了
"""


def main():
    parser = argparse.ArgumentParser(description="プロジェクト雛形の生成")
    parser.add_argument("name", help="プロジェクト名（projects/配下のディレクトリ名）")
    parser.add_argument("--why",  required=True, help="質問1の回答")
    parser.add_argument("--mvp",  required=True, help="質問2の回答")
    parser.add_argument("--risk", required=True, help="質問3の回答")
    args = parser.parse_args()

    proj_dir = PROJECTS / args.name
    if proj_dir.exists() and (proj_dir / "README.md").exists():
        print(f"[ERROR] projects/{args.name}/README.md は既に存在します。上書きを避けるため中断しました。")
        raise SystemExit(1)

    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "docs").mkdir(exist_ok=True)
    (proj_dir / "src").mkdir(exist_ok=True)

    today = datetime.date.today().isoformat()

    (proj_dir / "README.md").write_text(
        README_TEMPLATE.format(name=args.name, why=args.why, mvp=args.mvp, risk=args.risk, date=today),
        encoding="utf-8",
    )
    (proj_dir / "tasks.md").write_text(
        TASKS_TEMPLATE.format(name=args.name),
        encoding="utf-8",
    )

    print(f"[scaffold-project] 生成完了:")
    print(f"  {proj_dir / 'README.md'}")
    print(f"  {proj_dir / 'tasks.md'}")
    print(f"  {proj_dir / 'docs'}/  (空)")
    print(f"  {proj_dir / 'src'}/   (空)")
    print()
    print("次のステップ: git add で追加し、'docs: {} プロジェクト立ち上げ' でコミットしてください".format(args.name))


if __name__ == "__main__":
    main()
