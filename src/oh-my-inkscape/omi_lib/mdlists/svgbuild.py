# SPDX-License-Identifier: GPL-3.0-or-later
"""SVG elements for a laid-out block, plus Inkscape fallback lines for auto-wrapping text."""
import copy

from lxml import etree

from .layout import merge_runs
from .markdown import Run

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def run_style_attr(bold, italic):
    parts = []
    if bold:
        parts.append("font-weight:bold")
    if italic:
        parts.append("font-style:italic")
    return ";".join(parts)


def add_runs(parent, runs):
    for r in runs:
        st = run_style_attr(r.bold, r.italic)
        if st:
            t = etree.SubElement(parent, f"{{{SVG_NS}}}tspan", style=st)
            t.text = r.text
        else:
            children = list(parent)
            if children:
                children[-1].tail = (children[-1].tail or "") + r.text
            else:
                parent.text = (parent.text or "") + r.text


def build_content(layout, ts, mode, fallback=None):
    s = ts.s
    root_g = etree.Element(f"{{{SVG_NS}}}g")
    groups = {None: root_g}
    for gid, parent in layout.groups:
        g = etree.SubElement(groups[parent], f"{{{SVG_NS}}}g", id=gid)
        groups[gid] = g
    base_style = f"font-family:'{s['font_family']}';fill:{s['color']}"
    for p in layout.placed:
        size = ts.size_mm(p.para.heading)
        parent = groups[p.group]
        style = f"{base_style};font-size:{fmt(size)}px;line-height:{s['line_height']}"
        if p.para.heading and ts.heading_style(p.para.heading).get("bold", True):
            style += ";font-weight:bold"
        if p.para.heading and ts.heading_style(p.para.heading).get("italic", False):
            style += ";font-style:italic"
        lh = size * s["line_height"]
        if mode == "metrics":
            text = etree.SubElement(parent, f"{{{SVG_NS}}}text", id=p.pid, x=fmt(p.x), y=fmt(p.baseline),
                                    style=style)
            text.set(XML_SPACE, "preserve")
            if p.marker:
                mt = etree.SubElement(text, f"{{{SVG_NS}}}tspan", id=f"{p.pid}-m", x=fmt(p.marker_x),
                                      y=fmt(p.baseline))
                if p.marker_bold:
                    mt.set("style", "font-weight:bold")
                mt.text = p.marker
            for n, line in enumerate(p.lines):
                lt = etree.SubElement(text, f"{{{SVG_NS}}}tspan", id=f"{p.pid}-l{n + 1}", x=fmt(p.x),
                                      y=fmt(p.baseline + n * lh))
                if p.para.heading:
                    line = [Run(r.text, r.bold and not ts.heading_style(p.para.heading).get("bold", True),
                                r.italic and not ts.heading_style(p.para.heading).get("italic", False))
                            for r in line]
                add_runs(lt, merge_runs(line))
        else:
            if p.marker:
                mt = etree.SubElement(parent, f"{{{SVG_NS}}}text", id=f"{p.pid}-m", x=fmt(p.marker_x),
                                      y=fmt(p.baseline), style=style + (";font-weight:bold" if p.marker_bold else ""))
                mt.set(XML_SPACE, "preserve")
                mt.text = p.marker
            text = etree.SubElement(parent, f"{{{SVG_NS}}}text", id=p.pid, x=fmt(p.x), y=fmt(p.baseline),
                                    style=f"{style};inline-size:{fmt(p.width)};white-space:pre-wrap")
            text.set(XML_SPACE, "preserve")
            runs = p.para.runs
            if p.para.heading:
                h = ts.heading_style(p.para.heading)
                runs = [Run(r.text, r.bold and not h.get("bold", True), r.italic and not h.get("italic", False))
                        for r in runs]
            if fallback and p.pid in fallback:
                add_fallback_lines(text, fallback[p.pid][1], fallback[p.pid][0], p.baseline)
            else:
                add_runs(text, merge_runs(runs))
    return root_g


def standalone_svg(content, width, height):
    nsmap = {None: SVG_NS, "inkscape": INKSCAPE_NS}
    svg = etree.Element(f"{{{SVG_NS}}}svg", nsmap=nsmap, width=f"{fmt(width)}mm", height=f"{fmt(height)}mm",
                        viewBox=f"0 0 {fmt(width)} {fmt(height)}", version="1.1")
    svg.append(content)
    return etree.ElementTree(svg)


def add_fallback_lines(text, lines, first_y, baseline):
    """SVG 1.1 fallback: Inkscape's own line breaks as positioned tspans, so browsers and
    other renderers (which ignore inline-size) show the same lines. Inkscape itself
    re-flows from inline-size and rewrites these when the file is saved."""
    shift = baseline - first_y
    for line in lines:
        t = copy.deepcopy(line)
        t.set("y", fmt(float(t.get("y")) + shift))
        text.append(t)
