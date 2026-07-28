# 詳細設計書（コンポーネント詳細・データフロー・実装仕様）
**LangGraph / LiteLLM / Aider / Ruff / Reviewdog 統合実装仕様**

| 項目     | 内容                                                           |
| :------- | :--------------------------------------------------------------- |
| 文書番号 | SBOS-DD-003                                                      |
| 版数     | Rev.4.1（Aiderフラグ修復・動的B7エスカレーション・リトライ上限回路統合版） |
| 改訂日   | 2026年7月28日                                                     |
| 作成日   | 2026年7月28日                                                     |
| 関連文書 | SBOS-BD-002（基本設計書 Rev.4.1）、SBOS-MULTI-001 Rev.2.1、SBOS-OP-001 Rev.3.3（※旧自前実装向け。新アーキテクチャ移行に伴い大半が改訂対象）、SBOS-OSS-001/002 |
| 対象読者 | 実装担当エンジニア / アーキテクト / テストエンジニア             |

---

## 1. 依存パッケージおよび環境構築

```bash
# パッケージマネージャー uv による導入（Linux / macOS / Windows Native 共通）
uv pip install langgraph litellm aider-chat ruff pytest pytest-json-report

# Reviewdog（Windows Native の場合は executable を PATH に配置）
reviewdog -version
```

---

## 2. 状態管理データ構造 (`OrchestratorState`)

```python
# tools/orchestrator_graph.py
from typing import TypedDict, Literal, List, Dict, Any
from pathlib import Path
from langgraph.graph import StateGraph, END

class OrchestratorState(TypedDict):
    issue_id: str
    project_path: str            # projects/<name> の絶対パス
    title: str
    description: str
    priority: str

    impl_plan: str                # Executor（plan_node）が生成した実装指示書
    aider_message: str            # code_nodeでAiderに渡す追加指示（lint/test/review指摘の蓄積）

    lint_result: Dict[str, Any]   # {"passed": bool, "issues": [...]}
    test_result: Dict[str, Any]   # {"passed": bool, "log": str}
    review_verdict: Literal["LGTM", "changes_requested", ""]
    review_comments: List[Dict[str, Any]]  # rdjson準拠のコメント配列

    round: int                    # レビュー試行ラウンド数
    lint_round: int               # ⭐NEW: lint リトライ数 (F3対応)
    test_round: int               # ⭐NEW: test リトライ数 (F3対応)
    max_round: int                # タスクごとの最大試行許容数
    history: List[Dict[str, Any]]  # 各ノードの実行履歴
```

---

## 3. モジュール設計

### 3.1 `tools/llm_client.py` (LiteLLM ラッパー)

```python
#!/usr/bin/env python3
"""tools/llm_client.py - LiteLLM経由でのLLM呼び出し"""
import json, re, logging, litellm
from typing import Optional

logger = logging.getLogger("llm_client")
MODEL_MAP = {"planner": "ollama/qwen2.5-coder:14b", "reviewer": "ollama/qwen3:32b"}

def call_llm(role: str, system_prompt: str, user_prompt: str, expect_json: bool = False, timeout: int = 300) -> dict:
    model = MODEL_MAP.get(role, "ollama/qwen2.5-coder:7b-16k")
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            timeout=timeout, api_base="http://localhost:11434"
        )
    except Exception as e:
        logger.error(f"LiteLLM Error ({role}): {e}")
        raise

    raw_output = response.choices[0].message.content
    if not expect_json:
        return {"raw": raw_output}

    json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if not json_match:
        return {"verdict": "changes_requested", "comment": "JSON抽出失敗", "raw": raw_output}
    try:
        return json.loads(json_match.group(0))
    except Exception as e:
        return {"verdict": "changes_requested", "comment": f"JSONパースエラー: {e}", "raw": raw_output}
```

### 3.2 `tools/aider_runner.py` (Aider サブプロセス制御)

