# Second Brain OS - Agent制御アーキテクチャ Rev.3.0

OpenCode × ローカルLLM（Ollama）による オフライン完結型「第二の脳」プロジェクト管理システム

## 📋 概要

本プロジェクトは、完全オフライン環境でAIエージェントを活用したプロジェクト管理を実現するシステムです。

**Rev.3.0の主要改善点**:
- ✅ エージェント間コンテキスト断絶の解消
- ✅ ハルシネーション抑制
- ✅ Python側でのエラーハンドリング・リトライ制御
- ✅ テスタビリティの向上

---

## 🏗️ アーキテクチャ

### Rev.3.0 アーキテクチャ概要

```
[ ユーザー ]
    ↓
[ OpenCode (直接対話) ]
    ↓
[ Ollama API (ローカルLLM) ]

[ Python Orchestrator Layer (新規) ]
├── orchestrator.py      全体制御
├── agent_client.py      OpenCode CLI呼び出し
├── context_manager.py   コンテキスト共有
└── prompt_builder.py    プロンプト構築
    ↓
[ Git リポジトリ ]
```

### 主要コンポーネント

| モジュール                 | 役割                           |
| -------------------------- | ------------------------------ |
| `tools/orchestrator.py`    | Issue実行の全体フロー制御      |
| `tools/agent_client.py`    | OpenCode CLI呼び出しラッパー   |
| `tools/context_manager.py` | エージェント間コンテキスト共有 |
| `tools/prompt_builder.py`  | エージェント別プロンプト構築   |

---

## 🚀 使い方

### 1. Issue実行（Python Orchestrator経由）

```bash
# ドライラン（ファイル書き込みなし）
python tools/orchestrator.py execute --issue-id ARCH-001 --dry-run

# 実行（ファイル書き込み + テスト実行）
python tools/orchestrator.py execute --issue-id ARCH-001
```

### 2. エージェント直接呼び出し（テスト用）

```bash
# Executorエージェントを呼び出し
python tools/agent_client.py executor "Issue ARCH-001を実装してください"

# Coderエージェントを呼び出し
python tools/agent_client.py coder "tools/example.py を実装"
```

### 3. コンテキスト管理

```python
from tools.context_manager import SharedContext, ContextSerializer

# コンテキスト作成
ctx = SharedContext()
ctx.set_issue_id("ARCH-001")
ctx.add_requirement("title", "オーケストレーター実装")
ctx.add_constraint("external_modules_forbidden", True)

# サマリー生成（プロンプトに埋め込み）
summary = ctx.get_summary()

# ファイル保存
ContextSerializer.save(ctx, Path("context.json"))
```

---

## 🧪 テスト

### テストファイル一覧

```
tests/
├── test_orchestrator.py       orchestrator.py のテスト
├── test_agent_client.py       agent_client.py のテスト
├── test_context_manager.py    context_manager.py のテスト
└── test_prompt_builder.py     prompt_builder.py のテスト
```

### テスト実行（pytest必要）

```bash
# 全テスト実行
pytest tests/ -v

# 特定モジュールのテスト
pytest tests/test_context_manager.py -v

# カバレッジ付き実行
pytest tests/ --cov=tools --cov-report=html
```

---

## 📚 設計ドキュメント

### 主要ドキュメント

| ドキュメント                             | 内容                             |
| ---------------------------------------- | -------------------------------- |
| `docs/基本設計書.md`                     | Rev.3.0 基本設計                 |
| `docs/Python_Orchestrator_詳細設計書.md` | 新規モジュール詳細設計           |
| `AGENTS.md`                              | エージェント共通ルール（要更新） |
| `tasks.md`                               | タスク管理（本プロジェクト用）   |

---

## 🔧 開発環境

### 必要なツール

- Python 3.10以上
- OpenCode CLI
- Ollama (ローカルLLM実行環境)
- pytest (テスト実行用)

### 推奨LLMモデル

- gemma4-12b-it-Q4_K_M (デフォルト)
- qwen3.6-35B-A3B-UD-IQ4_XS

---

## 📝 タスク管理

### タスクの追加

```bash
# フラットタスク登録
python tools/add-task.py . "[ARCH-011] 新機能実装" --priority high

# サブタスク登録
python tools/add-task.py . "サブタスク内容" --parent ARCH-011 --priority medium
```

### タスク確認

```bash
# tasks.md を直接確認
cat tasks.md
```

---

## 🎯 使用例

### Example 1: Issue実行の全体フロー

```python
from tools.orchestrator import IssueOrchestrator

orchestrator = IssueOrchestrator()
result = orchestrator.execute_issue("ARCH-001")

if result.success:
    print(f"✓ 成功: {len(result.files_changed)}個のファイルを変更")
    print(f"✓ テスト: {'PASSED' if result.test_result.passed else 'FAILED'}")
else:
    print(f"✗ 失敗: {result.error_log}")
```

### Example 2: カスタムプロンプト構築

```python
from tools.prompt_builder import PromptBuilder
from tools.orchestrator import Requirements, Constraints

builder = PromptBuilder()

requirements = Requirements(
    issue_id="CUSTOM-001",
    title="カスタム機能",
    description="説明",
    project_path=Path("."),
    related_files=[],
    priority="high"
)

constraints = Constraints(
    external_modules_forbidden=True,
    allowed_imports=["sys", "os"]
)

prompt = builder.build_implementation_prompt(requirements, constraints)
print(prompt)
```

---

## 🔄 Rev.2.0 からの移行

### 主な変更点

1. **エージェント連携**: LLM内部 → Python側制御
2. **コンテキスト管理**: LLMセッション依存 → SharedContext一元管理
3. **エラー処理**: LLM任せ → Python側リトライ・フォールバック

### 移行手順

1. 新規Pythonモジュール（orchestrator等）の配置 ✅
2. AGENTS.mdの改訂（Python管理前提への変更）
3. 既存ワークフローの段階的移行
4. 並行運用期間を設けて検証

---

## 🐛 トラブルシューティング

### OpenCode CLIが見つからない

```bash
# PATHにopencodeが含まれているか確認
which opencode  # Linux/Mac
where opencode  # Windows

# 見つからない場合は、agent_client.pyで明示的にパス指定
client = AgentClient(opencode_bin="/path/to/opencode")
```

### コンテキストが大きすぎる

```python
# 中間結果をクリア
ctx.clear_intermediate_results()

# サマリー最大長を制限
summary = ctx.get_summary(max_length=1000)
```

### テストがタイムアウトする

```python
# タイムアウト時間を延長
orchestrator._run_tests(project_path)  # デフォルト120秒

# subprocess.runのtimeout引数を調整（orchestrator.py内）
```

---

## 🤝 貢献

本プロジェクトは個人ナレッジマネジメント用途を想定していますが、改善提案は歓迎します。

---

## 📄 ライセンス

プロジェクトのライセンスに従います。

---

## 📞 サポート

質問や問題が発生した場合は、`docs/knowledge/failures.md` にナレッジとして記録してください。

---

**Last Updated**: 2026-07-06  
**Version**: Rev.3.0
