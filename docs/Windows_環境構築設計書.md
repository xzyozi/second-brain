# 環境構築設計書 (Windows 環境)
**OpenCode × Ollama × ローカルLLM 「第二の脳」プロジェクト管理システム**

| 項目 | 内容 |
| :--- | :--- |
| 文書番号 | SBOS-WIN-001 |
| 版数 | Rev.2.0 |
| 作成日 | 2026年6月26日 |
| 対象OS | Windows 10 / 11（x64） |
| 関連文書 | SBOS-BD-001（基本設計書）/ SBOS-L2-001（Layer 2詳細設計書） |

## 1. 概要
### 1.1 目的
本書は、基本設計書（SBOS-BD-001）および Layer 2 詳細設計書（SBOS-L2-001）で定義したシステムを Windows 10 / 11 環境で構築・運用するための手順・差分設計を定義する。macOS / Linux との環境差異を正確に把握し、全ての構成要素をWindowsネイティブまたはWSL2上で正常に動作させることを目的とする。

### 1.2 Windowsにおける構成方針の選択
OpenCode公式ドキュメントはWindowsについて、WSL2を強く推奨している。一方でScoop / Chocolateyによるネイティブインストールも可能であり、それぞれに一長一短がある。本設計書では両方式の比較を行い、推奨構成を明示する。

| 比較軸 | WSL2構成（推奨） | ネイティブWindows構成 |
| :--- | :--- | :--- |
| **OpenCodeの動作** | ◎ 完全対応（Linux環境） | ○ 対応（一部制限あり） |
| **Ollama連携** | ◎ localhost:11434 直接通信 | ◎ localhost:11434 直接通信 |
| **Pythonスクリプト** | ◎ bash/Python完全動作 | △ パス区切り・改行コードに注意 |
| **daily-loop.sh** | ◎ cronがそのまま使用可能 | ✕ Task Schedulerへの書き換えが必要 |
| **通知（notify.py）** | ◎ PowerShell経由でToast発火対応 | ◎ Toastネイティブ対応 |
| **ターミナル** | Windows Terminal + WSL2 | Windows Terminal / PowerShell |
| **セットアップ難易度** | 中（WSL2有効化が初回必要） | 低（即時使用可能） |

> **推奨方針**：本設計書では **WSL2構成を主軸**とし、ネイティブWindows固有の差分を補足として記載する。理由はOpenCode TUIの完全な文字・色レンダリング、cronによるLayer 3自動化、Pythonスクリプトのパス互換性を確保するためである。

---

## 2. 前提条件・必要要件
### 2.1 ハードウェア要件
| 項目 | 要件 |
| :--- | :--- |
| **CPU** | 64bit対応（x64）。仮想化支援機能（VT-x / AMD-V）が有効であること |
| **RAM** | 最小 16GB（ローカルLLM 7B クラスで約6〜8GB消費するため） |
| **GPU（推奨）** | NVIDIA CUDA対応GPU（VRAM 8GB以上）またはAMD ROCm対応GPU |
| **GPU（CPU推論）** | GPUなしでも動作するが、7Bモデルで応答に30〜120秒/トークン程度かかる |
| **ストレージ** | 空き容量 40GB 以上（WSL2 + Ollama + モデルファイルで計約30GB） |
| **OS** | Windows 10 Version 2004以上（Build 19041以上）または Windows 11 |

### 2.2 Windowsターミナルの準備
OpenCode TUIはUnicode・TrueColor（24bit色）に対応したターミナルエミュレータを必要とする。Windows標準のコマンドプロンプト（cmd.exe）では文字化け・色崩れが発生する。

| ターミナル | TrueColor | 入手方法 |
| :--- | :--- | :--- |
| **Windows Terminal** | ◎ | Microsoft Store または `winget install Microsoft.WindowsTerminal` |
| **WezTerm** | ◎ | https://wezfurlong.org/wezterm/ |
| **VSCode統合ターミナル** | ◎ | OpenCode TUI非推奨（幅が狭い場合あり） |
| **PowerShell 7** | ○ | `winget install Microsoft.PowerShell` |
| **cmd.exe** | ✕ | 使用不可 |

