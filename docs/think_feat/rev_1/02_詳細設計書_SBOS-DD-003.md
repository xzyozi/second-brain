# 詳細設計書（コンポーネント詳細・データフロー・実装仕様）
**LangGraph / LiteLLM / Aider / Ruff / Reviewdog 統合実装仕様**

| 項目     | 内容                                                           |
| :------- | :--------------------------------------------------------------- |
| 文書番号 | SBOS-DD-003                                                      |
| 版数     | Rev.4.0（LangGraph/LiteLLM/Aider/Ruff/Reviewdog 統合実装仕様版） |
| 改訂日   | 2026年7月28日                                                     |
| 作成日   | 2026年7月27日                                                     |
| 関連文書 | SBOS-BD-002（基本設計書 Rev.4.0）、SBOS-MULTI-001 Rev.2.1、SBOS-OP-001 Rev.3.3、SBOS-OSS-001/002 |
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

    round: int
    max_round: int
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
"""tools/aider_runner.py - Aiderサブプロセス起動"""
import os, subprocess, logging
from pathlib import Path

def run_aider(project_path: Path, message: str, model: str = "ollama/qwen2.5-coder:7b-16k", timeout: int = 600) -> str:
    env = os.environ.copy()
    env["OLLAMA_API_BASE"] = "http://localhost:11434"
    cmd = ["aider", "--message", message, "--model", model, "--no-auto-commit", "--yes-always", "--no-stream"]
    res = subprocess.run(cmd, cwd=str(project_path), env=env, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"Aider failed: {res.stderr}")
    return get_git_diff(project_path)

def get_git_diff(project_path: Path) -> str:
    return subprocess.run(["git", "diff", "HEAD"], cwd=str(project_path), capture_output=True, text=True).stdout
```

---

## 4. LangGraph グラフ構築と条件分岐ロジック

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

    g.add_conditional_edges("lint", lambda s: "test" if s["lint_result"]["passed"] else "code", {"test": "test", "code": "code"})
    g.add_conditional_edges("test", lambda s: "review" if s["test_result"]["passed"] else "code", {"review": "review", "code": "code"})

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

### 4.1 B7 ブロッカー判定と `escalate_node`
`escalate_node` はレビューの上限回数（`max_round`）に達した際に呼ばれ、`tasks.md` 内の該当 Issue 行のメタデータを `round:3` に書き換えることで、翌朝の `check-blockers.py` スキャンで **`B7` ブロッカー** として自動検知・エスカレーションされる。

---

## 5. テスト・検証設計

1. **`test_orchestrator_graph.py`**: LangGraph の各ノード（`plan` → `code` → `lint` → `test` → `review` → `done`/`escalate`）の状態遷移経路テスト。
2. **`test_llm_client.py`**: LiteLLM 呼び出しおよび壊れた JSON レスポンス時の安全フォールバックテスト。
3. **`test_aider_runner.py`**: `--no-auto-commit` フラグおよびタイムアウト処理テスト。