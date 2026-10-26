# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from omi_lib.mdlists.engine import read_fallback, typeset
from omi_lib.mdlists.style import merge_style
from omi_lib.mdlists.svgbuild import SVG_NS

LONG = ("1. Determine odds.\n"
        "2. Roll one die, then apply every modifier listed on the chart; results with A* or D* "
        "refer to the legend below the table and may force a retreat.\n"
        "   a) Retreat first.\n"
        "   b) Then advance after combat if the hex is vacant and nothing else blocks it.\n")


def lines_of(content, pid):
    text = next(t for t in content.iter(f"{{{SVG_NS}}}text") if t.get("id") == pid)
    return [t for t in text if t.get("id", "").startswith(f"{pid}-l")], text


def test_hanging_indent_and_column_width(font_family):
    style = merge_style({"font_family": font_family, "width_mm": 60})
    res = typeset(LONG, style, prefix="t", log=lambda m: None)
    wrapped = [p for p in res.layout.placed if p.nlines > 1]
    assert wrapped, "test text should wrap"
    for p in wrapped:
        lines, text = lines_of(res.content, p.pid)
        assert all(float(line.get("x")) == pytest.approx(p.x, abs=1e-4) for line in lines)
        marker = text.find(f"{{{SVG_NS}}}tspan")
        assert float(marker.get("x")) < p.x
    for p in res.layout.placed:
        for line in p.lines:
            width = sum(res.typesetter.text_width(r.text, r.bold, r.italic, res.typesetter.size_mm()) for r in line)
            assert p.x + width <= style["width_mm"] + 1e-6


def test_nested_marker_starts_at_parent_text_edge(font_family):
    res = typeset(LONG, merge_style({"font_family": font_family, "width_mm": 60}), prefix="t", log=lambda m: None)
    parent = next(p for p in res.layout.placed if p.marker == "2.")
    child = next(p for p in res.layout.placed if p.marker == "a)")
    assert child.marker_x == pytest.approx(parent.x)


def test_flowed_mode_stacks_from_measured_lines_and_adds_fallback(font_family):
    from lxml import etree

    def fake_export(tree):
        # pretend Inkscape wrapped every paragraph into 3 lines
        doc = etree.fromstring(etree.tostring(tree))
        for text in doc.iter(f"{{{SVG_NS}}}text"):
            if "inline-size" not in (text.get("style") or ""):
                continue
            words = "".join(text.itertext())
            for child in list(text):
                text.remove(child)
            text.text = None
            y = float(text.get("y"))
            for n in range(3):
                t = etree.SubElement(text, f"{{{SVG_NS}}}tspan", x=text.get("x"), y=str(y + 4 * n))
                t.text = words if n == 0 else "…"
        return etree.ElementTree(doc)

    style = merge_style({"font_family": font_family, "width_mm": 60})
    res = typeset("first paragraph\n\nsecond paragraph", style, mode="flowed", prefix="f",
                  export_plain=fake_export, log=lambda m: None)
    a, b = res.layout.placed
    lh = style["font_size_pt"] * 25.4 / 72 * style["line_height"]
    assert b.top == pytest.approx(a.top + 3 * lh + style["paragraph_gap_mm"])
    counts, _ = read_fallback(etree.ElementTree(res.content))
    assert counts == {"f-p1": 3, "f-p2": 3}


def test_unknown_font_family_warns_and_falls_back():
    messages = []
    typeset("x", merge_style({"font_family": "No Such Font Family 123"}), log=messages.append)
    assert any("No Such Font Family 123" in m for m in messages)


def test_missing_font_file_is_an_error():
    from omi_lib.mdlists.fonts import FontError
    with pytest.raises(FontError):
        typeset("x", merge_style({"fonts": {"regular": "/nonexistent.ttf"}}), log=lambda m: None)
