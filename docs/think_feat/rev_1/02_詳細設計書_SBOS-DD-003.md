# 詳細設計書（コンポーネント内部仕様・データ構造・インターフェース）
**Python Orchestrator × 共有コンテキスト × レビュー自己修復 統合内部仕様**

| 項目 | 内容 |
| :--- | :--- |
| 文書番号 | SBOS-DD-003 |
| 版数 | Rev.3.1 |
| 作成日 | 2026年7月27日 |
| 対象読者 | システム開発エンジニア / コンポーネント実装者 / 保守担当者 |
| 関連文書 | SBOS-BD-002（基本設計書）、SBOS-ORCH-001（オーケストレイト設計書） |

---

## 1. コアコンポーネント詳細設計

Python Orchestrator Layer (`tools/` 配下) を構成する中核4モジュールのクラス構造、データモデル、メソッドシグネチャ、例外処理を規定する。

### 1.1 `context_manager.py` (`SharedContext` クラス)
各LLMエージェントの単発呼び出し（独立したセッション）の間で、プロジェクトの前提要件、設計制約、実行ステップ結果、エラーログを引き継ぐためのインメモリ状態管理コンポーネント。

#### データモデルおよびクラス属性仕様
```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class ExecutionStepResult:
    step_name: str                  # ステップ識別子 (例: "requirement_gathering", "lint_check")
    timestamp: datetime             # 実行完了日時
    data: Any                       # 出力データ (文字列、辞書、テスト結果オブジェクト等)
    success: bool                   # 成否フラグ
    error_message: Optional[str] = None # エラー時のメッセージ

class SharedContext:
    def __init__(self, issue_id: str, project_key: str, project_path: str):
        self.issue_id: str = issue_id
        self.project_key: str = project_key
        self.project_path: str = project_path
        self.requirements: Dict[str, Any] = {}
        self.constraints: List[str] = []
        self.intermediate_results: List[ExecutionStepResult] = []
        self.error_history: List[Dict[str, Any]] = []
        self.review_history: List[Dict[str, Any]] = []
        self.file_snapshots: Dict[str, str] = {} # filepath -> initial content before modification
```

#### 主要メソッドとアルゴリズム
- `add_step_result(step_name: str, data: Any, success: bool = True, error_msg: Optional[str] = None) -> None`:
  各処理フェーズの実行結果を `intermediate_results` に追記する。失敗時は `error_history` にも自動登録する。
- `record_file_snapshot(filepath: str, content: str) -> None`:
  コード書き込みを行う直前のオリジナルソースコードをスナップショットとしてメモリに保存する。このデータは、後段の Reviewer Agent が Git に依存せずに書き込み前後の unified diff を計算するために必須となる。
- `get_summary_for_prompt(max_tokens_approx: int = 3500) -> str`:
  次のエージェントのプロンプトに注入するためのコンテキストサマリー文字列を生成する。
  **トークン溢れ防止（クリッピング）アルゴリズム:**
  生成した文字列全体の文字数をカウントし、`len(text) / 1.5 > max_tokens_approx` の条件に合致した場合、以下の優先度で古い情報を自動除外する。
  1. `intermediate_results` のうち、過去の成功した Linter やテストの標準出力ログを削除。
  2. `error_history` のうち、直近2回よりも前の古いスタックトレースを切り捨て。
  3. 最新の「実装指示書（仕様）」と直近の「エラー分類・レビュー指摘」を最優先で維持し、コンテキスト窓の破綻を保証する。
- `clear_intermediate_data() -> None`:
  レビュー差し戻しやリトライの再開始時に呼び出され、前回の試行で失敗したコードブロックの中間生成アセットのみを破棄する。基本要件（`requirements`）と仕様制約（`constraints`）は維持する。

---

### 1.2 `agent_client.py` (`AgentClient` クラス)
OpenCode CLI をサブプロセスとしてセキュアかつ決定論的に呼び出すためのローカルプロキシラッパー。

#### クラス定義と初期化パラメータ
```python
import subprocess
import json
import time
import logging
from typing import Optional, Dict, Any, Union

class AgentCallError(Exception):
    """LLMエージェントの呼び出し、タイムアウト、または致命的なパース失敗時に送出される例外"""
    pass

class AgentClient:
    def __init__(self, opencode_bin: str = "opencode", default_timeout: int = 300, max_retries: int = 3):
        self.opencode_bin = opencode_bin
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
```

