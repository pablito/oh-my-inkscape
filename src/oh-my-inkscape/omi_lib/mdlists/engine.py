# SPDX-License-Identifier: GPL-3.0-or-later
"""typeset(): Markdown + style → an SVG <g> with hanging-indent text, in millimetre units.

Two modes:
  metrics  line breaks computed from the font files; every line is a positioned <tspan>.
  flowed   every paragraph is SVG2 auto-wrapping text (inline-size). Inkscape decides the
           line breaks: the caller supplies `export_plain(tree)`, a function that runs
           Inkscape's plain-SVG export on a probe document and returns the parsed result,
           from which line counts (to stack items) and SVG 1.1 fallback lines are read.
"""
import sys
from dataclasses import dataclass

from lxml import etree

from .fonts import Fonts
from .layout import Layout, Typesetter
from .markdown import parse_markdown, refine_text
from .svgbuild import SVG_NS, build_content, standalone_svg


def _stderr(message):
    print(message, file=sys.stderr)


@dataclass
class TypesetResult:
    content: etree._Element  # <g> without id/transform; 1 user unit = 1 mm, origin = block top-left
    width: float
    height: float
    layout: Layout
    typesetter: Typesetter
    blocks: list


def read_fallback(doc):
    """Line counts and fallback line tspans per <text> id, from Inkscape's plain-SVG export."""
    counts, fallback = {}, {}
    for text in doc.iter(f"{{{SVG_NS}}}text"):
        tid = text.get("id")
        lines = [t for t in text.findall(f"{{{SVG_NS}}}tspan") if t.get("y") is not None]
        counts[tid] = max(1, len({t.get("y") for t in lines}))
        if lines:
            for t in lines:
                for el in t.iter():
                    el.attrib.pop("id", None)
            fallback[tid] = (float(lines[0].get("y")), lines)
    return counts, fallback


def typeset(markdown, style, mode="metrics", prefix="mdtext", export_plain=None, log=_stderr):
    """`style` must be complete (see style.merge_style)."""
    if mode not in ("metrics", "flowed"):
        raise ValueError(f"unknown mode {mode!r}")
    blocks = parse_markdown(markdown)
    refine_text(blocks, style)
    fonts = Fonts(style, log)
    ts = Typesetter(style, fonts, log)

    layout = Layout(ts, mode=mode, prefix=prefix)
    height = layout.run(blocks)
    fallback = None
    if mode == "flowed":
        if export_plain is None:
            raise ValueError("flowed mode needs export_plain")
        probe = standalone_svg(build_content(layout, ts, "flowed"), style["width_mm"], max(height, 1))
        counts, fallback = read_fallback(export_plain(probe))
        layout = Layout(ts, line_counts=counts, mode="flowed", prefix=prefix)
        height = layout.run(blocks)
    fonts.report_missing()
    content = build_content(layout, ts, mode, fallback)
    return TypesetResult(content, style["width_mm"], height, layout, ts, blocks)


def flowed_probe(result, prefix):
    """Probe document of `result`'s paragraphs as auto-wrapping text (to compare line breaks)."""
    layout = Layout(result.typesetter, mode="flowed", prefix=prefix)
    layout.run(result.blocks)
    return standalone_svg(build_content(layout, result.typesetter, "flowed"), result.width, max(result.height, 1))