> **推奨設定**：Windows Terminal を使用し、フォントを「Nerd Font」または「JetBrains Mono」等のUnicode対応等幅フォントに変更する。デフォルトの「游ゴシック」はTUI表示で罫線が崩れることがある。

---

## 3. WSL2 セットアップ手順
### 3.1 WSL2の有効化
PowerShellを管理者として起動し、以下を実行する。

```powershell
# PowerShell（管理者）で実行
wsl --install

# 再起動後、WSL2のデフォルト設定を確認
wsl --set-default-version 2

# インストール済みディストリビューション確認
wsl --list --verbose
# → Ubuntu 24.04 LTS が推奨

```

> **注意**：`wsl --install` の実行後にPCの再起動が必要。再起動後にUbuntuの初回セットアップ（ユーザー名・パスワード設定）が自動起動する。

### 3.2 WSL2内の環境セットアップ

WSL2（Ubuntu）のターミナルを開き、以下の順序でセットアップを行う。

```bash
# パッケージ更新
sudo apt update && sudo apt upgrade -y

# Python 3 と git のインストール確認
sudo apt install -y python3 python3-pip git
python3 --version   # 3.12以上を確認

# Node.js（OpenCode npmインストール用）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # v22以上を確認

```

### 3.3 Ollamaのインストール（Windows側）

OllamaはWSL2ではなくWindowsネイティブにインストールする。これによりGPUドライバを直接使用でき、WSL2から `localhost:11434` で通信できる。

```powershell
# Windows側（PowerShellまたはブラウザ）でOllamaをインストール
# 方法A: 公式インストーラー（推奨） https://ollama.com/download/OllamaSetup.exe を実行
# 方法B: winget
winget install Ollama.Ollama

# インストール後、Ollamaサービスが自動起動する
# WSL2内から疎通確認
curl http://localhost:11434/api/version
# → {"version":"..."} が返れば成功

```

> **重要**：OllamaをWSL2側にインストールするとGPUが認識されず、CPU推論のみになる。必ずWindowsネイティブ側にインストールすること。WSL2からはlocalhost（または `$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')` のWindowsホストIP）でアクセスできる。

### 3.4 Ollamaモデルの取得とコンテキスト拡張

Windowsのコマンドプロンプト（またはPowerShell）でモデルを取得する。

```powershell
# Windows PowerShell または コマンドプロンプトで実行
ollama pull qwen2.5-coder:7b

# コンテキスト拡張版を作成
ollama run qwen2.5-coder:7b
>>> /set parameter num_ctx 16384
>>> /save qwen2.5-coder:7b-16k
>>> /bye

# 14Bモデル（coderエージェント用、VRAM 10GB以上推奨）
ollama pull qwen2.5-coder:14b

```

---

## 4. OpenCode のインストール

### 4.1 WSL2構成（推奨）

```bash
# WSL2（Ubuntu）内で実行
# 方法A: npm（推奨 / 最新版）
sudo npm install -g opencode-ai@latest

# バージョン確認
opencode --version

# プロジェクトディレクトリで起動
mkdir -p ~/second-brain && cd ~/second-brain
opencode

```

### 4.2 ネイティブWindows構成

```powershell
# Windows PowerShell で実行
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex
scoop install opencode
opencode --version

```

### 4.3 opencode.json の Windows対応設定

基本設計書の `opencode.json` との差分はOllama接続先URLのみ。WSL2構成ではlocalhostが通常動作する。

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
        "qwen2.5-coder:7b-16k": { "name": "Qwen2.5 Coder 7B (16K)" },
        "qwen2.5-coder:14b":    { "name": "Qwen2.5 Coder 14B" }
      }
    }
  },
  "model": "ollama/qwen2.5-coder:7b-16k",
  "default_agent": "sisyphus",
  "permission": {
    "edit": "ask",
    "bash": { "*": "ask", "rm -rf *": "deny" }
  },
  "instructions": ["AGENTS.md"]
}

