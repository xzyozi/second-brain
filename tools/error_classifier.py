#!/usr/bin/env python3
"""
error_classifier.py - オーケストレーター用エラー自動分類モジュール

例外オブジェクトまたはエラーログを解析し、エラーの種別
(SYNTAX / CONSTRAINT / TEST_FAILURE / RUNTIME) を決定論的に分類します。
"""

import ast
from enum import Enum, auto
from typing import Any, Optional


class ErrorCategory(Enum):
    """エラーカテゴリの列挙型"""
    SYNTAX = auto()       # L1: 構文エラー (SyntaxError, IndentationError, 記号エラー)
    CONSTRAINT = auto()   # L2: CCR制約違反 (型ヒント欠落, 裸のexcept, 禁止インポート等)
    TEST_FAILURE = auto() # L3: 実行テスト失敗 (AssertionError, test collection error 等)
    RUNTIME = auto()      # 実行時例外 (FileNotFoundError, AttributeError 等)


class ConstraintViolationError(Exception):
    """CCR制約違反を表すカスタム例外"""
    def __init__(self, message: str, violations: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.violations = violations or []


class TaskTestFailureError(Exception):
    """テスト実行失敗を表すカスタム例外"""
    def __init__(self, message: str, test_output: str | None = None):
        super().__init__(message)
        self.test_output = test_output or ""


class ErrorClassifier:
    """エラー分類器"""

    @staticmethod
    def classify(error: Exception | str) -> ErrorCategory:
        """
        例外オブジェクトまたはエラーメッセージ文字列を受け取り、ErrorCategory を返す
        """
        if isinstance(error, (SyntaxError, IndentationError)):
            return ErrorCategory.SYNTAX

        if isinstance(error, ConstraintViolationError):
            return ErrorCategory.CONSTRAINT

        if isinstance(error, TaskTestFailureError):
            return ErrorCategory.TEST_FAILURE

        if isinstance(error, AssertionError):
            return ErrorCategory.TEST_FAILURE

        # 文字列判定（エラーログ・出力からの逆引）
        err_str = str(error)

        if "SyntaxError:" in err_str or "IndentationError:" in err_str or "invalid character" in err_str:
            return ErrorCategory.SYNTAX

        if "CCR (制約遵守率)" in err_str or "Constraint Violation" in err_str:
            return ErrorCategory.CONSTRAINT

        if "FAILED" in err_str or "AssertionError" in err_str or "Interrupted: 1 error during collection" in err_str or "Tests failed" in err_str:
            return ErrorCategory.TEST_FAILURE

        return ErrorCategory.RUNTIME

    @staticmethod
    def extract_error_snippet(error: Exception | str, err_category: ErrorCategory) -> str:
        """
        エラー分類に応じたノイズの少ないエラー要約（スニペット）を抽出する
        """
        err_str = str(error)

        if err_category == ErrorCategory.SYNTAX:
            # SyntaxError の行番号・メッセージ部分を抽出
            lines = [line for line in err_str.split("\n") if "SyntaxError" in line or "Line" in line or "line" in line or "^" in line]
            return "\n".join(lines) if lines else err_str[:300]

        elif err_category == ErrorCategory.CONSTRAINT:
            # 不適合項目リストのみ抽出
            return err_str

        elif err_category == ErrorCategory.TEST_FAILURE:
            # FAILED 行や E 行のみ抽出してプロンプトのトークン数を削減
            lines = err_str.split("\n")
            failure_lines = [line for line in lines if line.startswith("E ") or "FAILED" in line or "SyntaxError:" in line or "AssertionError" in line]
            return "\n".join(failure_lines) if failure_lines else err_str[:600]

        return err_str[:400]