```python
#!/usr/bin/env python3
"""tools/aider_runner.py - Aiderサブプロセス起動 (F1修正済み)"""
import os, subprocess, logging
from pathlib import Path

def run_aider(project_path: Path, message: str, model: str = "ollama/qwen2.5-coder:7b-16k", timeout: int = 600) -> str:
    env = os.environ.copy()
    env["OLLAMA_API_BASE"] = "http://localhost:11434"
    # [F1修正] 正しい Aider CLI フラグは --no-auto-commits (複数形)
    cmd = ["aider", "--message", message, "--model", model, "--no-auto-commits", "--yes-always", "--no-stream"]
    res = subprocess.run(cmd, cwd=str(project_path), env=env, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"Aider failed: {res.stderr}")
    return get_git_diff(project_path)

def get_git_diff(project_path: Path) -> str:
    return subprocess.run(["git", "diff", "HEAD"], cwd=str(project_path), capture_output=True, text=True).stdout
```

---

## 4. LangGraph グラフ構築と条件分岐ロジック (リトライ回路統合)

```python
def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("plan", plan_node)
    g.add_node("code", code_node)
    g.add_node("lint", lint_node)
    g.add_node("test", test_node)
    g.add_node("review", review_node)
    g.add_node("done", done_node)
    g.add_node("escalate", escalate_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "code")
    g.add_edge("code", "lint")

    # [F3修正] lint 失敗時のループ制御（上限超過で escalate）
    def route_after_lint(s: OrchestratorState) -> str:
        if s["lint_result"]["passed"]:
            return "test"
        s["lint_round"] += 1
        if s["lint_round"] >= s["max_round"]:
            return "escalate"
        return "code"

    g.add_conditional_edges("lint", route_after_lint, {"test": "test", "code": "code", "escalate": "escalate"})

    # [F3修正] test 失敗時のループ制御（上限超過で escalate）
    def route_after_test(s: OrchestratorState) -> str:
        if s["test_result"]["passed"]:
            return "review"
        s["test_round"] += 1
        if s["test_round"] >= s["max_round"]:
            return "escalate"
        return "code"

    g.add_conditional_edges("test", route_after_test, {"review": "review", "code": "code", "escalate": "escalate"})

    # review 失敗時のループ制御
    def route_after_review(s: OrchestratorState) -> str:
        s["round"] += 1
        if s["review_verdict"] == "LGTM":
            return "done"
        if s["round"] >= s["max_round"]:
            return "escalate"
        return "code"

    g.add_conditional_edges("review", route_after_review, {"done": "done", "escalate": "escalate", "code": "code"})
    g.add_edge("done", END)
    g.add_edge("escalate", END)
    return g.compile()
```

### 4.1 B7 ブロッカー判定と `escalate_node` (F2修正)
`escalate_node` はレビュー、lint、または test の試行回数が `max_round` に達した際に呼ばれる。
固定値の `round:3` ではなく、**`state["round"]` (または発生時点の実際の試行数)** を動的に `tasks.md` 内のメタデータへ書き込む。これにより、`max_round` が可変（例: 5）であっても `check-blockers.py` の `B7` 判定条件（`round >= max_round`）が正確に判定される。

```python
def escalate_node(state: OrchestratorState) -> OrchestratorState:
    """レビュー/テスト/lint の試行回数上限到達時に tasks.md を動的更新し、B7 ブロッカー化させる"""
    actual_round = max(state["round"], state["lint_round"], state["test_round"])
    logger.error(f"Issue {state['issue_id']} がリトライ上限 ({actual_round}/{state['max_round']}) に達しました。B7ブロッカー化します。")
    # [F2修正] 固定値 'round:3' ではなく動的な actual_round を書き込む
    update_task_metadata(state["project_path"], state["issue_id"], round_num=actual_round)
    return state
```

---

## 5. テスト・検証設計

1. **`test_orchestrator_graph.py`**: LangGraph の各ノード（`plan` → `code` → `lint` → `test` → `review` → `done`/`escalate`）の状態遷移経路および `lint_round`/`test_round` 超過時の `escalate` 経路テスト。
2. **`test_llm_client.py`**: LiteLLM 呼び出しおよび壊れた JSON レスポンス時の安全フォールバックテスト。
3. **`test_aider_runner.py`**: `--no-auto-commits` （複数形）が常に付加されること、タイムアウト時に `AiderRunError` を送出することの検証。