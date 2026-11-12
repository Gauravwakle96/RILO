"""Bundled OFL Unicode fonts; never silently replace missing characters in reports."""

from __future__ import annotations

from functools import cache
from html import escape
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


@cache
def fonts() -> tuple:
    values = []
    for family in ("NotoSans", "NotoSansDevanagari", "NotoSansArabic"):
        font = TTFont(
            "Rilo" + family, str(Path(__file__).parent / "fonts" / (family + "-Regular.ttf"))
        )
        pdfmetrics.registerFont(font)
        values.append(font)
    return tuple(values)


def paragraph_text(text: str) -> str:
    registered = fonts()
    spans = []
    current = None
    chunk = ""
    for char in text:
        font = next(
            (
                value
                for value in registered
                if ord(char) in value.face.charToGlyph or char in "\n\t\r"
            ),
            None,
        )
        if font is None:
            raise ValueError(
                f"PDF font does not support character U+{ord(char):04X}. Export Markdown or JSON to preserve this text."
            )
        if current != font.fontName:
            if chunk:
                spans.append(
                    f'<font name="{current}">{escape(chunk).replace(chr(10), "<br/>")}</font>'
                )
            current, chunk = font.fontName, ""
        chunk += char
    if chunk:
        spans.append(f'<font name="{current}">{escape(chunk).replace(chr(10), "<br/>")}</font>')
    return "".join(spans)
