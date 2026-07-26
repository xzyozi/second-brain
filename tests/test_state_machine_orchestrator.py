#!/usr/bin/env python3
"""
test_state_machine_orchestrator.py - ステートマシンおよびセルフヒーリング機能のテスト
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from tools.orchestrator import IssueOrchestrator, State
from tools.sanitizer import CodeSanitizer
from tools.error_classifier import ErrorClassifier, ErrorCategory


def test_code_sanitizer_integration():
    raw_code = "def parse() → dict:\n    return {'a': 1}"
    sanitized = CodeSanitizer.sanitize(raw_code)
    assert "-> dict:" in sanitized


def test_error_classifier_integration():
    syntax_err = SyntaxError("invalid syntax")
    assert ErrorClassifier.classify(syntax_err) == ErrorCategory.SYNTAX

    test_err_str = "FAILED projects/test_file_grep/test_xml_parser.py - AssertionError"
    assert ErrorClassifier.classify(test_err_str) == ErrorCategory.TEST_FAILURE


def test_orchestrator_healing_prompt_builder():
    orch = IssueOrchestrator()
    base_prompt = "Pythonコードを生成してください"
    err = SyntaxError("closing parenthesis '}' does not match opening parenthesis '(' on line 11")
    
    prompt = orch._build_healing_prompt(base_prompt, "", err, ErrorCategory.SYNTAX)
    assert "【修復依頼: 構文エラー (SyntaxError)】" in prompt
    assert "SyntaxError:" in prompt or "parenthesis" in prompt