#### 主要メソッド仕様と実行ロジック
- `call_agent(agent_name: str, prompt: str, timeout: Optional[int] = None, expect_json: bool = False) -> Union[str, Dict[str, Any]]`:
  指定されたエージェント（`executor`, `coder`, `reviewer`）に対し、標準入力を介してプロンプトを渡し、実行結果のテキストまたはパース済みJSONを返す。
  **実行コマンド構成:**
  ```bash
  opencode run --agent <agent_name> --format json
  ```
  ※ プロンプト文字列の引数渡しは OS コマンドインジェクションの脆弱性を生むため、必ず `subprocess.Popen(..., stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)` を用いて標準入力から UTF-8 で流し込む。

- `_parse_and_validate_response(raw_output: str, expect_json: bool) -> Union[str, Dict[str, Any]]`:
  LLMが出力した生の文字列から、有効なペイロードを抽出する。
  **決定論的自動リトライ・補正ロジック:**
  1. `expect_json=True` の場合、文字列中から最初の `{` と最後の `}` の間を正規表現 `r"(\{.*\})"` (dotall) で切り出し、`json.loads` を試行する。
  2. 閉じ括弧の欠落や末尾のカンマ違反等で `json.JSONDecodeError` が発生した場合、内部の修復パーサー（改行コードの整形や不完全なプロパティの除去）を走らせる。
  3. それでもパースに失敗した場合、最大 `max_retries`（デフォルト3回）まで1秒のバックオフを挟んで自動でパース試行を繰り返す。3回すべて失敗した場合は `AgentCallError` を送出し、上位の Orchestrator へエスカレーションする。
  4. `expect_json=False` の場合、マークダウンコードブロック（````python ... ```` や ````markdown ... ````）を抽出し、トリムした本文のみを返す。


---

### 1.3 `prompt_builder.py` (`PromptBuilder` クラス)
エージェントに送信するプロンプトを動的に組み立てる合成器。テンプレートエンジンに依存せず、Python の標準文字列操作で高速に構築する。

#### テンプレート自動読込とキャッシング
初期化時、`~/second-brain/.opencode/agents/` に存在するすべての `.md` ファイル（`executor.md`, `coder.md`, `reviewer.md`）を読み込み、ヘッダのメタデータを解析した上で、プレースホルダーを持つ本文をインメモリの辞書 `self.templates` へキャッシュする。

#### 動的合成メソッド仕様
- `build_implementation_prompt(requirements: Dict[str, Any], constraints: List[str], error_context: Optional[str] = None) -> str`:
  `executor.md` テンプレートをロードし、以下のプレースホルダーを展開する。
  - `{requirements}`: 収集された Issue のタイトル、説明、および依存タスクのサマリー。
  - `{constraints}`: プロジェクトのアーキテクチャ制約（使用言語フレームワーク、禁止ライブラリ等）。
  - `{error_context}`: リトライ時において、前回生成した指示書がなぜ棄却されたのかの理由。初回呼び出し時は空文字。

- `build_coding_prompt(impl_plan: str, target_files: List[str], error_log: Optional[str] = None) -> str`:
  `coder.md` テンプレートをロードし、Executor の実装指示書と編集対象のファイルリストを展開する。
  **フォーマット厳格化指示の自動追加:**
  プロンプトの最後尾に、以下の厳密なフォーマット制約文字列を自動追記する。
  ```text
  【厳密フォーマット指示】
  あなたはソースコードのみを出力するコード生成器です。挨拶、謝罪、言い訳、コードの解説などの自然言語は一切出力してはなりません。
  必ず以下の形式でコードブロックのみを出力し、先頭行にはファイルパスをコメントで記載してください。
  ```python
  # filepath: projects/<name>/src/example.py
  <実装コード>
  ```
  ```

- `build_review_prompt(impl_plan: str, diff_text: str, round_num: int) -> str`:
  `reviewer.md` テンプレートをロードし、実装指示書、`difflib.unified_diff` による差分テキスト、現在のラウンド数を埋め込む。

---

## 2. データ構造・ファイルスキーマ仕様

永続化層におけるタスク管理、衛星台帳、キャッシュ、実行監査ログの詳細スキーマを規定する。

