#!/usr/bin/env python3
"""
test_error_classifier.py - ErrorClassifier の単体テスト
"""

import pytest
from tools.error_classifier import ErrorClassifier, ErrorCategory, ConstraintViolationError, TaskTestFailureError


def test_classify_syntax_error():
    err = SyntaxError("invalid syntax")
    assert ErrorClassifier.classify(err) == ErrorCategory.SYNTAX

    err_str = "File 'test.py', line 12\n    }\nSyntaxError: closing parenthesis '}' does not match"
    assert ErrorClassifier.classify(err_str) == ErrorCategory.SYNTAX


def test_classify_constraint_error():
    err = ConstraintViolationError("CCR (制約遵守率) が基準値を下回りました: 70%")
    assert ErrorClassifier.classify(err) == ErrorCategory.CONSTRAINT


def test_classify_test_failure_error():
    err = TaskTestFailureError("Tests failed: 1 error during collection")
    assert ErrorClassifier.classify(err) == ErrorCategory.TEST_FAILURE

    err_assert = AssertionError("Expected 5 but got 3")
    assert ErrorClassifier.classify(err_assert) == ErrorCategory.TEST_FAILURE


def test_extract_error_snippet_syntax():
    err_log = """
==================================== ERRORS ====================================
E File "/home/user/test.py", line 13
E SyntaxError: closing parenthesis '}' does not match opening parenthesis '(' on line 11
"""
    snippet = ErrorClassifier.extract_error_snippet(err_log, ErrorCategory.SYNTAX)
    assert "SyntaxError:" in snippet
    assert "line 13" in snippet
