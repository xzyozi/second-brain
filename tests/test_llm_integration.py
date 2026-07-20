#!/usr/bin/env python3
"""
test_llm_integration.py - LLM（Ollama）の実呼び出しを伴う検証インテグレーションテスト

基本的な動作確認テスト。シナリオベースの詳細検証は test_llm_scenarios.py を参照。
"""

import pytest
from tools.agent_client import AgentClient

@pytest.mark.llm
def test_pm_decomposition_format_with_llm(opencode_available):
    """PMエージェントを実際に呼び出してタスク分解結果をアサーションする"""
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")
        
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

@pytest.mark.llm
def test_executor_format_with_llm(opencode_available):
    """executorエージェントを実際に呼び出して実装指示書のフォーマットをアサーションする"""
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")
        
    client = AgentClient()
    
    # 実在タスク TFG-001 の情報をコンテキストとして渡す
    prompt = (
        "以下のタスクに対する実装指示書を作成してください。\n\n"
        "ID: TFG-001\n"
        "タイトル: docx/xlsx/pptxの「テキスト構造抽出精度」検証のためのアプローチ確立\n"
        "プロジェクト: test_file_grep\n\n"
        "出力は必ず「## 実装指示書」セクションから始めてください。"
    )
    
    try:
        response = client.call_agent("executor", prompt)
        
        # 呼び出し結果が成功であること
        assert response.success is True
        assert "implementation_plan" in response.parsed_data
        assert len(response.parsed_data["implementation_plan"]) > 0
        
    except Exception as e:
        pytest.fail(f"LLMエージェントの呼び出し中にエラーが発生しました: {e}")

@pytest.mark.llm
def test_coder_format_with_llm(opencode_available):
    """coderエージェントを実際に呼び出してコード生成とパース結果をアサーションする"""
    if not opencode_available:
        pytest.skip("opencode が PATH に見つからないためスキップします")
        
    client = AgentClient()
    
    # # filepath: の強制指示なしで依頼し、より実環境に近い条件で確認する
    prompt = (
        "tools/example.py に対して、文字列の長さを返す length(s: str) -> int 関数を追加してください。 "
        "コードブロックには実際のPythonコードのみを含めてください。"
    )
    
    try:
        response = client.call_agent("coder", prompt)
        
        # 呼び出し結果が成功であること
        assert response.success is True
        assert "code_blocks" in response.parsed_data
        assert len(response.parsed_data["code_blocks"]) > 0
        
        # 生成コードに length 関数が含まれているか
        all_code = "\n".join(response.parsed_data["code_blocks"])
        assert "length" in all_code, (
            f"生成コードに 'length' が含まれていません\ncode: {all_code[:300]}"
        )
        
    except Exception as e:
        pytest.fail(f"LLMエージェントの呼び出し中にエラーが発生しました: {e}")

