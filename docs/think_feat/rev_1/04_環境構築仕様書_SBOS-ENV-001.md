# 環境構築仕様書（システム前提要件・マルチモデル配置・セットアップガイド）
**ローカルLLM × OpenCode × Python Orchestrator フルスタック構築仕様**

| 項目 | 内容 |
| :--- | :--- |
| 文書番号 | SBOS-ENV-001 |
| 版数 | Rev.3.1 |
| 作成日 | 2026年7月27日 |
| 対象読者 | インフラエンジニア / システム管理者 / 開発環境構築担当エンジニア |
| 関連文書 | SBOS-BD-002（基本設計書）、SBOS-OP-001（運用詳細設計書） |

---

## 1. ハードウェア・システム前提要件

本システムは完全オフライン環境およびローカルマシンの計算リソースで稼働するため、以下のハードウェア・ソフトウェア要件を厳格に満たす必要がある。

### 1.1 推奨ハードウェア要件（GPU VRAM 割り当て）
ローカルLLMを並列あるいは高速ロードして稼働させるため、特に NVIDIA GPU または Apple Silicon (Mシリーズ) Unified Memory の VRAM 容量が極めて重要となる。

| パターン | システム構成・GPUスペック | 稼働可能なモデル構成 | 想定パフォーマンス |
| :--- | :--- | :--- | :--- |
| **推奨環境** | **NVIDIA RTX 4090 (24GB VRAM)**<br>または Apple M3/M4 Max (64GB RAM) | • Reviewer: `qwen3:32b` (Q4_K_M)<br>• Executor: `qwen2.5-coder:14b`<br>• Coder/PM: `qwen2.5-coder:7b-16k` | 32BモデルをVRAMに常駐させつつ、7B/14Bモデルの即時ロードが可能。最高速の応答性と品質を実現。 |
| **標準環境** | **NVIDIA RTX 4080 / 3090 (16GB VRAM)**<br>または Apple M2/M3 Pro (32GB RAM) | • Reviewer/Executor: `qwen2.5-coder:14b`<br>• Coder/PM: `qwen2.5-coder:7b-16k` | 14Bモデルを最上位設計・監査として利用。全タスクの実用的で安定した自律処理が可能。 |
| **最小要件** | **NVIDIA RTX 3060 / 4060 (8GB〜12GB VRAM)**<br>または Apple M1/M2 (16GB RAM) | • 全エージェント共通: `qwen2.5-coder:7b-16k` (または 7b-instruct) | 7Bモデル単体による運用。高度なレビューや複雑な要件定義ではリトライ回数が増加する可能性あり。 |

### 1.2 必須ソフトウェアおよびミドルウェア
- **OS:** Linux (Ubuntu 22.04 LTS+ / Debian 12+), macOS (Sonoma 14+), または Windows 11 (WSL2 Ubuntu 22.04 推奨)
- **Python:** Version 3.10 以上 (推奨: Python 3.11 または 3.12)
- **パッケージマネージャー:** `uv` (Astral製 - 依存関係の確定的かつ高速な解決のために必須)
- **Git:** Version 2.30 以上
- **Ollama:** Version 0.3.0 以上 (OpenAI 互換 REST API `/v1` エンドポイントが `localhost:11434` で有効化されていること)
- **OpenCode CLI:** 最新安定版 (ターミナルおよびサブプロセスからの呼び出しに対応していること)

---

## 2. マルチモデル配置戦略と OpenCode 完全設定仕様

### 2.1 役割別推奨オープンウェイトモデル
Ollama にダウンロードし、各エージェントの責務に合わせて配備するモデル名と選択根拠を規定する。

```bash
# コマンドによるモデルのプル
ollama pull qwen2.5-coder:7b-16k
ollama pull qwen2.5-coder:14b
ollama pull qwen3:32b  # VRAM 20GB以上が確保できる場合
```

- **`qwen2.5-coder:7b-16k` (実装・対話用):**
  16,384トークンの拡張コンテキスト窓を持ち、構文エラーのないコードブロック出力と高速な応答（約40-60 token/sec）に特化。Coder および Sisyphus/PM に配備。
- **`qwen2.5-coder:14b` (設計用):**
  複雑なディレクトリ構造の把握、アルゴリズムの選択、および正確なマークダウン指示書の生成において7Bモデルを圧倒する精度を誇る。Executor に配備。
