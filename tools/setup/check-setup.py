#!/usr/bin/env python3
"""
check-setup.py  ―  環境構築セットアップ完了チェックリスト自動検証スクリプト
Windows / WSL2 双方の環境差異を考慮して各コンポーネントを診断します。
"""

import sys
import os
import shutil
import json
import urllib.request
import urllib.error
import subprocess
import logging
from pathlib import Path

# loggerの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("check-setup")

def is_wsl() -> bool:
    """WSL環境かどうかを判定する"""
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            content = f.read().lower()
            if "microsoft" in content or "wsl" in content:
                return True
    except Exception:
        pass
    return False

def check_terminal() -> bool:
    """Windows Terminalの検出"""
    if "WT_SESSION" in os.environ:
        logger.info("[OK] 1. Terminal: Windows Terminal を検出しました。")
        return True
    elif "TERM_PROGRAM" in os.environ:
        logger.info(f"[OK] 1. Terminal: {os.environ['TERM_PROGRAM']} を検出しました。")
        return True
    else:
        # フォールバック: 標準入力の端末チェック
        if sys.stdout.isatty():
            logger.info("[OK] 1. Terminal: 適切なインタラクティブ端末を検出しました。")
            return True
        logger.warning("[WARN] 1. Terminal: Windows Terminal または一般的なターミナルエミュレータが検出されませんでした。")
        return False

def check_wsl() -> bool:
    """WSL2有効化状態の確認"""
    if is_wsl():
        logger.info("[OK] 2. WSL2: WSL2環境で動作しています。")
        return True
    else:
        # Windowsネイティブ環境かチェック
        import platform
        if platform.system() == "Windows":
            logger.info("[INFO] 2. Environment: Windowsネイティブ環境で動作しています。")
            return True
        logger.warning("[WARN] 2. WSL2: WSL2環境が検出されませんでした（Windows Terminal上でWSL2を起動してください）。")
        return False

def check_ollama() -> tuple[bool, str]:
    """Ollamaの動作状態確認"""
    hosts = ["localhost", "127.0.0.1"]
    if is_wsl():
        # 【現代WSL2対応】ip routeコマンドから「本物のWindowsホストIP」を確実に取り出す
        try:
            res = subprocess.run(["sh", "-c", "ip route show default | awk '{print $3}'"], capture_output=True, text=True)
            gw = res.stdout.strip()
            if gw and gw not in hosts:
                hosts.append(gw)
        except Exception:
            pass

        # 旧方式（resolv.conf）もフォールバックとして一応残す
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        ip = line.split()[1].strip()
                        if ip not in hosts:
                            hosts.append(ip)
                        break
        except Exception:
            pass

    for host in hosts:
        url = f"http://{host}:11434/api/version"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    logger.info(f"[OK] 3. Ollama: ホスト {host} にて Ollama 疎通成功 (version: {data.get('version')}).")
                    if host in ["localhost", "127.0.0.1"] and is_wsl():
                        logger.info("   -> [INFO] WSL2の mirrored ネットワークモード、または同一ローカル空間での接続が有効です。")
                    return True, host
        except Exception:
            continue
    logger.error("[NG] 3. Ollama: Ollama 疎通失敗。")
    if is_wsl():
        logger.error("   -> [HINT] Windows側で Ollama が起動しているか確認してください。")
        logger.error("   -> [HINT] WSL2の mirrored モードをご使用の場合は、Windows側の .wslconfig に [wsl2] networkingMode=mirrored が設定されていることを確認してください。")
        logger.error("   -> [HINT] mirrored モードでない場合は、WindowsのホストIP（ip route defaultのIP）が Ollama のホストとして opencode.json の baseURL に設定されている必要があります。")
    return False, ""

def check_model(ollama_host: str) -> bool:
    """モデル qwen2.5-coder:14b-instruct または gemma4-12b-it-Q4_K_M:latest が利用可能かチェック"""
    if not ollama_host:
        logger.error("[NG] 4. Ollama Model: Ollamaに接続できないため検証をスキップします。")
        return False
    url = f"http://{ollama_host}:11434/api/tags"
    target_models = ["qwen2.5-coder:14b-instruct", "gemma4-12b-it-Q4_K_M:latest"]
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                available = [m.get("name") for m in data.get("models", [])]
                # リストが ['model:latest'] のようになっている場合があるため部分一致も含める
                found = []
                for t in target_models:
                    for a in available:
                        if t in a:
                            found.append(a)
                if found:
                    logger.info(f"[OK] 4. Ollama Model: 必要なモデルが見つかりました: {list(set(found))}")
                    return True
                else:
                    logger.warning(f"[WARN] 4. Ollama Model: 推奨モデル {target_models} が Ollama 内に存在しません。'ollama pull qwen2.5-coder:7b' を実行してください (利用可能: {available})。")
                    return False
    except Exception as e:
        logger.error(f"[NG] 4. Ollama Model: モデル一覧の取得に失敗しました: {e}")
    return False

