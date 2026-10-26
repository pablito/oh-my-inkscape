# SPDX-License-Identifier: GPL-3.0-or-later
"""Markdown → SVG text with hanging indents (engine of the Markdown Lists extension and md2svg CLI)."""
from .engine import typeset, TypesetResult  # noqa: F401
from .style import DEFAULT_STYLE, merge_style  # noqa: F401
