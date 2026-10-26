# SPDX-License-Identifier: GPL-3.0-or-later
"""Line breaking and vertical layout of paragraphs, list items and nested lists."""
import re
from dataclasses import dataclass

from ..i18n import _
from .markdown import Para, Run

PT_TO_MM = 25.4 / 72


class Typesetter:
    def __init__(self, style, fonts, log):
        self.s = style
        self.fonts = fonts
        self.log = log

    def size_mm(self, heading=0):
        if heading:
            return self.heading_style(heading)["size_pt"] * PT_TO_MM
        return self.s["font_size_pt"] * PT_TO_MM

    def heading_style(self, level):
        hs = self.s["headings"]
        return hs.get(str(level)) or hs[max(hs, key=int)]

    def run_style(self, run, heading):
        if heading:
            h = self.heading_style(heading)
            return run.bold or h.get("bold", True), run.italic or h.get("italic", False)
        return run.bold, run.italic

    def text_width(self, text, bold, italic, size, measure_only=False):
        return self.fonts.face(bold, italic).width(text, size, measure_only) * self.s["safety"]

    def wrap(self, para, width):
        """Greedy line breaking at spaces; returns lines as lists of Run."""
        size = self.size_mm(para.heading)
        tokens = []  # ('word', [Run]) | ('space', Run) | ('break',)
        word = []
        for run in para.runs:
            b, i = self.run_style(run, para.heading)
            for piece in re.split(r"( |\n)", run.text):
                if piece == " ":
                    if word:
                        tokens.append(("word", word))
                        word = []
                    tokens.append(("space", Run(" ", b, i)))
                elif piece == "\n":
                    if word:
                        tokens.append(("word", word))
                        word = []
                    tokens.append(("break",))
                elif piece:
                    word.append(Run(piece, b, i))
        if word:
            tokens.append(("word", word))

        def w(runs):
            return sum(self.text_width(r.text, r.bold, r.italic, size) for r in runs)

        lines, line, line_w, pending_space = [], [], 0.0, None
        for tok in tokens:
            if tok[0] == "break":
                lines.append(line)
                line, line_w, pending_space = [], 0.0, None
            elif tok[0] == "space":
                if line:
                    pending_space = tok[1]
            else:
                ww = w(tok[1])
                sw = w([pending_space]) if pending_space and line else 0.0
                if line and line_w + sw + ww > width:
                    lines.append(line)
                    line, line_w = list(tok[1]), ww
                else:
                    if sw:
                        line.append(pending_space)
                    line.extend(tok[1])
                    line_w += sw + ww
                pending_space = None
                if line_w > width and len(line) == len(tok[1]):
                    self.log(_("'{word}' is wider than its column ({w:.2f} > {col:.2f} mm).").format(
                        word="".join(r.text for r in tok[1]), w=ww, col=width))
        lines.append(line)
        return [merge_runs(l) for l in lines]


def merge_runs(runs):
    out = []
    for r in runs:
        if out and out[-1].bold == r.bold and out[-1].italic == r.italic:
            out[-1] = Run(out[-1].text + r.text, r.bold, r.italic)
        else:
            out.append(Run(r.text, r.bold, r.italic))
    return out


@dataclass
class Placed:
    pid: str
    para: Para
    x: float
    width: float
    top: float
    baseline: float
    lines: list  # metrics mode: list of [Run]; flowed: None
    nlines: int
    marker: str = ""
    marker_x: float = 0.0
    marker_bold: bool = False
    group: str = ""


class Layout:
    def __init__(self, ts, line_counts=None, mode="metrics", prefix="mdtext"):
        self.ts = ts
        self.s = ts.s
        self.line_counts = line_counts or {}
        self.mode = mode
        self.prefix = prefix
        self.placed = []
        self.groups = []  # (group_id, parent_group_id)
        self.y = 0.0
        self.first = True
        self.prev_heading = 0
        self.counter = 0

    def next_id(self, kind):
        self.counter += 1
        return f"{self.prefix}-{kind}{self.counter}"

    def gap(self, amount):
        if not self.first:
            self.y += amount
        self.first = False

    def line_height(self, heading=0):
        return self.ts.size_mm(heading) * self.s["line_height"]

    def place_para(self, para, x, width, group, marker="", marker_x=0.0, marker_bold=False):
        pid = self.next_id("p")
        lh = self.line_height(para.heading)
        face = self.ts.fonts.face(False, False)
        size = self.ts.size_mm(para.heading)
        baseline = self.y + (lh - (face.ascent + face.descent) * size) / 2 + face.ascent * size
        lines = self.ts.wrap(para, width) if self.mode == "metrics" else None
        if self.mode == "metrics":
            n = len(lines)
        else:
            n = self.line_counts.get(pid) or len(self.ts.wrap(para, width))
        self.placed.append(Placed(pid, para, x, width, self.y, baseline, lines, n,
                                  marker, marker_x, marker_bold, group))
        self.y += n * lh

    def marker_width(self, marker, size):
        mb = self.s["marker_bold"]
        w = self.ts.text_width(marker, mb, False, size)
        gap = self.s["marker_gap"]
        if isinstance(gap, (int, float)):
            return w + gap
        return w + self.ts.text_width(gap, mb, False, size, measure_only=True)

    def place_blocks(self, blocks, x, width, depth, group, inner_gap):
        for b in blocks:
            if isinstance(b, Para):
                if b.heading:
                    self.gap(self.ts.heading_style(b.heading)["gap_before_mm"])
                elif self.prev_heading:
                    self.gap(self.ts.heading_style(self.prev_heading)["gap_after_mm"])
                else:
                    self.gap(inner_gap)
                self.place_para(b, x, width, group)
                self.prev_heading = b.heading
            else:
                self.gap(self.ts.heading_style(self.prev_heading)["gap_after_mm"] if self.prev_heading else inner_gap)
                self.prev_heading = 0
                self.place_list(b, x, width, depth, group)

    def place_list(self, lst, x, width, depth, group):
        size = self.ts.size_mm()
        marker_x = x + (self.s["list_indent_mm"] if depth == 0 else self.s["nested_indent_mm"])
        bullets = self.s["bullets"]
        markers = [it.marker if it.ordered else bullets[depth % len(bullets)] for it in lst.items]
        hang = max(self.marker_width(m, size) for m in markers)
        list_gid = self.next_id("list")
        self.groups.append((list_gid, group))
        for n, (item, marker) in enumerate(zip(lst.items, markers)):
            if n:
                self.gap(self.s["item_gap_mm"])
            text_x = marker_x + (hang if self.s["hang"] == "list" else self.marker_width(marker, size))
            item_gid = self.next_id("item")
            self.groups.append((item_gid, list_gid))
            first_para = True
            for b in item.blocks:
                if isinstance(b, Para) and first_para:
                    self.place_para(b, text_x, x + width - text_x, item_gid, marker, marker_x,
                                    self.s["marker_bold"])
                    first_para = False
                    self.prev_heading = 0
                    continue
                if first_para:  # item starting directly with a nested list
                    self.place_para(Para([Run("")]), text_x, x + width - text_x, item_gid, marker, marker_x,
                                    self.s["marker_bold"])
                    self.y -= self.line_height()
                    first_para = False
                self.place_blocks([b], text_x, x + width - text_x, depth + 1, item_gid, self.s["item_gap_mm"])

    def run(self, blocks):
        self.place_blocks(blocks, 0.0, self.s["width_mm"], 0, None, self.s["paragraph_gap_mm"])
        return self.y
