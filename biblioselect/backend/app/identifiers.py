"""Validación de ISBN-10, ISBN-13 e ISSN mediante su dígito verificador."""
from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[\s-]")


def normalize_identifier(value: str) -> str:
    """Quita espacios y guiones y pasa a mayúsculas (la X final de ISBN-10/ISSN es válida)."""
    return _SEPARATORS.sub("", value).upper()


def is_valid_isbn10(value: str) -> bool:
    s = normalize_identifier(value)
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
    return total % 11 == 0


def is_valid_isbn13(value: str) -> bool:
    s = normalize_identifier(value)
    if not re.fullmatch(r"\d{13}", s):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s))
    return total % 10 == 0


def is_valid_isbn(value: str) -> bool:
    return is_valid_isbn10(value) or is_valid_isbn13(value)


def is_valid_issn(value: str) -> bool:
    s = normalize_identifier(value)
    if not re.fullmatch(r"\d{7}[\dX]", s):
        return False
    total = sum(int(c) * (8 - i) for i, c in enumerate(s[:7]))
    check = (11 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    return s[7] == expected
