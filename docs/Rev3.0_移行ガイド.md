# Rev.3.0 移行ガイド
**Second Brain OS - Python側オーケストレーション化への移行**

| 項目     | 内容           |
| :------- | :------------- |
| 文書番号 | SBOS-MG-001    |
| 版数     | Rev.1.0        |
| 作成日   | 2026年7月6日   |
| 対象読者 | システム運用者 |

---

## 📋 目次

1. [移行の概要](#1-移行の概要)
2. [主な変更点](#2-主な変更点)
3. [移行前の準備](#3-移行前の準備)
4. [段階的移行手順](#4-段階的移行手順)
5. [並行運用期間](#5-並行運用期間)
6. [完全移行後の運用](#6-完全移行後の運用)
7. [トラブルシューティング](#7-トラブルシューティング)

---

## 1. 移行の概要

### 1.1 移行の目的

Rev.2.0では、エージェント間の連携がLLM内部で行われていたため、以下の問題がありました:

| 問題                 | Rev.2.0                  | Rev.3.0での解決                    |
| -------------------- | ------------------------ | ---------------------------------- |
| **コンテキスト断絶** | 各LLMセッションが独立    | SharedContextで一元管理            |
| **ハルシネーション** | エージェント間で認識ズレ | Python側で明示的プロンプト構築     |
| **エラー伝搬困難**   | LLM任せ                  | Python側でリトライ・フォールバック |
| **テスト不可能**     | LLM内部ロジック          | Pythonコードで単体・統合テスト     |

### 1.2 移行の影響範囲

| 影響度 | コンポーネント                 | 変更内容                                     |
| ------ | ------------------------------ | -------------------------------------------- |
| **高** | `AGENTS.md`                    | Python側制御を前提とした記述に更新           |
| **高** | `.opencode/agents/executor.md` | Coder委譲削除、実装指示書生成のみ            |
| **高** | `.opencode/agents/coder.md`    | ファイル書き込み削除、コードブロック出力のみ |
| **中** | Issue実行フロー                | Python Orchestrator経由に変更                |
| **低** | 直接対話（PM/Sisyphus）        | 変更なし                                     |

---

## 2. 主な変更点

### 2.1 アーキテクチャの変更

#### Before (Rev.2.0)

```
[ OpenCode ]
  ↓ (LLM内部で連携)
[ Executor Agent ]
  ↓ opencode run --agent coder
[ Coder Agent ]
  ↓
[ ファイル書き込み ]
```

#### After (Rev.3.0)

```
[ Python Orchestrator ]
  ├─ 1. Issue情報読み込み
  ├─ 2. 制約検証
  ├─ 3. Executor呼び出し (実装指示書生成)
  ├─ 4. Coder呼び出し (コード生成)
  ├─ 5. ファイル書き込み
  ├─ 6. テスト実行
  └─ 7. 結果記録
```

### 2.2 エージェントの役割変更

| エージェント | Rev.2.0                          | Rev.3.0                    |
| ------------ | -------------------------------- | -------------------------- |
| **Executor** | Issue実行・Coder委譲・テスト実行 | **実装指示書生成のみ**     |
| **Coder**    | コード生成・ファイル書き込み     | **コードブロック出力のみ** |

### 2.3 新規追加コンポーネント

| ファイル                   | 役割                 |
| -------------------------- | -------------------- |
| `tools/orchestrator.py`    | Issue実行の全体制御  |
| `tools/agent_client.py`    | OpenCode CLI呼び出し |
| `tools/context_manager.py` | コンテキスト共有     |
| `tools/prompt_builder.py`  | プロンプト構築       |

---

## 3. 移行前の準備

### 3.1 環境確認

#### 必須要件

```bash
# Python 3.10以上
python --version

# OpenCode CLI
opencode --version

# Ollama
curl http://localhost:11434/api/version

# pytest（テスト実行用）
pytest --version
```

#### 推奨要件

- Git（バージョン管理）
- エディタ（VS Code等）

### 3.2 バックアップ

移行前に以下をバックアップしてください:

```bash
# 重要ファイルのバックアップ
cp AGENTS.md AGENTS.md.rev2.0.bak
cp .opencode/agents/executor.md .opencode/agents/executor.md.rev2.0.bak
cp .opencode/agents/coder.md .opencode/agents/coder.md.rev2.0.bak

# tasks.md とroadmap.md
cp tasks.md tasks.md.bak
cp roadmap.md roadmap.md.bak
```

### 3.3 新規ファイルの配置

```bash
# tools/ 配下に新規Pythonモジュールが配置されていることを確認
ls -l tools/orchestrator.py
ls -l tools/agent_client.py
ls -l tools/context_manager.py
ls -l tools/prompt_builder.py

# テストファイルの確認
ls -l tests/test_orchestrator.py
ls -l tests/test_agent_client.py
ls -l tests/test_context_manager.py
ls -l tests/test_prompt_builder.py
```

---

## 4. 段階的移行手順

### Phase 1: 準備フェーズ（1日目）

#### ステップ1: ドキュメント確認

- [ ] `README.md` を読む
- [ ] `docs/基本設計書.md` (Rev.3.0) を読む
- [ ] `docs/Python_Orchestrator_詳細設計書.md` を読む
- [ ] 本移行ガイドを読む

#### ステップ2: 新規ファイルの動作確認

```bash
# モジュールのインポートテスト
python -c "from tools.orchestrator import IssueOrchestrator; print('✓ orchestrator.py')"
python -c "from tools.agent_client import AgentClient; print('✓ agent_client.py')"
python -c "from tools.context_manager import SharedContext; print('✓ context_manager.py')"
python -c "from tools.prompt_builder import PromptBuilder; print('✓ prompt_builder.py')"
```

#### ステップ3: AGENTS.mdの更新

```bash
# Rev.3.0版のAGENTS.mdが配置されていることを確認
grep "Rev.3.0" AGENTS.md

# エージェント定義ファイルの確認
grep "Rev.3.0" .opencode/agents/executor.md
grep "Rev.3.0" .opencode/agents/coder.md
```

### Phase 2: 並行運用開始（2-3日目）

#### ステップ4: テストIssueでの検証

```bash
# 簡単なIssueを登録
python tools/add-task.py . "[TEST-001] Python Orchestrator動作確認" --priority high

# Python Orchestrator経由で実行（ドライラン）
python tools/orchestrator.py execute --issue-id TEST-001 --dry-run

# 結果確認
# - エラーが出ないか
# - 実装指示書が生成されるか
# - コードブロックが出力されるか
```

#### ステップ5: 実Issue での試験運用

```bash
# 実際のIssueで実行（本番）
python tools/orchestrator.py execute --issue-id ARCH-XXX

# 結果確認
# - ファイルが書き込まれたか
# - テストが通ったか
# - エラーハンドリングが動作したか
```

### Phase 3: 完全移行（4-5日目）

#### ステップ6: 旧フローの廃止

- [ ] Rev.2.0のExecutor→Coder自動委譲フローを使用停止
- [ ] Python Orchestrator経由を標準フローとして確立
- [ ] 運用ドキュメントを更新

#### ステップ7: 移行完了確認

- [ ] すべてのIssue実行がPython Orchestrator経由になった
- [ ] エラー発生時のリトライが機能している
- [ ] コンテキストが正しく共有されている
- [ ] テストが自動実行されている

---

## 5. 並行運用期間

### 5.1 並行運用の方針

Phase 2（2-3日目）では、Rev.2.0とRev.3.0を並行運用します。

| フロー                            | 用途                     | 推奨度   |
| --------------------------------- | ------------------------ | -------- |
| **Rev.3.0** (Python Orchestrator) | 新規Issue、重要Issue     | ⭐⭐⭐ 推奨 |
| **Rev.2.0** (Executor自動委譲)    | 緊急対応、フォールバック | ⚠️ 非推奨 |

### 5.2 並行運用時の注意点

#### 使い分け基準

| 条件                     | 使用フロー                    |
| ------------------------ | ----------------------------- |
| 通常のIssue実行          | Rev.3.0 (Python Orchestrator) |
| テスト検証が必要         | Rev.3.0 (Python Orchestrator) |
| エラーリトライが必要     | Rev.3.0 (Python Orchestrator) |
| 緊急で旧フローを使いたい | Rev.2.0 (一時的にのみ)        |

#### 切り替え方法

```bash
# Rev.3.0フロー（推奨）
python tools/orchestrator.py execute --issue-id ARCH-001

# Rev.2.0フロー（非推奨、緊急時のみ）
# OpenCode経由でExecutorを直接呼び出し
# （AGENTS.mdのバックアップ版を一時的に使用）
```

---

## 6. 完全移行後の運用

### 6.1 標準Issue実行フロー

```bash
# 1. Issueの登録
python tools/add-task.py . "[PROJ-001] 新機能実装" --priority high

# 2. Issue実行（Python Orchestrator経由）
python tools/orchestrator.py execute --issue-id PROJ-001

# 3. 結果確認
# - 実行結果が表示される
# - ファイルが書き込まれる
# - テストが自動実行される
# - 成功/失敗が明示される
```

### 6.2 エラー発生時の対応

#### ケース1: LLM応答のパース失敗

```bash
# エラーメッセージ例
ERROR: Agent response parse failed

# 対処:
# 1. リトライ（自動で3回まで試行）
# 2. それでも失敗する場合は、プロンプトを調整
```

#### ケース2: テスト失敗

```bash
# エラーメッセージ例
TestFailureError: Tests failed: ...

# 対処:
# 1. Coderに修正を依頼（自動で2回まで試行）
# 2. 手動で修正
```

#### ケース3: タイムアウト

```bash
# エラーメッセージ例
AgentCallError: Agent executor がタイムアウトしました

# 対処:
# 1. timeout値を延長（agent_client.pyのinitで指定）
# 2. Issueを分割して小さくする
```

### 6.3 ログとデバッグ

#### ログファイルの確認

```bash
# orchestrator.pyは標準出力にログを出力
python tools/orchestrator.py execute --issue-id ARCH-001 2>&1 | tee execution.log

# agent_clientの呼び出し履歴
# （agent_client.py内でsave_call_history()を呼び出す）
```

#### デバッグモード

```python
# orchestrator.py を編集
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 7. トラブルシューティング

### 7.1 よくある問題と解決策

#### 問題1: OpenCode CLIが見つからない

**症状**:
```
FileNotFoundError: opencode command not found
```

**解決策**:
```bash
# PATHを確認
which opencode  # Linux/Mac
where opencode  # Windows

# 見つからない場合、明示的にパスを指定
# agent_client.py で opencode_bin="/path/to/opencode" を指定
```

#### 問題2: コンテキストが大きすぎる

**症状**:
```
Token limit exceeded
```

**解決策**:
```python
# context_manager.py で中間結果をクリア
ctx.clear_intermediate_results()

# サマリー最大長を制限
summary = ctx.get_summary(max_length=1000)
```

#### 問題3: Executorが実装指示書を生成しない

**症状**:
Executor応答に「## 実装指示書」セクションがない

**解決策**:
```bash
# executor.mdが Rev.3.0版に更新されているか確認
grep "Rev.3.0" .opencode/agents/executor.md

# プロンプトを確認
# prompt_builder.pyのbuild_implementation_prompt()を確認
```

#### 問題4: Coderがコードブロックを出力しない

**症状**:
Coder応答に ```python ブロックがない

**解決策**:
```bash
# coder.mdが Rev.3.0版に更新されているか確認
grep "Rev.3.0" .opencode/agents/coder.md

# プロンプトに「# filepath:」の指示があるか確認
# prompt_builder.pyのbuild_coding_prompt()を確認
```

### 7.2 ロールバック手順

Rev.3.0で問題が発生した場合、Rev.2.0に戻すことができます。

```bash
# バックアップから復元
cp AGENTS.md.rev2.0.bak AGENTS.md
cp .opencode/agents/executor.md.rev2.0.bak .opencode/agents/executor.md
cp .opencode/agents/coder.md.rev2.0.bak .opencode/agents/coder.md

# OpenCodeを再起動（設定を再読み込み）
# ...

# Rev.2.0フローで動作確認
# （Executor→Coder自動委譲が復活）
```

### 7.3 サポートとフィードバック

#### 問題の記録

```bash
# 失敗情報をナレッジに記録
python tools/record-failure.py \
  --agent orchestrator \
  --phase "issue_execution" \
  --issue "実行中にタイムアウトが発生" \
  --action "timeout値を300→600に延長"
```

#### ドキュメント参照

- `README.md`: プロジェクト概要
- `docs/基本設計書.md`: Rev.3.0アーキテクチャ
- `docs/Python_Orchestrator_詳細設計書.md`: モジュール詳細
- `COMPLETION_REPORT.md`: 実装完了報告

---

## 8. 移行チェックリスト

### 事前準備

- [ ] Rev.3.0ドキュメントを読んだ
- [ ] 環境要件を満たしている
- [ ] バックアップを取得した
- [ ] 新規ファイルが配置されている

### Phase 1: 準備

- [ ] 新規モジュールのインポートテスト完了
- [ ] AGENTS.md が Rev.3.0版に更新されている
- [ ] エージェント定義ファイルが Rev.3.0版に更新されている

### Phase 2: 並行運用

- [ ] テストIssueでドライラン成功
- [ ] テストIssueで実行成功
- [ ] 実IssueでPython Orchestrator動作確認
- [ ] エラーハンドリング動作確認

### Phase 3: 完全移行

- [ ] 旧フロー（Rev.2.0）を使用停止
- [ ] Python Orchestratorを標準フローとして確立
- [ ] 運用ドキュメント更新
- [ ] チーム/個人への周知完了

---

**Last Updated**: 2026年7月6日  
**Version**: Rev.1.0  
**Status**: 移行ガイド初版
