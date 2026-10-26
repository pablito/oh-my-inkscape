# SPDX-License-Identifier: GPL-3.0-or-later
"""Markdown subset parser and typographic refinement (smart punctuation, no-break groups)."""
import re
from dataclasses import dataclass, field

NBSP = "\u00a0"


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Para:
    runs: list
    heading: int = 0


@dataclass
class Item:
    marker: str
    ordered: bool
    blocks: list = field(default_factory=list)


@dataclass
class ListBlock:
    items: list


LIST_RE = re.compile(r"^( *)([-*+•–]|\d+[a-z]?[.)]|[a-zA-Z]\d*[.)]|[ivxlcIVXLC]+[.)])( +|$)(.*)$")


HEADING_RE = re.compile(r"^ {0,3}(#{1,6}) +(.*?)(?: +#+ *)?$")


INLINE_PATTERNS = [
    (re.compile(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*"), True, True),
    (re.compile(r"(?<![\w])___(?=\S)(.+?)(?<=\S)___(?![\w])"), True, True),
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), True, False),
    (re.compile(r"(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])"), True, False),
    (re.compile(r"\*(?=[^\s*])(.+?)(?<=[^\s*])\*"), False, True),
    (re.compile(r"(?<![\w])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w])"), False, True),
]


ESCAPES = {"\\*": "\ue001", "\\_": "\ue002", "\\#": "\ue003", "\\\\": "\ue004", "\\`": "\ue005"}


UNESCAPE = {v: k[1] for k, v in ESCAPES.items()}


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def is_blank(line):
    return not line.strip()


def parse_inline(text, bold=False, italic=False):
    runs = []
    pos = 0
    while pos < len(text):
        best = None
        for regex, b, i in INLINE_PATTERNS:
            m = regex.search(text, pos)
            if m and (best is None or m.start() < best[0].start()):
                best = (m, b, i)
        if not best:
            break
        m, b, i = best
        if m.start() > pos:
            runs.append(Run(text[pos:m.start()], bold, italic))
        runs.extend(parse_inline(m.group(1), bold or b, italic or i))
        pos = m.end()
    if pos < len(text):
        runs.append(Run(text[pos:], bold, italic))
    return runs


def finish_runs(runs):
    out = []
    for r in runs:
        t = r.text.replace("`", "")
        for k, v in UNESCAPE.items():
            t = t.replace(k, v)
        if out and out[-1].bold == r.bold and out[-1].italic == r.italic:
            out[-1].text += t
        else:
            out.append(Run(t, r.bold, r.italic))
    return [r for r in out if r.text]


def make_para(lines, heading=0):
    parts = []
    for n, line in enumerate(lines):
        hard = line.endswith("  ") or line.rstrip().endswith("\\")
        s = line.strip()
        if s.endswith("\\") and not s.endswith("\\\\"):
            s = s[:-1].rstrip()
        parts.append(s)
        if n < len(lines) - 1:
            parts.append("\n" if hard else " ")
    text = "".join(parts)
    for k, v in ESCAPES.items():
        text = text.replace(k, v)
    return Para(finish_runs(parse_inline(text)), heading)


def parse_blocks(lines):
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_blank(line):
            i += 1
            continue
        h = HEADING_RE.match(line)
        if h:
            blocks.append(make_para([h.group(2)], heading=len(h.group(1))))
            i += 1
            continue
        if LIST_RE.match(line):
            lst, i = parse_list(lines, i, indent_of(line))
            blocks.append(lst)
            continue
        para = [line]
        i += 1
        while i < len(lines) and not is_blank(lines[i]) and not HEADING_RE.match(lines[i]) \
                and not LIST_RE.match(lines[i]):
            para.append(lines[i])
            i += 1
        blocks.append(make_para(para))
    return blocks


def parse_list(lines, i, base):
    items = []
    while i < len(lines):
        m = LIST_RE.match(lines[i])
        if not m or indent_of(lines[i]) != base:
            break
        marker = m.group(2)
        ordered = marker not in "-*+•–"
        if items and ordered != items[0].ordered:
            break
        content_col = len(m.group(1)) + len(marker) + max(1, len(m.group(3)))
        body = [m.group(4)]
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if is_blank(line):
                k = j
                while k < len(lines) and is_blank(lines[k]):
                    k += 1
                if k < len(lines) and indent_of(lines[k]) > base:
                    body.extend([""] * (k - j))
                    j = k
                    continue
                break
            lm = LIST_RE.match(line)
            if lm and indent_of(line) <= base:
                break
            if indent_of(line) <= base and (HEADING_RE.match(line) or is_blank(body[-1])):
                break
            body.append(line[min(indent_of(line), content_col):])
            j += 1
        items.append(Item(marker, ordered, parse_blocks(body)))
        i = j
        while i < len(lines) and is_blank(lines[i]):
            nxt = i
            while nxt < len(lines) and is_blank(lines[nxt]):
                nxt += 1
            if nxt < len(lines) and LIST_RE.match(lines[nxt]) and indent_of(lines[nxt]) == base:
                i = nxt
            else:
                break
    return ListBlock(items), i


def smarten(text, prev):
    text = text.replace("---", "\u2014").replace("--", "\u2013").replace("...", "\u2026")
    out = []
    for ch in text:
        before = out[-1] if out else prev
        if ch == "'":
            out.append("\u2019" if before and (before.isalnum() or before in ".,;:!?)]\u2019\u201d") else "\u2018")
        elif ch == '"':
            out.append("\u201c" if not before or before.isspace() or before in "([{\u2018\u201c\u2014\u2013" else "\u201d")
        else:
            out.append(ch)
    return "".join(out)


def refine_text(blocks, style):
    """Typographic pass: smart punctuation, then no-break spaces inside `nobreak` matches."""
    for b in blocks:
        if isinstance(b, ListBlock):
            for item in b.items:
                refine_text(item.blocks, style)
            continue
        if style.get("smart_punctuation"):
            prev = ""
            for r in b.runs:
                r.text = smarten(r.text, prev)
                prev = r.text[-1:] or prev
        patterns = style.get("nobreak") or []
        if patterns:
            full = "".join(r.text for r in b.runs)
            chars = list(full)
            for pat in patterns:
                for m in re.finditer(pat, full):
                    for i in range(m.start(), m.end()):
                        if chars[i] == " ":
                            chars[i] = NBSP
            full = "".join(chars)
            pos = 0
            for r in b.runs:
                r.text, pos = full[pos:pos + len(r.text)], pos + len(r.text)


def parse_markdown(text):
    text = text.replace("\t", "    ").replace("\r\n", "\n")
    return parse_blocks(text.split("\n"))
