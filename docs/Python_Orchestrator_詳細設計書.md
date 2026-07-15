# Python Orchestrator 詳細設計書
**Agent制御アーキテクチャ Rev.3.0 実装仕様**

| 項目     | 内容                           |
| :------- | :----------------------------- |
| 文書番号 | SBOS-DD-002                    |
| 版数     | Rev.1.0                        |
| 作成日   | 2026年7月6日                   |
| 対象読者 | システム開発者                 |
| 前提文書 | SBOS-BD-001 基本設計書 Rev.3.0 |

---

## 1. 概要

本書は、基本設計書 Rev.3.0 で定義された「Python側オーケストレーション化」の実装詳細を規定する。
従来はエージェント間の連携をLLM内部で行っていたが、Rev.3.0では以下4つのPythonモジュールを新規作成し、制御ロジックを外部化する。

### 1.1 新規モジュール一覧

| モジュール名               | 役割                           | 主要クラス/関数                        |
| -------------------------- | ------------------------------ | -------------------------------------- |
| `tools/orchestrator.py`    | Issue実行の全体フロー制御      | `IssueOrchestrator`, `execute_issue()` |
| `tools/agent_client.py`    | OpenCode CLI呼び出しラッパー   | `AgentClient`, `call_agent()`          |
| `tools/context_manager.py` | エージェント間コンテキスト共有 | `SharedContext`, `ContextSerializer`   |
| `tools/prompt_builder.py`  | エージェント別プロンプト構築   | `PromptBuilder`, `build_*_prompt()`    |

---

## 2. orchestrator.py 設計

### 2.1 役割

Issue実行の全体フローを統括する。従来Executorエージェント（LLM）が担当していた「他エージェントへの委譲判断」「結果の統合」をPython側で決定論的に実行する。

### 2.2 クラス設計

```python
class ExecutionResult:
    """Issue実行結果"""
    success: bool
    issue_id: str
    context: SharedContext
    error_log: Optional[str]
    files_changed: List[Path]
    test_result: Optional[TestResult]

class IssueOrchestrator:
    """Issue実行のメインコントローラー"""
    
    def __init__(self, agent_client: AgentClient, context_mgr: ContextManager):
        self.agent_client = agent_client
        self.context_mgr = context_mgr
        self.prompt_builder = PromptBuilder()
    
    def execute_issue(self, issue_id: str, max_retries: int = 2) -> ExecutionResult:
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
            
        Returns:
            ExecutionResult: 実行結果の詳細
        """
        pass
    
    def _gather_requirements(self, issue_id: str) -> Requirements:
        """Issue関連の要件を収集"""
        pass
    
    def _verify_constraints(self, requirements: Requirements) -> Constraints:
        """制約条件を検証（外部モジュール禁止等）"""
        pass
    
    def _generate_implementation_plan(
        self, 
        requirements: Requirements,
        constraints: Constraints
    ) -> ImplementationPlan:
        """ExecutorエージェントLLMを呼び出して実装指示書を生成"""
        pass
    
    def _generate_code(
        self, 
        impl_plan: ImplementationPlan,
        constraints: Constraints
    ) -> GeneratedCode:
        """CoderエージェントLLMを呼び出してコード生成"""
        pass
    
    def _write_files(self, generated_code: GeneratedCode) -> WriteResult:
        """生成されたコードをファイルに書き込む"""
        pass
    
    def _run_tests(self, project_path: Path) -> TestResult:
        """pytestを実行してテスト結果を取得"""
        pass
```

### 2.3 エラーハンドリング

```python
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
    def __init__(self, test_result: TestResult):
        self.test_result = test_result
        super().__init__(f"Tests failed: {test_result.summary}")
```

---

## 3. agent_client.py 設計

### 3.1 役割

OpenCode CLI (`opencode run --agent <name> "<prompt>"`) の呼び出しをラップし、レスポンスのパースを統一的に処理する。

### 3.2 クラス設計

