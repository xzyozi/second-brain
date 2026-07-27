#!/usr/bin/env python3
"""
sanitizer.py - LLM生成コードのサニタイズ・正規化モジュール

モデルが出力したコードに含まれる Unicode 記号の誤用（→ ➔ -> 等）や、
不要なコードブロック記号・制御文字のクレンジングを自動で行います。
"""

import re


class CodeSanitizer:
    """コードの無害化・正規化クラス"""

    # 置換対象の Unicode 記号マップ
    UNICODE_REPLACEMENTS = {
        "→": "->",  # U+2192 (Rightwards Arrow)
        "⇒": "->",  # U+21D2
        "➔": "->",  # U+2794
        "➜": "->",  # U+279C
        "’": "'",   # Right Single Quotation Mark
        "‘": "'",   # Left Single Quotation Mark
        "”": '"',   # Right Double Quotation Mark
        "“": '"',   # Left Double Quotation Mark
        "：": ":",   # 全角コロン
        "　": " ",   # 全角スペース
    }

    @classmethod
    def sanitize(cls, code_str: str) -> str:
        """
        コード文字列のサニタイズ処理を行う
        
        - Unicode 特殊記号の標準 ASCII 化
        - 先頭/末尾の不必要なマークダウン囲みの除去
        """
        if not code_str:
            return ""

        sanitized = code_str

        # 1. マークダウンコードブロックの剥ぎ取り（もし含まれている場合）
        match = re.search(r"```(?:py(?:thon)?)?\s*\n(.*?)\n```", sanitized, re.DOTALL | re.IGNORECASE)
        if match:
            sanitized = match.group(1)
        else:
            # 単一の ``` の除去
            sanitized = re.sub(r"^```(?:py(?:thon)?)?\s*\n?", "", sanitized, flags=re.MULTILINE | re.IGNORECASE)
            sanitized = re.sub(r"\n?```$", "", sanitized, flags=re.MULTILINE)

        # 2. Unicode 記号の自動置換
        for char, replacement in cls.UNICODE_REPLACEMENTS.items():
            if char in sanitized:
                sanitized = sanitized.replace(char, replacement)

        # 3. 裸の単一識別子行（例: 行全体が `json` や `sys` のみ）を削除
        sanitized = re.sub(r"^\s*(?:json|sys|os|re|ast|pathlib)\s*$", "", sanitized, flags=re.MULTILINE)

        # 4. 数値リテラルの先頭ゼロ (01, 02 ➔ 1, 2) の自動修正 (文字列内部は除外)
        sanitized = re.sub(r"(?<=[\s\[\(,:=])0([1-9][0-9]*)\b", r"\1", sanitized)

        return sanitized.strip()
