#!/usr/bin/env python3
"""
eval_ccr.py - 制約遵守率 (CCR: Constraint Compliance Rate) 自動評価エンジン

Pythonコード（AST / 動的検査）に対して、構文・スタイル、構造・アーキテクチャ、
安全性・堅牢性、ドメイン固有ルールの4カテゴリの制約チェックを行い、CCRスコアを算出します。
"""

import ast
import re
from typing import Any, Callable


class ConstraintComplianceValidator:
    """生成コードの AST / 構文解析・動的ルール検証クラス"""

    def __init__(self, code_str: str):
        self.code_str = code_str
        self.tree: ast.AST | None = None
        self.parse_error: str | None = None
        try:
            self.tree = ast.parse(code_str)
        except Exception as e:
            self.parse_error = str(e)

    def check_syntax_valid() -> tuple[bool, str]:
        """Pythonの構文として正常にパースできるか"""
        if self.parse_error:
            return False, f"SyntaxError: {self.parse_error}"
        return True, "Valid Python Syntax"

    def check_type_annotations(self) -> tuple[bool, str]:
        """【構文・スタイル】すべての関数・メソッドに引数と返り値の型ヒントが付与されているか"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        missing = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                # 引数の型ヒント
                for arg in node.args.args:
                    if arg.arg != "self" and arg.annotation is None:
                        missing.append(f"{node.name}(arg: {arg.arg})")
                # 返り値の型ヒント
                if node.returns is None:
                    missing.append(f"{node.name}(return)")
        if missing:
            return False, f"Missing type annotations in: {', '.join(missing)}"
        return True, "All functions and parameters have type annotations"

    def check_docstrings(self) -> tuple[bool, str]:
        """【構文・スタイル】すべての関数・クラスに Docstring が定義されているか"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        missing = []
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if not ast.get_docstring(node):
                    missing.append(node.name)
        if missing:
            return False, f"Missing docstring in: {', '.join(missing)}"
        return True, "All functions and classes have docstrings"

    def check_naming_conventions(self) -> tuple[bool, str]:
        """【構文・スタイル】関数のスネークケース命名規則のチェック"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        snake_pattern = re.compile(r"^[a-z_][a-z0-9_]*$")
        invalid = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if not snake_pattern.match(node.name) and not node.name.startswith("__"):
                    invalid.append(node.name)
        if invalid:
            return False, f"Non-snake_case function names: {', '.join(invalid)}"
        return True, "All functions follow snake_case naming convention"

    def check_dataclass_usage(self) -> tuple[bool, str]:
        """【構造・アーキテクチャ】すべてのクラスに @dataclass デコレータが付与されているか"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        invalid = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                decorator_names = []
                for d in node.decorator_list:
                    if isinstance(d, ast.Name):
                        decorator_names.append(d.id)
                    elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
                        decorator_names.append(d.func.id)
                if "dataclass" not in decorator_names:
                    invalid.append(node.name)
        if invalid:
            return False, f"Classes missing @dataclass: {', '.join(invalid)}"
        return True, "All classes use @dataclass decorator"

    def check_no_bare_except(self) -> tuple[bool, str]:
        """【安全性・堅牢性】裸の except: または except Exception: pass の禁止"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        violations = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    violations.append("bare except")
                elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        violations.append(f"except {node.type.id}: pass")
        if violations:
            return False, f"Unsafe exception handler found: {', '.join(violations)}"
        return True, "No bare or swallowed exceptions found"

    def check_no_mutable_defaults(self) -> tuple[bool, str]:
        """【安全性・堅牢性】デフォルト引数に可変オブジェクト (list/dict/set) を使用していないか"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        violations = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        violations.append(node.name)
        if violations:
            return False, f"Mutable default arguments in: {', '.join(set(violations))}"
        return True, "No mutable default arguments used"

    def check_no_print(self) -> tuple[bool, str]:
        """【ドメイン固有】print() ステートメントの使用禁止"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    return False, "print() function call found"
        return True, "No print() calls found"

    def check_forbidden_imports(self, forbidden_list: list[str]) -> tuple[bool, str]:
        """【ドメイン固有】指定されたインポートの不使用チェック"""
        if not self.tree:
            return False, "Syntax error prevents AST check"
        found = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_list:
                        found.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_list:
                    found.append(node.module)
        if found:
            return False, f"Forbidden imports used: {', '.join(set(found))}"
        return True, f"No forbidden imports ({', '.join(forbidden_list)}) used"

    def evaluate_rules(self, rules: list[str | dict[str, Any]]) -> dict[str, Any]:
        """
        リストで指定されたルールを評価し、CCRスコアを算出する。
        
        rules の要素例:
        - "type_annotations"
        - "docstrings"
        - "snake_case"
        - "dataclass"
        - "no_bare_except"
        - "no_mutable_defaults"
        - "no_print"
        - {"forbidden_imports": ["requests", "python-docx"]}
        """
        rule_map: dict[str, Callable[[], tuple[bool, str]]] = {
            "type_annotations": self.check_type_annotations,
            "docstrings": self.check_docstrings,
            "snake_case": self.check_naming_conventions,
            "dataclass": self.check_dataclass_usage,
            "no_bare_except": self.check_no_bare_except,
            "no_mutable_defaults": self.check_no_mutable_defaults,
            "no_print": self.check_no_print,
        }

        results = []
        passed_count = 0
        total_count = 0

        for rule in rules:
            total_count += 1
            if isinstance(rule, str):
                if rule in rule_map:
                    passed, msg = rule_map[rule]()
                    results.append({"rule": rule, "passed": passed, "message": msg})
                    if passed:
                        passed_count += 1
                else:
                    results.append({"rule": rule, "passed": False, "message": f"Unknown rule: {rule}"})
            elif isinstance(rule, dict):
                if "forbidden_imports" in rule:
                    forbidden = rule["forbidden_imports"]
                    passed, msg = self.check_forbidden_imports(forbidden)
                    results.append({"rule": "forbidden_imports", "passed": passed, "message": msg})
                    if passed:
                        passed_count += 1

        ccr_rate = (passed_count / total_count * 100.0) if total_count > 0 else 100.0
        return {
            "ccr_score": ccr_rate,
            "passed_count": passed_count,
            "total_count": total_count,
            "results": results,
        }