```python
class AgentResponse:
    """エージェント応答の構造化データ"""
    raw_output: str
    parsed_data: Dict[str, Any]
    success: bool
    error_message: Optional[str]
    execution_time: float

class AgentClient:
    """OpenCode CLIの呼び出しクライアント"""
    
    def __init__(self, timeout: int = 300):
        self.timeout = timeout  # 秒単位のタイムアウト
        self.call_history = []  # デバッグ用の呼び出し履歴
    
    def call_agent(
        self,
        agent_name: str,
        prompt: str,
        context: Optional[SharedContext] = None,
        max_retries: int = 3
    ) -> AgentResponse:
        """
        OpenCode CLIを呼び出してエージェントを実行
        
        実行コマンド:
        opencode run --agent {agent_name} "{prompt}"
        
        Args:
            agent_name: エージェント名（executor, coder等）
            prompt: エージェントに渡すプロンプト
            context: 共有コンテキスト（プロンプトに埋め込まれる）
            max_retries: 失敗時のリトライ回数
            
        Returns:
            AgentResponse: パース済みの応答データ
            
        Raises:
            AgentCallError: 呼び出しが max_retries 回失敗した場合
        """
        pass
    
    def _execute_opencode_cli(self, agent_name: str, prompt: str) -> subprocess.CompletedProcess:
        """subprocess でOpenCode CLIを実行"""
        pass
    
    def _parse_response(self, raw_output: str, agent_name: str) -> Dict[str, Any]:
        """エージェント応答をパース（Markdown/JSON混在に対応）"""
        pass
    
    def _validate_response(self, parsed_data: Dict[str, Any], agent_name: str) -> bool:
        """応答データの妥当性検証"""
        pass
```

### 3.3 レスポンスパース戦略

エージェントの応答はMarkdownとJSON が混在するため、パターンマッチングで抽出する。

```python
def _parse_response(self, raw_output: str, agent_name: str) -> Dict[str, Any]:
    """
    パターン:
    - Executorの応答: 「## 実装指示書」セクションを抽出
    - Coderの応答: ```python ... ``` コードブロックを抽出
    - エラー時: "ERROR:" で始まる行を検出
    """
    result = {}
    
    # Executorの実装指示書パース
    if agent_name == "executor":
        match = re.search(r'## 実装指示書\n(.*?)(?=\n##|\Z)', raw_output, re.DOTALL)
        if match:
            result["implementation_plan"] = match.group(1).strip()
    
    # Coderのコードブロックパース
    elif agent_name == "coder":
        code_blocks = re.findall(r'```python\n(.*?)\n```', raw_output, re.DOTALL)
        result["generated_code"] = code_blocks
    
    # エラー検出
    error_lines = [line for line in raw_output.split('\n') if line.startswith('ERROR:')]
    if error_lines:
        result["error"] = '\n'.join(error_lines)
    
    return result
```

---

## 4. context_manager.py 設計

### 4.1 役割

エージェント間で共有するコンテキスト情報を管理する。従来は各LLMセッションが独立していたため文脈が失われていたが、Python側で明示的に保持する。

### 4.2 クラス設計

```python
class SharedContext:
    """全エージェント間で共有するコンテキスト"""
    
    def __init__(self):
        self.issue_id: Optional[str] = None
        self.requirements: Dict[str, Any] = {}
        self.constraints: Dict[str, Any] = {}
        self.intermediate_results: List[Dict[str, Any]] = []
        self.error_history: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
    
    def add(self, key: str, value: Any, category: str = "intermediate"):
        """コンテキストに情報を追加"""
        entry = {
            "key": key,
            "value": value,
            "category": category,
            "timestamp": datetime.now().isoformat()
        }
        self.intermediate_results.append(entry)
    
    def get_summary(self, max_length: int = 2000) -> str:
        """プロンプトに埋め込む用のサマリー文字列を生成"""
        summary = f"""
# 共有コンテキスト

## Issue情報
- Issue ID: {self.issue_id}

## 要件
{self._format_dict(self.requirements)}

## 制約条件
{self._format_dict(self.constraints)}

## これまでの処理
{len(self.intermediate_results)}ステップ実行済み
"""
        # トークン数制限のため、max_lengthで切り詰め
        return summary[:max_length]
    
    def add_error(self, phase: str, error: Exception):
        """エラー履歴を記録"""
        self.error_history.append({
            "phase": phase,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """dict形式に変換（ファイル保存用）"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SharedContext':
        """dict形式から復元"""
        pass


class ContextSerializer:
    """コンテキストのファイル保存・読み込み"""
    
    @staticmethod
    def save(context: SharedContext, filepath: Path):
        """コンテキストをJSONファイルに保存"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load(filepath: Path) -> SharedContext:
        """JSONファイルからコンテキストを読み込み"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return SharedContext.from_dict(data)
```

---

## 5. prompt_builder.py 設計

### 5.1 役割

エージェント別に最適化されたプロンプトを動的構築する。`.opencode/agents/` 配下のテンプレートに、実行時情報（要件、制約、コンテキスト）を統合する。

### 5.2 クラス設計

