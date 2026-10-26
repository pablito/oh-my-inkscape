# SPDX-License-Identifier: GPL-3.0-or-later
"""Style settings: defaults, merging and validation. Lengths in mm, sizes in pt."""
import copy

from ..i18n import _

DEFAULT_STYLE = {
    "font_family": "sans-serif",
    "fonts": {},
    "font_size_pt": 9,
    "line_height": 1.2,
    "width_mm": 90,
    "color": "#000000",
    "paragraph_gap_mm": 1.5,
    "item_gap_mm": 0.5,
    "list_indent_mm": 0,
    "nested_indent_mm": 0,
    "marker_gap": "\u2002",
    "nobreak": [r"\[[^\]\n]*\]", r"(?<!\S)[−+±–-]?\d(?:[\d.,:/]*\d)?%? \S+"],
    "smart_punctuation": True,
    "hang": "list",
    "bullets": ["•", "–", "▪"],
    "marker_bold": False,
    "safety": 1.0,
    "headings": {
        "1": {"size_pt": 12, "bold": True, "italic": False, "gap_before_mm": 3, "gap_after_mm": 1.5},
        "2": {"size_pt": 10.5, "bold": True, "italic": False, "gap_before_mm": 2.5, "gap_after_mm": 1},
        "3": {"size_pt": 9, "bold": True, "italic": False, "gap_before_mm": 2, "gap_after_mm": 0.8},
    },
}


def deep_merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def merge_style(*layers):
    """DEFAULT_STYLE overlaid with each layer in order; raises ValueError on invalid values."""
    style = copy.deepcopy(DEFAULT_STYLE)
    for layer in layers:
        style = deep_merge(style, layer)
    validate(style)
    return style


def validate(style):
    if style["hang"] not in ("list", "item"):
        raise ValueError(_("'hang' must be 'list' or 'item'"))
    if not style["bullets"]:
        raise ValueError(_("'bullets' needs at least one marker"))
    for key in ("font_size_pt", "line_height", "width_mm", "safety"):
        if not isinstance(style[key], (int, float)) or style[key] <= 0:
            raise ValueError(_("'{key}' must be a positive number").format(key=key))
    if not style["headings"]:
        raise ValueError(_("'headings' needs at least one level"))