```

---

## 5. Windows 固有 of 差分実装

### 5.1 notify.py のWindows対応（Toastデスクトップ通知）

macOS版は `osascript` を使用したが、WindowsではWSL2からネイティブの `powershell.exe` を直接叩いてバルーン通知を発火させる。

```python
def notify_desktop_wsl_to_windows(title: str, body: str) -> bool:
    """WSL2内からPowerShellを経由してWindowsトースト通知を発火させる"""
    import shutil, subprocess, sys
    ps_candidates = [
        shutil.which("powershell.exe"),
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    ps_path = next((p for p in ps_candidates if p), None)
    if not ps_path:
        return False

    ps_script = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(5000, '{title}', '{body}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep 3; $n.Dispose()"
    )
    try:
        subprocess.run([ps_path, "-NonInteractive", "-Command", ps_script], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"[notify] WSL2→Windows通知失敗: {e}", file=sys.stderr)
        return False

```

### 5.2 daily-loop.sh の代替設定

#### 方法A（推奨）：WSL2内のcrontab

```bash
crontab -e
# 以下を追記（毎朝 07:00 にスコアリング実行）
0 7 * * * cd ~/second-brain && python3 tools/score-issues.py && python3 tools/check-blockers.py && python3 tools/notify.py --event daily_summary

```

---

## 6. Windows 固有の注意事項

### 6.1 パス区切り文字

| 環境 | パスの扱い |
| --- | --- |
| **WSL2内のPython/bash** | Linux形式（`/home/user/...`）でそのまま動作 |
| **WSL2からWindowsファイルへのアクセス** | `/mnt/c/Users/...` 形式でアクセスする |
| **ネイティブWindows Python** | `C:\Users\...` 形式。スクリプト内の `Path()` はOSに応じて自動解決 |
| **保存場所** | WSL2のホームディレクトリ（`~/second-brain/`）推奨。`/mnt/c/` 配下は著しく速度が低下する |

### 6.2 改行コードの厳格管理

Gitのデフォルト設定ではWindowsでチェックアウトするとCRLFに変換される。WSL2上で動作するPythonやシェルスクリプトに対してはLFを厳格に維持する必要があるため、全ファイルをLF固定とする。

```text
# .gitattributes
* text=auto
*.py   text eol=lf
*.sh   text eol=lf
*.md   text eol=lf
*.json text eol=lf
*.ps1  text eol=lf

```

---

## 7. セットアップ完了チェックリスト

| # | 確認項目 | 確認コマンド / 方法 |
| --- | --- | --- |
| 1 | Windows Terminal がインストールされている | Microsoft Storeを確認 |
| 2 | WSL2が有効化されUbuntu 24.04が起動できる | `wsl --list --verbose` |
| 3 | Ollama がWindows側で動作している | `curl http://localhost:11434/api/version`（WSL2内から） |
| 4 | qwen2.5-coder:7b-16k が利用可能 | `ollama list`（Windows側で） |
| 5 | OpenCode が WSL2内でインストールされている | `opencode --version`（WSL2内で） |
| 6 | opencode.json が正しく設定されている | `cd ~/second-brain && opencode` で起動確認 |
| 7 | score-issues.py が正常動作する | `python3 tools/score-issues.py` |
| 8 | check-blockers.py が正常動作する | `python3 tools/check-blockers.py` |
| 9 | notify.py がデスクトップ通知を発火できる | `python3 tools/notify.py --event custom --title テスト --detail 動作確認` |
| 10 | crontab が登録されている | `crontab -l`（WSL2） |
| 11 | .gitattributes が配置されている | `cat .gitattributes` |
| 12 | git hooks がインストールされている | `ls .git/hooks/post-commit` |

---

## 8. トラブルシューティング

| 症状 | 原因 | 対処法 |
| --- | --- | --- |
| **Ollama に接続できない（WSL2から）** | Windowsファイアウォールがブロックしている | `netsh advfirewall firewall add rule name="Ollama WSL2" dir=in action=allow protocol=TCP localport=11434` を管理者PSで実行 |
| **OpenCode TUIが文字化けする** | フォントがマルチバイト非対応 | Windows Terminal設定でフォントを JetBrains Mono 等に変更 |
| **cronがWSL2再起動後に動かない** | Windows再起動時にWSL2VMが停止するため | Windowsスタートアップに `wsl -e bash -c "sudo service cron start"` を登録 |
| **GPUが認識されない** | WSL2側にOllamaを入れてしまった | Windows側にOllamaを再インストールし、NVIDIA Driverを確認 |
| **notify.pyの通知が届かない** | PowerShellのパスが解決できていない | `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe` のフルパス固定を確認 |