### 2.1 `tasks.md` 行内コメント正規表現仕様
Markdown のタスクリスト行に HTML コメントとして埋め込まれるキーバリューメタデータの文法規則と抽出パーサー仕様。

#### 基本フォーマットと拡張キー
```markdown
- [/] [EC-012] 決済例外ロールバックハンドラの統合  <!-- priority:high parent:EC-010 blockedby:#EC-011 added:2026-07-27 round:1 max_round:3 -->
```

#### 抽出正規表現とデータ仕様
```python
import re
from typing import Dict, Any, Optional

TASK_LINE_REGEX = re.compile(
    r"^\s*-\s*\[([ x/])\]\s*\[([A-Z0-9]+-\d+)\]\s*(.*?)\s*<!--\s*(.*?)\s*-->\s*$"
)
META_KV_REGEX = re.compile(r"([a-z_]+):([^\s]+)")

def parse_task_line(line: str) -> Optional[Dict[str, Any]]:
    match = TASK_LINE_REGEX.match(line)
    if not match:
        return None
    
    status_char, issue_id, title, meta_str = match.groups()
    meta_dict = dict(META_KV_REGEX.findall(meta_str))
    
    # 状態マッピング
    status_map = {" ": "todo", "/": "in_progress", "x": "done"}
    
    return {
        "id": issue_id,
        "title": title.strip(),
        "status": status_map.get(status_char, "todo"),
        "priority": meta_dict.get("priority", "medium"),
        "parent": meta_dict.get("parent", None),
        "blockedby": meta_dict.get("blockedby", None),
        "added": meta_dict.get("added", None),
        "round": int(meta_dict.get("round", 1)),          # ⭐NEW: 現在のレビューラウンド
        "max_round": int(meta_dict.get("max_round", 3))   # ⭐NEW: レビュー上限試行回数
    }
```

---

### 2.2 衛星台帳および個別プロジェクト設定スキーマ

#### 母艦側台帳インデックス `projects/.project-registry.json` スキーマ
全衛星プロジェクトのプレフィックスと実パスをマッピングする JSON Schema (Draft 7)。
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ProjectRegistry",
  "type": "object",
  "patternProperties": {
    "^[A-Z0-9]{2,5}$": {
      "type": "string",
      "description": "母艦リポジトリルートからの相対ディレクトリパス (例: projects/ec-site)"
    }
  },
  "additionalProperties": false
}
```

#### 衛星側設定ファイル `project.json` スキーマ
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ProjectMetadata",
  "type": "object",
  "required": ["name", "key", "created_at", "default_branch"],
  "properties": {
    "name": { "type": "string", "description": "プロジェクトの人間可読名" },
    "key": { "type": "string", "pattern": "^[A-Z0-9]{2,5}$", "description": "プレフィックス" },
    "created_at": { "type": "string", "format": "date" },
    "default_branch": { "type": "string", "default": "main" },
    "test_command": { "type": "string", "default": "uv run pytest" },
    "lint_command": { "type": "string", "default": "uv run ruff check ." },
    "dependencies": { "type": "array", "items": { "type": "string" }, "default": [] }
  }
}
```

---

### 2.3 実行時キャッシュおよび監査ログデータ構造

#### 品質監査ログ `tools/.cache/execution_history.json` （レビュー拡張フォーマット）
1回の Issue 実行（試行〜成功または上限到達終了）につき1レコードが追記される NDJSON (Newline Delimited JSON) ファイル構造。
```json
{
  "issue_id": "EC-012",
  "project_key": "EC",
  "timestamp": "2026-07-27T15:30:45+09:00",
  "success": true,
  "final_state": "REVIEW_PASSED",
  "model_info": {
    "executor": "ollama/qwen2.5-coder:14b",
    "coder": "ollama/qwen2.5-coder:7b-16k",
    "reviewer": "ollama/qwen3:32b"
  },
  "files_changed": [
    "projects/ec-site/src/payments/rollback.py",
    "projects/ec-site/tests/test_rollback.py"
  ],
  "test_result": {
    "passed": true,
    "total_tests": 18,
    "failed_tests": 0,
    "duration_sec": 4.12
  },
  "review": {
    "total_rounds": 2,
    "rounds": [
      {
        "round": 1,
        "verdict": "changes_requested",
        "comment": "CONSTRAINT: トランザクションロールバック時にDBコネクションのクローズが保証されていません。try-finallyブロックで囲むかコンテキストマネージャを使用してください。",
        "timestamp": "2026-07-27T15:28:10+09:00"
      },
      {
        "round": 2,
        "verdict": "LGTM",
        "comment": "指摘したリソースクローズの漏れが修正され、すべてのテストが通過することを確認しました。仕様およびセキュリティ要件を満たしています。",
        "timestamp": "2026-07-27T15:30:45+09:00"
      }
    ]
  },
  "error_log": null
}
```

