#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Oh My Inkscape — Markdown Lists: Markdown with bulleted/numbered lists and hanging indents.

A block is a group tied to a frame rectangle. It stores its Markdown in <desc> (editable in
Object Properties → Description), its settings in omi:* attributes, and the frame's id, so
selecting the block or its frame and running the extension again regenerates it in place.
"""
import json
import math
import os
import shutil
import tempfile

import inkex
from inkex.command import inkscape
from inkex.elements import _parser
from lxml import etree

import omi_lib  # noqa: F401  (vendored fontTools)
from omi_lib.i18n import _
from omi_lib.mdlists.engine import typeset
from omi_lib.mdlists.fonts import FontError
from omi_lib.mdlists.style import deep_merge, merge_style

OMI_NS = "urn:oh-my-inkscape:1"
BLOCK = "markdown-lists"
inkex.NSS["omi"] = OMI_NS
etree.register_namespace("omi", OMI_NS)
GAPS = {"space": " ", "en": "\u2002", "em": "\u2003"}


def omi(name):
    return f"{{{OMI_NS}}}{name}"


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class MarkdownLists(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--text", default="")
        pars.add_argument("--md_file", default="")
        pars.add_argument("--mode", default="metrics")
        pars.add_argument("--margin_mm", type=float, default=2.0)
        pars.add_argument("--source", default="block")
        pars.add_argument("--use_stored", type=inkex.Boolean, default=True)
        pars.add_argument("--font_family", default="sans-serif")
        pars.add_argument("--font_size_pt", type=float, default=9.0)
        pars.add_argument("--line_height", type=float, default=1.2)
        pars.add_argument("--color", type=inkex.Color, default=inkex.Color("black"))
        pars.add_argument("--paragraph_gap_mm", type=float, default=1.5)
        pars.add_argument("--smart_punctuation", type=inkex.Boolean, default=True)
        pars.add_argument("--keep_together", type=inkex.Boolean, default=True)
        pars.add_argument("--style_file", default="")
        pars.add_argument("--bullets", default="• – ▪")
        pars.add_argument("--marker_gap", default="en")
        pars.add_argument("--marker_gap_mm", type=float, default=2.0)
        pars.add_argument("--hang", default="list")
        pars.add_argument("--list_indent_mm", type=float, default=0.0)
        pars.add_argument("--nested_indent_mm", type=float, default=0.0)
        pars.add_argument("--item_gap_mm", type=float, default=0.5)
        pars.add_argument("--marker_bold", type=inkex.Boolean, default=False)
        for level, (size, before, after) in {1: (12, 3, 1.5), 2: (10.5, 2.5, 1), 3: (9, 2, 0.8)}.items():
            pars.add_argument(f"--h{level}_size", type=float, default=size)
            pars.add_argument(f"--h{level}_before", type=float, default=before)
            pars.add_argument(f"--h{level}_after", type=float, default=after)

    # ------------------------------------------------------------ inputs

    def dialog_style(self):
        o = self.options
        style = {
            "font_family": o.font_family.strip() or "sans-serif",
            "font_size_pt": o.font_size_pt,
            "line_height": o.line_height,
            "color": str(o.color.to_rgb()),
            "paragraph_gap_mm": o.paragraph_gap_mm,
            "smart_punctuation": o.smart_punctuation,
            "bullets": o.bullets.split() or ["•"],
            "marker_gap": GAPS.get(o.marker_gap, o.marker_gap_mm),
            "hang": o.hang,
            "list_indent_mm": o.list_indent_mm,
            "nested_indent_mm": o.nested_indent_mm,
            "item_gap_mm": o.item_gap_mm,
            "marker_bold": o.marker_bold,
            "headings": {
                str(n): {"size_pt": getattr(o, f"h{n}_size"), "bold": True, "italic": False,
                         "gap_before_mm": getattr(o, f"h{n}_before"), "gap_after_mm": getattr(o, f"h{n}_after")}
                for n in (1, 2, 3)
            },
        }
        if not o.keep_together:
            style["nobreak"] = []
        if o.style_file:
            try:
                style = deep_merge(style, json.loads(read_text(o.style_file)))
            except (OSError, ValueError) as e:
                raise inkex.AbortExtension(_("Cannot read the style file {path}: {error}")
                                           .format(path=o.style_file, error=e))
        return style

    def dialog_markdown(self):
        """(markdown, linked file) from the dialog; Inkscape passes newlines as the two characters \\n."""
        text = self.options.text.replace("\\n", "\n").strip("\n")
        if text.strip():
            return text, ""
        path = self.options.md_file
        if path and os.path.isfile(path):
            return read_text(path), path
        return None, ""

    def find_target(self):
        block = rect = None
        for el in self.svg.selection.values():
            for e in [el, *el.iterancestors()]:
                if e.get(omi("block")) == BLOCK:
                    block = block or e
            if rect is None and isinstance(el, inkex.Rectangle) and block is None:
                rect = el
        if block is None and rect is not None and rect.get("id"):
            found = self.svg.xpath(f"//*[@omi:frame='{rect.get('id')}']", namespaces={"omi": OMI_NS})
            block = found[0] if found else None
        if block is not None and rect is None:
            frame_id = block.get(omi("frame"))
            rect = self.svg.getElementById(frame_id) if frame_id else None
        return block, rect

    # ------------------------------------------------------------ geometry

    @staticmethod
    def scale_of(transform):
        return math.sqrt(abs(transform.a * transform.d - transform.b * transform.c)) or 1.0

    def frame_box(self, rect, parent):
        """Bounding box of `rect` in `parent`'s coordinates."""
        to_parent = -parent.composed_transform() @ rect.getparent().composed_transform()
        return rect.bounding_box(to_parent)

    # ------------------------------------------------------------ main

    def effect(self):
        o = self.options
        block, rect = self.find_target()
        if block is None and rect is None:
            raise inkex.AbortExtension(_("Select a rectangle to use as the text frame, or a block made by "
                                         "Markdown Lists to regenerate it."))

        if block is None or o.source == "dialog":
            markdown, source_file = self.dialog_markdown()
            if markdown is None:
                raise inkex.AbortExtension(_("Write some Markdown in the Text tab or choose a Markdown file."))
        else:
            source_file = block.get(omi("source-file")) or ""
            if source_file and os.path.isfile(source_file):
                markdown = read_text(source_file)
            else:
                desc = block.find(inkex.addNS("desc", "svg"))
                markdown = desc.text if desc is not None and desc.text else None
                source_file = ""
                if markdown is None:
                    raise inkex.AbortExtension(_("This block has no stored Markdown: choose “this dialog” as the "
                                                 "text source."))

        stored = block is not None and o.use_stored and block.get(omi("style"))
        if stored:
            layer = json.loads(block.get(omi("style")))
            mode = block.get(omi("mode")) or "metrics"
            margin = float(block.get(omi("margin-mm")) or 0)
        else:
            layer = self.dialog_style()
            mode = o.mode
            margin = o.margin_mm

        parent = block.getparent() if block is not None else rect.getparent()
        units_per_mm = self.svg.unittouu("1mm") / self.scale_of(parent.composed_transform())
        if rect is not None:
            box = self.frame_box(rect, parent)
            x, y = box.left + margin * units_per_mm, box.top + margin * units_per_mm
            width_mm = box.width / units_per_mm - 2 * margin
            frame_height_mm = box.height / units_per_mm - 2 * margin
        else:  # frame deleted: keep the block where it was
            x, y = (float(v) for v in block.get(omi("origin")).split(","))
            width_mm = float(block.get(omi("width-mm")))
            frame_height_mm = None
        if width_mm <= 1:
            raise inkex.AbortExtension(_("The frame is too narrow for the margin ({width:.1f} mm left).")
                                       .format(width=width_mm))

        try:
            style = merge_style(layer, {"width_mm": width_mm})
        except ValueError as e:
            raise inkex.AbortExtension(str(e))
        gid = block.get("id") if block is not None else self.svg.get_unique_id("mdlists")
        try:
            res = typeset(markdown, style, mode, prefix=gid, export_plain=self.export_plain, log=self.msg)
        except FontError as e:
            raise inkex.AbortExtension(str(e))

        group = etree.fromstring(etree.tostring(res.content), parser=_parser.SVG_PARSER)
        group.set("id", gid)
        group.set("transform", f"translate({x:.4f},{y:.4f}) scale({units_per_mm:.6f})")
        group.set(inkex.addNS("label", "inkscape"), "Markdown: " + self.label_of(markdown))
        group.set(omi("block"), BLOCK)
        group.set(omi("version"), "1")
        group.set(omi("mode"), mode)
        group.set(omi("margin-mm"), f"{margin:g}")
        group.set(omi("style"), json.dumps(layer, ensure_ascii=False, separators=(",", ":")))
        group.set(omi("origin"), f"{x:.4f},{y:.4f}")
        group.set(omi("width-mm"), f"{width_mm:.4f}")
        if rect is not None and rect.get("id"):
            group.set(omi("frame"), rect.get("id"))
        if source_file:
            group.set(omi("source-file"), source_file)
        desc = etree.Element(inkex.addNS("desc", "svg"))
        desc.text = markdown
        group.insert(0, desc)

        if block is not None:
            block.getparent().replace(block, group)
        else:
            rect.addnext(group)
        if frame_height_mm is not None and res.height > frame_height_mm + 0.05:
            self.msg(_("The text is {extra:.1f} mm taller than its frame.").format(extra=res.height - frame_height_mm))

    @staticmethod
    def label_of(markdown):
        for line in markdown.splitlines():
            line = line.strip().lstrip("#-*+ ").strip()
            if line:
                return line[:40] + ("…" if len(line) > 40 else "")
        return "…"

    @staticmethod
    def export_plain(tree):
        tmp = tempfile.mkdtemp(prefix="omi-")
        try:
            src = os.path.join(tmp, "probe.svg")
            dst = os.path.join(tmp, "probe-plain.svg")
            tree.write(src, xml_declaration=True, encoding="UTF-8")
            inkscape(src, export_type="svg", export_plain_svg=True, export_filename=dst)
            return etree.parse(dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    MarkdownLists().run()
