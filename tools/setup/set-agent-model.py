#!/usr/bin/env python3
"""
set-agent-model.py  ―  エージェントモデル一括管理・変更ツール
.opencode/agents/ 配下にある各エージェント定義（Markdown）のモデル設定を確認・変更します。
引数なしで起動された場合は対話的（CUI）メニューを起動します。
"""

import sys
import re
import argparse
import logging
import json
from pathlib import Path

# loggerの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("set-agent-model")

AGENTS_DIR = Path(".opencode/agents")

def is_wsl() -> bool:
    """WSL環境かどうかを判定する"""
    import os
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

def get_ollama_models() -> list[str]:
    """Ollama API から利用可能なモデル一覧を取得する"""
    import json
    import urllib.request
    
    hosts = ["localhost", "127.0.0.1"]
    if is_wsl():
        # resolv.conf からホストIPを取得して候補に入れる
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        ip = line.split()[1].strip()
                        hosts.append(ip)
                        break
        except Exception:
            pass

    for host in hosts:
        url = f"http://{host}:11434/api/tags"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    return sorted(list(set(models)))
        except Exception:
            continue
    return []

def get_agent_files() -> dict[str, Path]:
    """エージェント名とファイルの辞書を取得する"""
    if not AGENTS_DIR.exists():
        logger.error(f"[ERROR] エージェントディレクトリが見つかりません: {AGENTS_DIR}")
        return {}
    
    files = {}
    for p in AGENTS_DIR.glob("*.md"):
        files[p.stem] = p
    return files

def parse_agent_model(path: Path) -> str | None:
    """エージェントファイルからモデル名を抽出する"""
    try:
        content = path.read_text(encoding="utf-8")
        # フロントマター (先頭の --- から --- までの間) をパース
        m_fm = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
        if not m_fm:
            return None
        
        fm_text = m_fm.group(1)
        m_model = re.search(r"^model:\s*(.+)$", fm_text, re.MULTILINE)
        if m_model:
            return m_model.group(1).strip()
    except Exception as e:
        logger.error(f"[ERROR] {path.name} のパース失敗: {e}")
    return None

def update_agent_model(path: Path, new_model: str) -> bool:
    """エージェントファイルのモデル名を更新する"""
    try:
        content = path.read_text(encoding="utf-8")
        m_fm = re.match(r"^(---\r?\n)(.*?)(\r?\n---)", content, re.DOTALL)
        if not m_fm:
            logger.error(f"[ERROR] {path.name} にフロントマターが見つかりません。")
            return False
        
        prefix, fm_text, suffix = m_fm.groups()
        
        # model 行が存在するか確認
        if re.search(r"^model:\s*", fm_text, re.MULTILINE):
            # model 行を書き換え
            fm_text_new = re.sub(r"^(model:\s*).*$", r"\1" + new_model, fm_text, flags=re.MULTILINE)
        else:
            # model 行を追加
            fm_text_new = fm_text.rstrip() + f"\nmodel: {new_model}"
            
        new_content = prefix + fm_text_new + suffix + content[m_fm.end():]
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        logger.error(f"[ERROR] {path.name} の更新失敗: {e}")
def update_opencode_json_model(agent_name: str, new_model: str) -> bool:
    """opencode.json 内の指定エージェントのモデル名、およびデフォルトモデルを必要に応じて更新する"""
    config_path = Path("opencode.json")
    if not config_path.exists():
        return True
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        
        # 指定エージェントのモデル変更
        if "agent" in data and agent_name in data["agent"]:
            data["agent"][agent_name]["model"] = new_model
            
        # デフォルトエージェントが変更された場合は、デフォルトモデルも同期
        if agent_name == data.get("default_agent", "sisyphus"):
            data["model"] = new_model
            
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  [SUCCESS] opencode.json の '{agent_name}' モデルを {new_model} に更新しました。")
        return True
    except Exception as e:
        logger.error(f"[ERROR] opencode.json の更新失敗: {e}")
        return False

def list_agents(files: dict[str, Path]):
    """現在のモデル割り当てを一覧表示する"""
    logger.info("=== エージェントモデル設定一覧 ===")
    for name in sorted(files.keys()):
        model = parse_agent_model(files[name])
        model_str = model if model else "(未設定/デフォルト設定が適用されます)"
        logger.info(f"  {name:<15} : {model_str}")
    logger.info("=================================")

