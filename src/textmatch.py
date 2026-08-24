"""Matching de palavras-chave por word-boundary.

Evita falsos positivos como a keyword "R" batendo em qualquer texto que
contenha a letra R em qualquer palavra (ex.: "para", "trabalhar").
Aceita plural simples (s/es) para não perder matches óbvios como
"modelo"/"modelos".
"""
from __future__ import annotations

import re


def _pattern_for(keyword: str) -> re.Pattern:
    escaped = re.escape(keyword.strip())
    return re.compile(rf"\b{escaped}(e?s)?\b", re.IGNORECASE)


def contains_keyword(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    return _pattern_for(keyword).search(text) is not None


def matching_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if contains_keyword(text, kw)]