- **`qwen3:32b` (監査・レビュー用):**
  優れた自然言語論理推論力とエッジケース検知能力を持つ。コードを書かせるのではなく、仕様書と diff の整合性を批判的に監査する Reviewer に配備。

---

### 2.2 `.opencode/opencode.json` 完全コンフィグレーション定義
母艦リポジトリの `.opencode/opencode.json` に配置すべき完全な JSON 設定を以下に示す。この設定により、Python Orchestrator からのモデル呼出情報の取得（`_load_model_info`）、二重安全装置の Permission、ルール自動注入が実現される。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "qwen2.5-coder:7b-16k": { "tools": true },
        "qwen2.5-coder:14b": { "tools": true },
        "qwen3:32b": { "tools": true }
      }
    }
  },
  "model": "ollama/qwen2.5-coder:7b-16k",
  "default_agent": "sisyphus",
  "agent": {
    "executor": {
      "model": "ollama/qwen2.5-coder:14b",
      "description": "要件と制約から詳細な実装指示書を生成する設計エージェント"
    },
    "coder": {
      "model": "ollama/qwen2.5-coder:7b-16k",
      "description": "実装指示書に従い正確なソースコードを生成する実装エージェント"
    },
    "reviewer": {
      "model": "ollama/qwen3:32b",
      "description": "差分と仕様を照合しセキュリティと仕様整合性を監査するレビュアー"
    }
  },
  "permission": {
    "edit": "ask",
    "bash": {
      "*": "ask",
      "python3 tools/*.py*": "allow",
      "uv run python tools/*.py*": "allow",
      "git commit*": "ask",
      "git push*": "ask",
      "rm -rf *": "deny",
      "sudo *": "deny"
    }
  },
  "instructions": [
    "AGENTS.md"
  ]
}
```


---

## 3. ステップ・バイ・ステップ環境構築手順

新規マシンまたはクリーンな開発環境に本システムスタックをゼロから構築するための手順書を以下に規定する。

### Step 1: 必須ツールと Python パッケージマネージャー (uv) の導入
```bash
# 1. uv のインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # または ~/.zshrc

# 2. OpenCode CLI のインストール (npm 経由の例)
npm install -g @opencode-ai/cli
opencode --version

# 3. Ollama サーバーの確認
curl -s http://localhost:11434/api/version
```

### Step 2: 母艦リポジトリおよび Git 隔離構造の初期化
```bash
# 1. 母艦ディレクトリの作成と Git 初期化
mkdir -p ~/second-brain
cd ~/second-brain
git init

# 2. 決定論的ツールおよびキャッシュ用フォルダ構成の作成
mkdir -p tools/.cache projects .opencode/agents .opencode/commands