def select_model_menu(ollama_models: list[str], agent_name: str) -> str | None:
    """モデル選択メニューを表示して選択されたモデルを返す"""
    import os
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        logger.info(f"=== モデルの選択 (対象エージェント: {agent_name}) ===")
        
        # Ollama のモデルリストを表示
        for idx, model in enumerate(ollama_models, 1):
            logger.info(f"  {idx:>2}. {model}")
            
        manual_idx = len(ollama_models) + 1
        logger.info(f"  {manual_idx:>2}. 手動で直接入力する")
        logger.info("=========================================")
        logger.info("  [c]. キャンセルして戻る")
        logger.info("=========================================")
        
        choice = input("割り当てるモデルの番号を入力してください: ").strip()
        if choice.lower() == "c":
            return None
            
        try:
            val = int(choice)
            if 1 <= val <= len(ollama_models):
                selected = ollama_models[val - 1]
                # OpenCodeのモデルフォーマットは 'ollama/モデル名' なのでプレフィックスを付ける
                if not selected.startswith("ollama/"):
                    return f"ollama/{selected}"
                return selected
            elif val == manual_idx:
                manual_model = input("モデル名を手動入力してください (例: ollama/qwen2.5-coder:7b-16k): ").strip()
                if manual_model:
                    return manual_model
                else:
                    input("\n[ERROR] 入力が空です。Enterキーを押して再試行してください...")
            else:
                input("\n[ERROR] 無効な番号です。Enterキーを押して再試行してください...")
        except ValueError:
            input("\n[ERROR] 無効な入力です。Enterキーを押して再試行してください...")

def interactive_mode(files: dict[str, Path]):
    """対話型（CUI）メニューの実行"""
    import os
    
    # Ollama からモデルリストを取得
    ollama_models = get_ollama_models()
    if not ollama_models:
        logger.warning("[WARN] Ollama からモデル一覧を取得できませんでした。手動入力のみとなります。")

    while True:
        # 画面クリア（Windows/Linux/WSL両対応）
        os.system("cls" if os.name == "nt" else "clear")
        
        logger.info("=========================================")
        logger.info("   エージェントモデル設定 (対話型 CUI)")
        logger.info("=========================================")
        
        # エージェントと現在の設定を表示
        agents = sorted(files.keys())
        for idx, name in enumerate(agents, 1):
            model = parse_agent_model(files[name])
            model_str = model if model else "(未設定)"
            logger.info(f"  {idx:>2}. {name:<15} : {model_str}")
        logger.info("=========================================")
        logger.info("  [q]. 終了")
        logger.info("=========================================")
        
        choice = input("操作するエージェントの番号を入力してください: ").strip()
        if choice.lower() == "q":
            logger.info("対話型 CUI モードを終了します。")
            break

        try:
            val = int(choice)
            if 1 <= val <= len(agents):
                target_agent = agents[val - 1]
                model_to_set = select_model_menu(ollama_models, target_agent)
                if model_to_set:
                    path = files[target_agent]
                    old_model = parse_agent_model(path)
                    logger.info(f"エージェント '{target_agent}' のモデル変更: {old_model} -> {model_to_set}")
                    if update_agent_model(path, model_to_set):
                        update_opencode_json_model(target_agent, model_to_set)
                        logger.info("[SUCCESS] 変更されました。")
                    input("\nEnterキーを押してメニューに戻ります...")
            else:
                input("\n[ERROR] 無効な番号です。Enterキーを押して再試行してください...")
        except ValueError:
            input("\n[ERROR] 無効な入力です。Enterキーを押して再試行してください...")

def main():
    parser = argparse.ArgumentParser(description="エージェントモデル管理ツール")
    parser.add_argument("agent", nargs="?", help="変更対象のエージェント名 (例: coder)")
    parser.add_argument("model", nargs="?", help="新しいモデル名 (例: ollama/qwen2.5-coder:7b-16k)")
    parser.add_argument("--list", "-l", action="store_true", help="現在のモデル割り当てを一覧表示")
    parser.add_argument("--interactive", "-i", action="store_true", help="対話型 CUI メニューを起動")
    args = parser.parse_args()

    files = get_agent_files()
    if not files:
        sys.exit(1)

    # 引数もオプションも何も指定されていない場合、または -i/--interactive が指定された場合は対話型モードへ
    if args.interactive or (not args.agent and not args.model and not args.list):
        interactive_mode(files)
        sys.exit(0)

    if args.list:
        list_agents(files)
        sys.exit(0)

    if args.agent and args.model:
        name = args.agent
        new_model = args.model
        if name not in files:
            logger.error(f"[ERROR] 指定されたエージェント '{name}' は存在しません。利用可能: {list(files.keys())}")
            sys.exit(1)
        
        path = files[name]
        old_model = parse_agent_model(path)
        logger.info(f"エージェント '{name}' のモデル変更: {old_model} -> {new_model}")
        if update_agent_model(path, new_model):
            update_opencode_json_model(name, new_model)
            logger.info("[SUCCESS] 正常に変更されました。")
            sys.exit(0)
        else:
            sys.exit(1)
            
    logger.error("[ERROR] 引数が正しくありません。引数を2つ指定するか、--list を使用してください。")
    parser.print_help()
    sys.exit(1)

if __name__ == "__main__":
    main()