---

## 3. エージェントインターフェース仕様（プロンプト入出力）

各モデルが遵守すべき入力・出力プロトコルの境界とフォーマット検証ルール。

### 3.1 Executor（要件定義・詳細設計Agent）
- **入力:** Issue ID、タイトル、説明、依存先行タスクの概要、プロジェクト `README.md`、および関連するソースコードの概略文字列。
- **出力規定:** マークダウンフォーマットの「実装指示書」。以下の4セクションを必ず含むこと。
  1. `## 実装方針`: アプローチの概要と設計上の判断。
  2. `## 変更対象ファイルと関数`: 修正・追加すべき具体的なパスと関数名。
  3. `## 入出力仕様`: シグネチャ、引数名、データ型、戻り値の型。
  4. `## テストケース要件`: pytest で検証すべき正常系、異常系、バウンダリ条件。
- **検証禁止事項:** 実際のプログラミング言語の完全な実装ソースコードを含めてはならない（設計と実装の責務分離）。

### 3.2 Coder（コード実装Agent）
- **入力:** 実装指示書、書き込み前対象ファイルソースコード、および（リトライ時のみ）Linter/pytestの失敗エラーログまたは Reviewer の指摘コメント。
- **出力規定:** 実行可能なソースコードブロック。
  ```python
  # filepath: projects/ec-site/src/payments/rollback.py
  import logging
  ...
  ```
- **検証禁止事項:** 自然言語による会話、謝罪、解説テキストを出力してはならない。コードブロック以外の文字列が検出された場合、`agent_client.py` が自動的にトリムする。

### 3.3 Reviewer（客観的コード監査Agent）
- **入力:** 
  1. `impl_plan`: Executor が作成した実装指示書（正解となる仕様の定義）。
  2. `diff_text`: `difflib.unified_diff` で生成されたコード変更差分。
  3. `round_num`: 現在の試行ラウンド数。
- **出力規定:** 以下のスキーマに準拠する JSON オブジェクトのみを返却すること。
  ```json
  {
    "verdict": "LGTM" | "changes_requested",
    "summary": "監査結果の短い要約",
    "comments": [
      {
        "filepath": "projects/ec-site/src/payments/rollback.py",
        "line_range": "45-50",
        "category": "CONSTRAINT" | "SECURITY" | "BUG",
        "message": "具体的な違反内容と、どう修正すべきかの指示"
      }
    ]
  }
  ```

---

## 4. Tool Calling 制約と事前セキュリティチェック関数仕様

### 4.1 Python側事前セキュリティチェック実装
`orchestrator.py` は、Coder のコードをファイルへ書き込む直前に、以下の静的検証モジュールを実行する。

```python
import re
from typing import List, Tuple

UNSAFE_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+/"), "Root directory deletion attempted"),
    (re.compile(r"os\.system\(['"]rm\s+-rf"), "Destructive OS command via python"),
    (re.compile(r"http://[a-zA-Z0-9\-\.]+\.xyz"), "Suspicious external network request"),
    (re.compile(r"(pip|npm)\s+install\s+([a-zA-Z0-9\-_]+)"), "Dynamic package installation")
]

def verify_code_security(filepath: str, code_content: str) -> Tuple[bool, str]:
    """コードをディスクに書き込む前にセキュリティ違反や攻撃パターンを検知する。
    戻り値: (安全であればTrue, 違反メッセージ)
    """
    for pattern, message in UNSAFE_PATTERNS:
        match = pattern.search(code_content)
        if match:
            if "install" in message:
                pkg_name = match.group(2)
                # サプライチェーン攻撃防止のためのクールダウン期間確認スタブ
                return False, f"Security Violation: Dynamic package install detected ({pkg_name})."
            else:
                return False, f"Security Violation in {filepath}: {message}"
    return True, "OK"
```