```python
class PromptBuilder:
    """エージェント別プロンプト構築"""
    
    def __init__(self, agents_dir: Path = Path(".opencode/agents")):
        self.agents_dir = agents_dir
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """エージェント定義ファイル（.md）をテンプレートとして読み込み"""
        templates = {}
        for md_file in self.agents_dir.glob("*.md"):
            agent_name = md_file.stem
            templates[agent_name] = md_file.read_text(encoding='utf-8')
        return templates
    
    def build_implementation_prompt(
        self,
        requirements: Requirements,
        constraints: Constraints,
        context: Optional[SharedContext] = None
    ) -> str:
        """Executor用の実装指示書生成プロンプトを構築"""
        base_template = self.templates.get("executor", "")
        
        prompt = f"""
{base_template}

# 実行指示

## Issue情報
- Issue ID: {requirements.issue_id}
- タイトル: {requirements.title}
- 説明: {requirements.description}

## 要件詳細
{self._format_requirements(requirements)}

## 制約条件（必須遵守）
{self._format_constraints(constraints)}

## 共有コンテキスト
{context.get_summary() if context else "なし"}

---

上記情報を元に、「実装指示書」を生成してください。
実装指示書には以下を含めること:
1. 作成・編集すべきファイルパスのリスト
2. 各ファイルで実装すべき内容の詳細
3. テストケースの作成方針
"""
        return prompt
    
    def build_coding_prompt(
        self,
        impl_plan: ImplementationPlan,
        constraints: Constraints,
        context: Optional[SharedContext] = None
    ) -> str:
        """Coder用のコード生成プロンプトを構築"""
        base_template = self.templates.get("coder", "")
        
        prompt = f"""
{base_template}

# コード生成指示

## 実装指示書
{impl_plan.content}

## 制約条件（必須遵守）
{self._format_constraints(constraints)}

## 共有コンテキスト
{context.get_summary() if context else "なし"}

---

上記の実装指示書に従い、Pythonコードを生成してください。
各ファイルごとに ```python ファイルパス ``` 形式のコードブロックで出力すること。

例:
\```python
# filepath: tools/example.py
def example():
    pass
\```
"""
        return prompt
    
    def _format_requirements(self, requirements: Requirements) -> str:
        """要件を整形"""
        pass
    
    def _format_constraints(self, constraints: Constraints) -> str:
        """制約を整形"""
        pass
```

---

## 6. データモデル

### 6.1 共通データ構造

```python
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
    files: Dict[Path, str]  # filepath -> content
    metadata: Dict[str, Any]

@dataclass
class TestResult:
    """テスト実行結果"""
    passed: bool
    total_tests: int
    failed_tests: int
    error_log: str
    duration: float
```

---

## 7. 実装優先度

### Phase 1: 基本機能（ARCH-004～ARCH-007）
1. `agent_client.py` - OpenCode CLI呼び出しとレスポンスパース
2. `context_manager.py` - SharedContextの基本機能
3. `prompt_builder.py` - Executor/Coder用プロンプト構築
4. `orchestrator.py` - 基本的なIssue実行フロー

### Phase 2: エラーハンドリング強化
5. リトライロジックの実装
6. 制約違反チェックの実装
7. テスト失敗時の自動修正ループ

### Phase 3: テスト・最適化（ARCH-008）
8. 単体テストの実装
9. 統合テストの実装
10. パフォーマンス最適化

---

## 8. 移行戦略

### 8.1 既存システムとの共存

Rev.3.0実装中も、既存のExecutor/Coderエージェント（LLM内連携）は保持する。
新システムは別のエントリポイント（例: `/work-v3 <issue_id>`）として提供し、段階的に移行する。

### 8.2 移行手順

1. **Week 1**: agent_client, context_manager の実装・単体テスト
2. **Week 2**: prompt_builder, orchestrator の実装
3. **Week 3**: 統合テスト・バグ修正
4. **Week 4**: 実環境での試験運用（並行運用）
5. **Week 5**: 既存システムからの完全切り替え

---

## 9. 補足資料

### 9.1 ディレクトリ構造

```
tools/
├── orchestrator.py          ⭐NEW
├── agent_client.py          ⭐NEW
├── context_manager.py       ⭐NEW
├── prompt_builder.py        ⭐NEW
├── add-task.py              (既存)
├── update-roadmap.py        (既存)
└── ...

tests/
├── test_orchestrator.py     ⭐NEW
├── test_agent_client.py     ⭐NEW
├── test_context_manager.py  ⭐NEW
└── ...

.opencode/agents/
├── executor.md              (テンプレート化)
├── coder.md                 (テンプレート化)
└── ...
```

### 9.2 ログ出力設計

```python
import logging

# tools/ 配下の全モジュールで統一されたロガーを使用
logger = logging.getLogger("second_brain.orchestrator")
logger.setLevel(logging.DEBUG)

# ログファイル: logs/orchestrator_{日付}.log
handler = logging.FileHandler(f"logs/orchestrator_{date.today()}.log")
formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

---

**作成日**: 2026年7月6日  
**作成者**: Second Brain OS Development Team
