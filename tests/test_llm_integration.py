#!/usr/bin/env python3
"""
test_llm_integration.py - LLM（Ollama）の実呼び出しを伴う検証インテグレーションテスト
"""

import pytest
import shutil
from tools.agent_client import AgentClient

@pytest.mark.llm
def test_pm_decomposition_format_with_llm():
    """PMエージェントを実際に呼び出してタスク分解結果をアサーションする"""
    if not shutil.which("opencode"):
        pytest.skip("Windowsホスト環境に 'opencode' コマンドが見つからないため、このテストをスキップします")
        
    client = AgentClient()
    
    prompt = (
        "projects/test_file_grep プロジェクトに、新機能として XML出力フォーマット機能 を追加したいです。 "
        "パーサーの対応、フォーマッターの対応、そして最後に結合テストを行いたいです。 "
        "依存関係を考慮した最小のステップに分解してタスク登録用のコマンドを提案してください。"
    )
    
    try:
        response = client.call_agent("pm", prompt)
        
        # 呼び出し結果が成功であること
        assert response.success is True
        
        output = response.raw_output
        
        # 表記揺れに配慮しつつ、決定論的にチェック可能不可欠な項目をアサーション
        # 1. 登録コマンド名が含まれるか
        assert "add-task.py" in output
        
        # 2. タスク内容が適切に分解されているキーワードが含まれるか
        assert any(x in output for x in ["パーサー", "parser", "Parser"])
        assert any(x in output for x in ["フォーマッター", "formatter", "Formatter"])
        assert any(x in output for x in ["テスト", "test", "Test"])
        
        # 3. 依存関係のオプションである blockedby が含まれるか
        assert any(x in output for x in ["blockedby", "--blockedby"])
        
    except Exception as e:
        pytest.fail(f"LLMエージェントの呼び出し中にエラーが発生しました: {e}")
