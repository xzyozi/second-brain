#!/usr/bin/env python3
"""
test_sanitizer.py - CodeSanitizer の単体テスト
"""

import pytest
from tools.sanitizer import CodeSanitizer


def test_sanitize_unicode_arrow():
    code_with_arrow = "def parse_data(x: int) → dict:\n    return {'val': x}"
    sanitized = CodeSanitizer.sanitize(code_with_arrow)
    assert "-> dict:" in sanitized
    assert "→" not in sanitized


def test_sanitize_quotes_and_colons():
    code_with_fullwidth = "def foo()：\n    val = “hello”\n    return val"
    sanitized = CodeSanitizer.sanitize(code_with_fullwidth)
    assert "def foo():" in sanitized
    assert 'val = "hello"' in sanitized


def test_sanitize_markdown_code_block():
    raw_markdown = "Here is the code:\n```python\ndef hello():\n    print('hi')\n```\nHope it helps!"
    sanitized = CodeSanitizer.sanitize(raw_markdown)
    assert sanitized.startswith("def hello():")
    assert sanitized.endswith("print('hi')")
    assert "```" not in sanitized
