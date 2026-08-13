#!/usr/bin/env python3
"""
test_ccr_evaluator.py - ConstraintComplianceValidator の単体テスト
"""

import pytest
from tools.eval_ccr import ConstraintComplianceValidator


def test_type_annotations_checker():
    valid_code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    validator = ConstraintComplianceValidator(valid_code)
    passed, _ = validator.check_type_annotations()
    assert passed is True

    invalid_code = """
def add(a, b):
    return a + b
"""
    validator_inv = ConstraintComplianceValidator(invalid_code)
    passed_inv, msg = validator_inv.check_type_annotations()
    assert passed_inv is False
    assert "add(arg: a)" in msg


def test_no_bare_except_checker():
    unsafe_code = """
try:
    x = 1 / 0
except:
    pass
"""
    validator = ConstraintComplianceValidator(unsafe_code)
    passed, _ = validator.check_no_bare_except()
    assert passed is False

    safe_code = """
try:
    x = 1 / 0
except ZeroDivisionError as e:
    logger.error(e)
"""
    validator_safe = ConstraintComplianceValidator(safe_code)
    passed_safe, _ = validator_safe.check_no_bare_except()
    assert passed_safe is True


def test_no_mutable_defaults_checker():
    bad_code = """
def append_item(item: str, items: list = []) -> list:
    items.append(item)
    return items
"""
    validator = ConstraintComplianceValidator(bad_code)
    passed, _ = validator.check_no_mutable_defaults()
    assert passed is False

    good_code = """
def append_item(item: str, items: list | None = None) -> list:
    if items is None:
        items = []
    items.append(item)
    return items
"""
    validator_good = ConstraintComplianceValidator(good_code)
    passed_good, _ = validator_good.check_no_mutable_defaults()
    assert passed_good is True


def test_evaluate_rules_summary():
    code = """
def calculate_total(prices: list[float]) -> float:
    \"\"\"Calculate total price.\"\"\"
    return sum(prices)
"""
    validator = ConstraintComplianceValidator(code)
    rules = ["type_annotations", "docstrings", "no_bare_except", "no_print"]
    summary = validator.evaluate_rules(rules)
    assert summary["ccr_score"] == 100.0
    assert summary["passed_count"] == 4
    assert summary["total_count"] == 4