def check_opencode() -> bool:
    """OpenCode コマンドの確認"""
    path = shutil.which("opencode")
    if path:
        logger.info(f"[OK] 5. OpenCode: インストールされています (path: {path})。")
        return True
    logger.error("[NG] 5. OpenCode: 'opencode' コマンドが見つかりません。npm または scoop を利用してインストールしてください。")
    return False

def check_opencode_json() -> bool:
    """opencode.json 設定ファイルの検証"""
    config_path = Path("opencode.json")
    if not config_path.exists():
        logger.error("[NG] 6. opencode.json: 設定ファイルがルートディレクトリに存在しません。")
        return False
    try:
        json.loads(config_path.read_text(encoding="utf-8"))
        logger.info("[OK] 6. opencode.json: 設定ファイルが存在し、正しいJSONフォーマットです。")
        return True
    except Exception as e:
        logger.error(f"[NG] 6. opencode.json: JSONパースエラー: {e}")
    return False

def check_script(num: int, name: str, path: str) -> bool:
    """Python スクリプトツールの存在と実行確認"""
    p = Path(path)
    if not p.exists():
        logger.error(f"[NG] {num}. {name}: スクリプトファイルが見つかりません (期待パス: {path})。")
        return False
    try:
        res = subprocess.run([sys.executable, path, "--help"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0 or "usage:" in res.stderr or "usage:" in res.stdout:
            logger.info(f"[OK] {num}. {name}: スクリプトが存在し、正常に実行可能です。")
            return True
        else:
            logger.warning(f"[WARN] {num}. {name}: スクリプトは存在しますが、--help の実行結果が異常値 (code: {res.returncode}) を返しました。")
            return True
    except Exception as e:
        logger.error(f"[NG] {num}. {name}: 実行テスト中にエラーが発生しました: {e}")
    return False

def check_crontab() -> bool:
    """crontabの設定確認"""
    if not is_wsl():
        logger.info("[INFO] 10. Crontab: WSL2環境ではないため、crontab検証をスキップします（Windowsではタスクスケジューラ等を利用してください）。")
        return True
    try:
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if "score-issues.py" in res.stdout or "check-blockers.py" in res.stdout:
            logger.info("[OK] 10. Crontab: バックグラウンド実行タスクが crontab に登録されています。")
            return True
        else:
            logger.warning("[WARN] 10. Crontab: crontab に second-brain 用の定期タスクが登録されていません。")
            return False
    except Exception as e:
        logger.warning(f"[WARN] 10. Crontab: crontab 情報が取得できませんでした: {e}")
    return False

def check_gitattributes() -> bool:
    """.gitattributes 設定の確認"""
    p = Path(".gitattributes")
    if p.exists():
        logger.info("[OK] 11. .gitattributes: ファイルが存在します。")
        return True
    logger.warning("[WARN] 11. .gitattributes: ファイルが存在しません。改行コードLF維持のため配置を推奨します。")
    return False

def check_git_hooks() -> bool:
    """Git Hookの設定確認"""
    git_dir = Path(".git")
    if not git_dir.exists():
        logger.info("[INFO] 12. Git Hooks: ルートに .git が存在しないため検証をスキップします。")
        return True
    
    hook_file = git_dir / "hooks" / "post-commit"
    if hook_file.exists():
        logger.info("[OK] 12. Git Hooks: post-commit フックがインストールされています。")
        return True
    logger.warning("[WARN] 12. Git Hooks: post-commit フックが見つかりません。")
    return False

def main():
    logger.info("=========================================")
    logger.info("   Second Brain OS 環境検証スクリプト")
    logger.info("=========================================")
    results = {}
    
    results["Terminal"] = check_terminal()
    results["WSL2"] = check_wsl()
    
    ok_ollama, ollama_host = check_ollama()
    results["Ollama"] = ok_ollama
    results["Ollama Model"] = check_model(ollama_host)
    
    results["OpenCode"] = check_opencode()
    results["opencode.json"] = check_opencode_json()
    
    results["score-issues.py"] = check_script(7, "score-issues.py", "tools/score-issues.py")
    results["check-blockers.py"] = check_script(8, "check-blockers.py", "tools/check-blockers.py")
    results["notify.py"] = check_script(9, "notify.py", "tools/notify.py")
    
    results["Crontab"] = check_crontab()
    results[".gitattributes"] = check_gitattributes()
    results["Git Hooks"] = check_git_hooks()
    
    logger.info("=========================================")
    logger.info("             検証結果サマリー")
    logger.info("=========================================")
    all_ok = True
    for key, val in results.items():
        status = "PASS" if val else "FAIL/WARN"
        if not val and key in ["Ollama", "OpenCode", "opencode.json", "score-issues.py", "check-blockers.py"]:
            all_ok = False
        logger.info(f"  {key:<20}: {status}")
        
    logger.info("=========================================")
    if all_ok:
        logger.info("[SUCCESS] すべての重要コンポーネントが稼働可能です！")
        sys.exit(0)
    else:
        logger.error("[ERROR] いくつかの重要コンポーネントの検証に失敗しました。上記ログを確認してください。")
        sys.exit(1)

if __name__ == "__main__":
    main()