# 3. 母艦側 .gitignore の作成（衛星プロジェクト完全遮断ルールの適用）
cat << 'EOF' > .gitignore
# 衛星プロジェクトのソースコードおよびGit履歴を母艦から完全に遮断
/projects/*
!/projects/.project-registry.json

# キャッシュ・ログ・一時ファイル
tools/.cache/*
*.log
__pycache__/
*.pyc
.venv/
EOF

# 4. 衛星台帳インデックスの初期化
echo '{}' > projects/.project-registry.json
git add .gitignore projects/.project-registry.json
git commit -m "chore: initialize second-brain OS base structure"
```

### Step 3: Python 決定論的検証・実行環境（venv・linter）の構築
`tools/` 配下のスクリプト群が使用する Python 仮想環境および静的解析ツールをセットアップする。

```bash
cd ~/second-brain

# uv による Python 仮想環境の初期化と必須ライブラリの導入
uv venv
source .venv/bin/activate
uv pip install ruff pytest pytest-cov pypdf openpyxl ruff-lsp

# ruff 設定ファイル (pyproject.toml または ruff.toml) の配置
cat << 'EOF' > ruff.toml
line-length = 100
target-version = "py310"

[lint]
select = ["E", "F", "W", "I", "N", "B"]
ignore = ["E501"]
EOF
```

### Step 4: エージェントテンプレートおよびコマンドの配置
```bash
# プロンプトテンプレートの配置確認
ls -l .opencode/agents/
# -> pm.md, executor.md, coder.md, reviewer.md が存在することを確認

# スラッシュコマンドの配置確認
ls -l .opencode/commands/
# -> orchestrate.md, work.md, new-proj.md が存在することを確認
```

---

## 4. 動作検証スクリプトと診断診断コマンド

構築完了後、環境全体が正常に機能しているかを検証するための診断テストを実行する。

### 4.1 モジュールインポートおよび単体スクリプト健全性テスト
以下のコマンドを実行し、すべての Python スクリプトがエラーなくロードされ、Ollama API や設定ファイルを正しく参照できることを確認する。

```bash
cd ~/second-brain
source .venv/bin/activate

# 1. コンポーネントインポートテスト
python -c "from tools.orchestrator import IssueOrchestrator, State; print('✓ orchestrator.py loaded successfully')"
python -c "from tools.agent_client import AgentClient; client = AgentClient(); print('✓ agent_client.py initialized')"
python -c "from tools.context_manager import SharedContext; print('✓ context_manager.py loaded')"
python -c "from tools.prompt_builder import PromptBuilder; print('✓ prompt_builder.py loaded')"

# 2. スコアリングとブロッカー検知スクリプトのドライラン
python tools/score-issues.py --dry-run
python tools/check-blockers.py --dry-run
```

### 4.2 衛星環境および Orchestrator 統合動作テスト (ドライラン)
テスト用のダミー衛星プロジェクトを作成し、オーケストレーターがエージェント連携を決定論的に制御できるかを検証する。

```bash
# 1. テスト衛星プロジェクトの作成
mkdir -p projects/test-app/src projects/test-app/tests
cd projects/test-app
git init
cat << 'EOF' > project.json
{
  "name": "動作検証アプリ",
  "key": "TST",
  "created_at": "2026-07-27",
  "default_branch": "main",
  "test_command": "pytest",
  "lint_command": "ruff check ."
}
EOF

cat << 'EOF' > tasks.md
## 未着手
- [ ] [TST-001] 四則演算ユーティリティモジュールの実装  <!-- priority:high added:2026-07-27 round:1 max_round:3 -->
EOF
cd ~/second-brain

# 2. 台帳インデックスへの登録
python -c '
import json
with open("projects/.project-registry.json", "r") as f: d = json.load(f)
d["TST"] = "projects/test-app"
with open("projects/.project-registry.json", "w") as f: json.dump(d, f, indent=2)
'

# 3. オーケストレーターによるドライラン実行
python tools/orchestrator.py execute --issue-id TST-001 --dry-run

# 結果検証確認項目:
# [x] TST-001 が認識されたこと
# [x] projects/test-app へCWDがスイッチされたこと
# [x] エージェント executor -> coder -> reviewer の呼び出しパラメータが正常に構築されたこと
```---

## 5. Windows WSL2 固有の最適化および GPU パススルーチューニング

Windows 11 上の WSL2 (Windows Subsystem for Linux 2) 環境で本スタックを構築する場合、ディスクI/Oパフォーマンスと GPU VRAM 割り当てにおいて、以下の固有チューニングが必須となる。

### 5.1 ディスク I/O パフォーマンスの最大化（クロスOSアクセス禁止）
Windows の NTFS ドライブ（`/mnt/c/Users/...` 等）に母艦（`~/second-brain/`）および衛星プロジェクトを配置して WSL2 からアクセスすると、9P プロトコルのオーバーヘッドによりファイル I/O 速度が通常の **5倍〜10倍遅延** する。これは Git の操作や `pytest`, `ruff` の実行速度に致命的な影響を与える。

**必須ルール:** リポジトリと開発環境は、必ず WSL2 内部の Linux 仮想ディスク（ext4 ファイルシステム上、例: `/home/<username>/second-brain`）に配置すること。

### 5.2 `.wslconfig` によるメモリおよび CPU リソース割り当て最適化
ローカルLLM（特に 14B〜32B クラス）が VRAM から溢れてシステム RAM のスワップメモリに落ちた際、Windows 側のメモリ管理と競合して OOM (Out of Memory) クラッシュを引き起こすことを防ぐため、Windows ユーザーフォルダ直下（`C:\Users\<username>\.wslconfig`）に以下のリソース制限を明示する。

```ini
[wsl2]
# システム物理メモリの約75%〜80%をWSLに割り当て（64GB RAM搭載マシンの例）
memory=48GB
processors=12
# スワップスペースの確保（モデルロード時のバッファとして必須）
swap=24GB
# GPUダイレクトパススルーの有効化
guiApplications=false
nestedVirtualization=true
```

### 5.3 NVIDIA CUDA パススルーと Ollama GPU 認識検証
WSL2 ターミナル上で NVIDIA GPU が正しく認識され、Ollama が GPU 推論を行えることを検証する。

```bash
# 1. NVIDIA ドライバおよび CUDA レイヤーの確認
nvidia-smi
# -> GPU 名称と VRAM 使用状況が正常に表示されることを確認

# 2. Ollama サーバーログでの CUDA 認識確認
journalctl -u ollama --no-pager | grep -i cuda
# -> "NVIDIA GPU detected" や "CUDA layer initialized" が出力されていることを確認
```

---

## 6. 定常自動バッチ・バックグラウンドワーカー (`systemd`) の構成

朝の優先度スコアリングや夜間の自動テスト走行を確実に行うため、Linux / WSL2 の systemd ユーザーサービスとして自動化エンジンを登録する。

### 6.1 スコアリングバッチ用 systemd サービス (`~/.config/systemd/user/second-brain-batch.service`)
```ini
[Unit]
Description=Second Brain OS Daily Issue Scoring and Blocker Detection Job
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/home/%u/second-brain
ExecStart=/home/%u/.local/bin/uv run python tools/score-issues.py
ExecStartPost=/home/%u/.local/bin/uv run python tools/check-blockers.py
StandardOutput=append:/home/%u/second-brain/tools/.cache/daily_batch.log
StandardError=append:/home/%u/second-brain/tools/.cache/daily_batch.err

[Install]
WantedBy=default.target
```

### 6.2 タイマーユニット (`~/.config/systemd/user/second-brain-batch.timer`)
```ini
[Unit]
Description=Timer for Second Brain Daily Scoring Job (Every morning at 07:00 JST)

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true
Unit=second-brain-batch.service

[Install]
WantedBy=timers.target
```

#### サービスの有効化コマンド
```bash
systemctl --user daemon-reload
systemctl --user enable --now second-brain-batch.timer
systemctl --user list-timers
```

---

## 7. 全環境診断・健全性検証スクリプト (`verify_environment.py`)

構築作業完了後、全層（LLM API, CLI, Linter, Git, スコアリング）の動作状況を一括診断するスクリプトの実装仕様である。

```python
#!/usr/bin/env python3
"""Second Brain OS 環境健全性診断スクリプト"""
import os
import sys
import subprocess
import urllib.request
import json

def print_result(check_name: str, passed: bool, msg: str = ""):
    icon = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    print(f"[{icon}] {status} | {check_name} {': ' + msg if msg else ''}")
    if not passed:
        sys.exit(1)

def main():
    print("=== Second Brain OS Full Environment Diagnostic ===")
    
    # 1. Python バージョンチェック
    py_ver = sys.version_info
    print_result("Python Version >= 3.10", py_ver.major == 3 and py_ver.minor >= 10, f"{py_ver.major}.{py_ver.minor}")
    
    # 2. Ollama API アクセスチェック
    try:
        with urllib.request.urlopen("http://localhost:11434/api/version", timeout=3) as res:
            data = json.loads(res.read().decode())
            print_result("Ollama API Server Running", True, f"v{data.get('version')}")
    except Exception as e:
        print_result("Ollama API Server Running", False, str(e))
        
    # 3. OpenCode CLI コマンドチェック
    try:
        out = subprocess.check_output(["opencode", "--version"], stderr=subprocess.STDOUT, text=True)
        print_result("OpenCode CLI Installed", True, out.strip())
    except Exception as e:
        print_result("OpenCode CLI Installed", False, str(e))
        
    # 4. 必須 Python ツール (ruff, pytest) チェック
    for tool in ["ruff", "pytest"]:
        try:
            out = subprocess.check_output([tool, "--version"], stderr=subprocess.STDOUT, text=True)
            print_result(f"Tool {tool} Available", True, out.splitlines()[0])
        except Exception as e:
            print_result(f"Tool {tool} Available", False, str(e))
            
    # 5. 台帳インデックス構造チェック
    reg_path = "projects/.project-registry.json"
    print_result("Project Registry File Exists", os.path.exists(reg_path), reg_path)
    
    print("=== All Diagnostics Passed Successfully! ===")

if __name__ == "__main__":
    main()
```