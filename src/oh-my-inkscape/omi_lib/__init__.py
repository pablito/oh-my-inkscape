# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared code for the Oh My Inkscape extensions."""
import os
import sys

__version__ = "0.1.0"

try:  # prefer an installed fontTools, fall back to the vendored copy (Inkscape's Python lacks it)
    import fontTools  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor"))
