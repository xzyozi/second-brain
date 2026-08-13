#!/usr/bin/env python3
"""
agent_client.py - OpenCode CLI呼び出しラッパー

OpenCode CLI (`opencode run --agent <name> "<prompt>"`) の呼び出しをラップし、
レスポンスのパースを統一的に処理する。

使い方:
    from agent_client import AgentClient
    
    client = AgentClient()
    response = client.call_agent("executor", "Issue ARCH-001を実装してください")
    print(response.parsed_data)
"""

import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import time

logger = logging.getLogger("agent_client")


# ===========================
# データモデル
# ===========================

@dataclass
class AgentResponse:
    """エージェント応答の構造化データ"""
    raw_output: str
    parsed_data: Dict[str, Any]
    success: bool
    error_message: Optional[str]
    execution_time: float
    agent_name: str
    timestamp: str


# ===========================
# エラー定義
# ===========================

class AgentCallError(Exception):
    """エージェント呼び出しエラー"""
    pass


class ResponseParseError(Exception):
    """レスポンスパースエラー"""
    pass


# ===========================
# AgentClient
# ===========================

class AgentClient:
    """OpenCode CLIの呼び出しクライアント"""

    def __init__(self, timeout: int = 300, opencode_bin: str = "opencode"):
        """
        Args:
            timeout: コマンド実行のタイムアウト（秒）
            opencode_bin: opencodeコマンドのパス（デフォルトはPATH上の opencode）
        """
        self.timeout = timeout
        self.opencode_bin = opencode_bin
        self.call_history: List[Dict[str, Any]] = []  # デバッグ用の呼び出し履歴

    def call_agent(
        self,
        agent_name: str,
        prompt: str,
        context_summary: Optional[str] = None,
        max_retries: int = 3
    ) -> AgentResponse:
        """
        OpenCode CLIを呼び出してエージェントを実行

        実行コマンド:
        opencode run --agent {agent_name} "{prompt}"

        Args:
            agent_name: エージェント名（executor, coder等）
            prompt: エージェントに渡すプロンプト
            context_summary: 共有コンテキストのサマリー（プロンプトに前置）
            max_retries: 失敗時のリトライ回数

        Returns:
            AgentResponse: パース済みの応答データ

        Raises:
            AgentCallError: 呼び出しが max_retries 回失敗した場合
        """
        logger.info(f"AgentClient.call_agent: {agent_name}")

        # コンテキストサマリーをプロンプトに前置
        full_prompt = prompt
        if context_summary:
            full_prompt = f"{context_summary}\n\n---\n\n{prompt}"

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"  試行 {attempt}/{max_retries}")

                start_time = time.time()
                completed_process = self._execute_opencode_cli(agent_name, full_prompt)
                execution_time = time.time() - start_time

                # レスポンスパース
                parsed_data = self._parse_response(completed_process.stdout, agent_name)

                # バリデーション
                is_valid = self._validate_response(parsed_data, agent_name)

                if not is_valid:
                    logger.warning(f"  応答の検証に失敗（attempt {attempt}）")
                    if attempt < max_retries:
                        continue
                    else:
                        raise ResponseParseError(f"応答が不正: {parsed_data}")

                # 成功
                response = AgentResponse(
                    raw_output=completed_process.stdout,
                    parsed_data=parsed_data,
                    success=True,
                    error_message=None,
                    execution_time=execution_time,
                    agent_name=agent_name,
                    timestamp=datetime.now().isoformat()
                )

                # 履歴に記録
                self.call_history.append({
                    "agent_name": agent_name,
                    "attempt": attempt,
                    "success": True,
                    "execution_time": execution_time,
                    "timestamp": response.timestamp
                })

                logger.info(f"  ✓ エージェント呼び出し成功 ({execution_time:.2f}s)")
                return response

            except subprocess.TimeoutExpired as e:
                logger.error(f"  タイムアウト（attempt {attempt}）: {self.timeout}秒")
                if attempt >= max_retries:
                    raise AgentCallError(f"Agent {agent_name} がタイムアウトしました（{max_retries}回試行）")

            except Exception as e:
                logger.error(f"  エラー（attempt {attempt}）: {e}")
                if attempt >= max_retries:
                    raise AgentCallError(f"Agent {agent_name} の呼び出しに失敗しました: {e}")

        # ここには到達しないはず
        raise AgentCallError(f"Agent {agent_name} の呼び出しに失敗しました（予期しないエラー）")

    def _execute_opencode_cli(self, agent_name: str, prompt: str) -> subprocess.CompletedProcess:
        """subprocess でOpenCode CLIを実行"""
        logger.debug(f"  コマンド実行: {self.opencode_bin} run --agent {agent_name}")

        import shutil
        cmd_path = shutil.which(self.opencode_bin) or self.opencode_bin
        cmd = [cmd_path, "run", "--agent", agent_name, prompt]

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8"
            )

            if result.returncode != 0:
                logger.warning(f"  OpenCodeが非ゼロで終了: {result.returncode}")
                logger.debug(f"  stderr: {result.stderr[:500]}")

            return result

        except subprocess.TimeoutExpired as e:
            logger.error(f"  タイムアウト: {self.timeout}秒経過")
            raise

        except Exception as e:
            logger.error(f"  subprocess実行エラー: {e}")
            raise AgentCallError(f"OpenCode CLI実行エラー: {e}")

    def _parse_response(self, raw_output: str, agent_name: str) -> Dict[str, Any]:
        """
        エージェント応答をパース（Markdown/JSON混在に対応）

        パターン:
        - Executorの応答: 「## 実装指示書」セクションを抽出
        - Coderの応答: ```python ... ``` コードブロックを抽出
        - エラー時: "ERROR:" で始まる行を検出
        """
        logger.debug(f"  レスポンスパース開始（agent={agent_name}, len={len(raw_output)}）")

        result: Dict[str, Any] = {
            "agent_name": agent_name,
            "parsed_at": datetime.now().isoformat()
        }

        # エラー検出
        error_lines = [line for line in raw_output.split('\n') if line.strip().startswith('ERROR:')]
        if error_lines:
            result["error"] = '\n'.join(error_lines)
            logger.warning(f"  エラー検出: {error_lines[0][:100]}")
            return result

        # エージェント別パース
        if agent_name == "executor":
            result.update(self._parse_executor_response(raw_output))

        elif agent_name == "coder":
            result.update(self._parse_coder_response(raw_output))

        else:
            # 汎用パース（Markdown見出しとコードブロックを抽出）
            result["sections"] = self._extract_markdown_sections(raw_output)
            result["code_blocks"] = self._extract_code_blocks(raw_output)

        return result

    def _parse_executor_response(self, raw_output: str) -> Dict[str, Any]:
        """Executor応答から実装指示書を抽出"""
        # 「## 実装指示書」セクションを探す
        match = re.search(
            r'## 実装指示書\s*\n(.*?)(?=\n##\s|\Z)',
            raw_output,
            re.DOTALL | re.IGNORECASE
        )

        if match:
            implementation_plan = match.group(1).strip()
            logger.debug(f"  実装指示書抽出成功（{len(implementation_plan)}文字）")

            # ファイルリストの抽出（例: - [ ] tools/example.py）
            file_patterns = [
                r'(?:作成|編集|新規).*?[：:]\s*([^\s]+\.py)',
                r'[-*]\s*\[.\]\s*([^\s]+\.py)',
                r'`([^\s]+\.py)`'
            ]

            files_mentioned = []
            for pattern in file_patterns:
                files_mentioned.extend(re.findall(pattern, implementation_plan, re.IGNORECASE))

            return {
                "implementation_plan": implementation_plan,
                "files_mentioned": list(set(files_mentioned))
            }

        else:
            logger.warning("  実装指示書セクションが見つかりませんでした")
            return {
                "implementation_plan": raw_output[:1000],  # 先頭1000文字をフォールバック
                "files_mentioned": []
            }

    def _parse_coder_response(self, raw_output: str) -> Dict[str, Any]:
        """Coder応答からコードブロックを抽出"""
        # 改行コードの差異 (\r\n) を \n に正規化して改行一致エラーを防止
        normalized_output = raw_output.replace('\r\n', '\n')

        # <think>...</think> タグが含まれている場合は除去
        normalized_output = re.sub(r'<think>.*?</think>', '', normalized_output, flags=re.DOTALL)

        # ```python ... ```, ```py ... ```, またはプレーンな ``` ... ``` 形式を大文字小文字を区別せず抽出
        code_blocks = re.findall(
            r'```(?:py(?:thon)?)?\s*\n(.*?)\n```',
            normalized_output,
            re.DOTALL | re.IGNORECASE
        )

        logger.debug(f"  コードブロック抽出: {len(code_blocks)}個")

        # デバッグ用：パース失敗時に生のレスポンスをファイルに保存してユーザーが確認できるようにする
        if len(code_blocks) == 0:
            try:
                debug_file = Path("log/coder_raw_failed.txt")
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                debug_file.write_text(raw_output, encoding="utf-8")
                logger.error(f"  [DEBUG] Coderパース失敗。生データを以下に保存しました: {debug_file.as_posix()}")
            except Exception as e:
                logger.error(f"  [DEBUG] デバッグ生データの書き出し失敗: {e}")

        # ファイルパス付きコードブロック（例: # filepath: tools/example.py）
        files_dict = {}
        for code_block in code_blocks:
            filepath_match = re.search(r'#\s*filepath:\s*(.+)', code_block, re.IGNORECASE)
            if filepath_match:
                filepath = filepath_match.group(1).strip()
                # filepath行を除いたコード本体
                code_body = re.sub(r'#\s*filepath:.*\n?', '', code_block, count=1)
                files_dict[filepath] = code_body.strip()

        return {
            "code_blocks": code_blocks,
            "generated_files": files_dict
        }

    def _extract_markdown_sections(self, text: str) -> Dict[str, str]:
        """Markdown見出しをセクションとして抽出"""
        sections = {}
        current_header = None
        current_content = []

        for line in text.split('\n'):
            header_match = re.match(r'^(#{1,3})\s+(.+)', line)
            if header_match:
                # 前のセクションを保存
                if current_header:
                    sections[current_header] = '\n'.join(current_content).strip()
                # 新しいセクション開始
                current_header = header_match.group(2).strip()
                current_content = []
            else:
                if current_header:
                    current_content.append(line)

        # 最後のセクションを保存
        if current_header:
            sections[current_header] = '\n'.join(current_content).strip()

        return sections

    def _extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """コードブロックを抽出（言語指定も保持）"""
        code_blocks = []

        # ```language\n...\n``` 形式
        for match in re.finditer(r'```(\w+)?\s*\n(.*?)\n```', text, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            code_blocks.append({"language": language, "code": code})

        return code_blocks

    def _validate_response(self, parsed_data: Dict[str, Any], agent_name: str) -> bool:
        """応答データの妥当性検証"""
        # エラーが含まれている場合は無効
        if "error" in parsed_data:
            return False

        # エージェント別の検証
        if agent_name == "executor":
            # 実装指示書が含まれているか
            if "implementation_plan" not in parsed_data or not parsed_data["implementation_plan"]:
                logger.warning("  実装指示書が空です")
                return False

        elif agent_name == "coder":
            # コードブロックが含まれているか
            if "code_blocks" not in parsed_data or not parsed_data["code_blocks"]:
                logger.warning("  コードブロックが空です")
                return False

        return True

    def get_call_history(self) -> List[Dict[str, Any]]:
        """呼び出し履歴を取得（デバッグ用）"""
        return self.call_history

    def save_call_history(self, filepath: Path):
        """呼び出し履歴をJSONファイルに保存"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.call_history, f, indent=2, ensure_ascii=False)
        logger.info(f"呼び出し履歴を保存: {filepath}")


# ===========================
# テスト用CLI
# ===========================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 3:
        print("使い方: python agent_client.py <agent_name> <prompt>")
        print("例: python agent_client.py executor 'Issue ARCH-001を実装'")
        sys.exit(1)

    agent_name = sys.argv[1]
    prompt = sys.argv[2]

    client = AgentClient()
    try:
        response = client.call_agent(agent_name, prompt)
        print("\n" + "=" * 60)
        print("エージェント応答")
        print("=" * 60)
        print(f"エージェント: {response.agent_name}")
        print(f"成功: {response.success}")
        print(f"実行時間: {response.execution_time:.2f}秒")
        print(f"\nパース結果:")
        print(json.dumps(response.parsed_data, indent=2, ensure_ascii=False))
        print("=" * 60)

    except AgentCallError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
