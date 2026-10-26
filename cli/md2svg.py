#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""md2svg — typeset a Markdown subset as Inkscape-ready SVG text with hanging indents.

Modes
  metrics  line breaks computed from the font files (fontTools); every line is a
           positioned <tspan>. Deterministic, portable, not reflowed by Inkscape.
  flowed   every paragraph is SVG2 auto-wrapping text (inline-size) plus SVG 1.1
           fallback lines; Inkscape decides the line breaks and keeps re-wrapping
           when edited.

Output
  --out FILE.svg                    standalone SVG, 1 user unit = 1 mm
  --insert-into PAGE.svg --at X,Y   group inserted (or replaced by --id) into an existing
                                    SVG; X,Y in mm from the page origin

Same engine as the Oh My Inkscape "Markdown Lists" Inkscape extension. Requires python3 >= 3.10,
lxml, fontconfig (fc-list); fontTools is used from the system or the vendored copy.
Inkscape >= 1.2 for flowed mode, --check and --png.
"""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "oh-my-inkscape"))

import omi_lib  # noqa: E402,F401  (sets up the vendored fontTools)
from lxml import etree  # noqa: E402

from omi_lib.mdlists.engine import flowed_probe, read_fallback, typeset  # noqa: E402
from omi_lib.mdlists.fonts import FontError  # noqa: E402
from omi_lib.mdlists.style import merge_style  # noqa: E402
from omi_lib.mdlists.svgbuild import fmt, standalone_svg  # noqa: E402

PT_TO_MM = 25.4 / 72
PX_TO_MM = 25.4 / 96


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def write_tree(tree, path):
    tree.write(path, xml_declaration=True, encoding="UTF-8", pretty_print=False)


def inkscape_bin():
    exe = os.environ.get("INKSCAPE") or shutil.which("inkscape")
    if not exe:
        sys.exit("error: Inkscape not found (set INKSCAPE=/path/to/inkscape)")
    return exe


def run_inkscape(args):
    res = subprocess.run([inkscape_bin()] + args, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"error: inkscape {' '.join(args)} failed:\n{res.stderr[-2000:]}")
    return res.stdout


def work_dir(near):
    """Scratch dir Inkscape can read: snap/flatpak builds can't see the host /tmp nor
    hidden top-level dirs of $HOME, so stay next to the output unless it lives there."""
    d = os.path.dirname(os.path.abspath(near))
    home = os.path.expanduser("~")
    rel = os.path.relpath(d, home)
    if rel.startswith("..") or (rel != "." and rel.split(os.sep)[0].startswith(".")):
        return tempfile.mkdtemp(prefix="md2svg-tmp-", dir=home)
    return tempfile.mkdtemp(prefix=".md2svg-", dir=d)


def export_plain(svg_tree, near):
    """Inkscape's plain-SVG export of `svg_tree` (its own line breaks for auto-wrapping text)."""
    tmp = work_dir(near)
    try:
        src = os.path.join(tmp, "measure.svg")
        dst = os.path.join(tmp, "measured.svg")
        write_tree(svg_tree, src)
        run_inkscape([src, "--export-type=svg", "--export-plain-svg", f"--export-filename={dst}"])
        return etree.parse(dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def query_all(path):
    tmp = work_dir(path)
    try:
        copy_ = os.path.join(tmp, "query.svg")
        shutil.copy2(path, copy_)
        out = run_inkscape(["--query-all", copy_])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    boxes = {}
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) == 5:
            try:
                boxes[parts[0]] = tuple(float(v) * PX_TO_MM for v in parts[1:])
            except ValueError:
                pass
    return boxes


def parse_length_mm(value):
    m = re.match(r"^\s*([0-9.eE+-]+)\s*(mm|cm|in|pt|pc|px|)\s*$", value or "")
    if not m:
        return None
    v = float(m.group(1))
    return v * {"mm": 1, "cm": 10, "in": 25.4, "pt": PT_TO_MM, "pc": 12 * PT_TO_MM, "px": PX_TO_MM, "": PX_TO_MM}[m.group(2)]


def user_units_per_mm(svg):
    width_mm = parse_length_mm(svg.get("width"))
    vb = svg.get("viewBox")
    if vb and width_mm:
        return float(re.split(r"[ ,]+", vb.strip())[2]) / width_mm
    if vb and not width_mm:
        return 1 / PX_TO_MM  # no width: viewBox units are CSS px
    return 1 / PX_TO_MM


def insert_into(target, content, group_id, at, parent_id, out_path):
    tree = etree.parse(target, etree.XMLParser(remove_blank_text=False))
    svg = tree.getroot()
    scale = user_units_per_mm(svg)
    content.set("id", group_id)
    content.set("transform", f"translate({fmt(at[0] * scale)},{fmt(at[1] * scale)}) scale({fmt(scale)})")
    existing = svg.xpath("//*[@id=$i]", i=group_id)
    if existing:
        old = existing[0]
        old.getparent().replace(old, content)
        print(f"replaced existing element #{group_id}")
    else:
        parent = svg
        if parent_id:
            found = svg.xpath("//*[@id=$i]", i=parent_id)
            if not found:
                sys.exit(f"error: no element with id '{parent_id}' in {target}")
            parent = found[0]
        if parent.get("transform") or any(a.get("transform") for a in parent.iterancestors()):
            warn(f"parent #{parent.get('id')} or an ancestor has a transform: --at is applied inside it, "
                 "not in page coordinates")
        parent.append(content)
    if os.path.abspath(out_path) == os.path.abspath(target):
        shutil.copy2(target, target + ".bak")
        print(f"backup written to {target}.bak")
    tree.write(out_path, xml_declaration=True, encoding="UTF-8")
    return scale


def check(out_path, layout, offset, mode, metrics_tree=None):
    boxes = query_all(out_path)
    tol = 0.1
    problems = 0
    for p in layout.placed:
        b = boxes.get(p.pid)
        if not b:
            continue
        right = b[0] + b[2]
        limit = offset[0] + p.x + p.width
        if right > limit + tol:
            problems += 1
            print(f"OVERFLOW {p.pid}: right edge {right - offset[0]:.2f} mm > column edge {p.x + p.width:.2f} mm "
                  f"({''.join(r.text for r in p.para.runs)[:50]!r})")
    if mode == "metrics" and metrics_tree is not None:
        counts, _ = read_fallback(export_plain(metrics_tree, out_path))
        for p in layout.placed:
            got = counts.get(p.pid)
            if got and got != p.nlines:
                print(f"NOTE {p.pid}: Inkscape would wrap this paragraph in {got} lines, this layout uses "
                      f"{p.nlines} (only matters if you later convert it to flowed text)")
    print(f"check: {len(layout.placed)} paragraphs, {problems} overflow(s)")
    return problems


def parse_set(values):
    out = {}
    for item in values or []:
        key, _, raw = item.partition("=")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            val = raw
        node = out
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = val
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Markdown file ('-' for stdin)")
    ap.add_argument("--style", help="style JSON file (see docs/mdlists.md)")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE",
                    help="override a style key, e.g. --set width_mm=80 --set headings.1.size_pt=11")
    ap.add_argument("--mode", choices=["metrics", "flowed"], default="metrics")
    ap.add_argument("--out", help="output SVG (standalone) or output path for --insert-into (default: overwrite)")
    ap.add_argument("--insert-into", metavar="PAGE.svg", help="insert into this existing SVG")
    ap.add_argument("--at", default="0,0", help="X,Y in mm of the block's top-left on the page (insert mode)")
    ap.add_argument("--parent", help="id of the layer/group to insert into (default: document root)")
    ap.add_argument("--id", default="mdtext", help="id of the generated group and prefix of inner ids")
    ap.add_argument("--check", action="store_true", help="verify with Inkscape that no line overflows its column")
    ap.add_argument("--png", help="also render a PNG preview of the block (200 dpi)")
    args = ap.parse_args()

    layers = []
    if args.style:
        with open(args.style, encoding="utf-8") as fh:
            layers.append(json.load(fh))
    layers.append(parse_set(args.set))
    try:
        style = merge_style(*layers)
    except ValueError as e:
        sys.exit(f"error: {e}")
    if not args.out and not args.insert_into:
        sys.exit("error: give --out FILE.svg and/or --insert-into PAGE.svg")

    md = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    out_path = args.out or args.insert_into
    try:
        res = typeset(md, style, args.mode, args.id, export_plain=lambda t: export_plain(t, out_path), log=warn)
    except FontError as e:
        sys.exit(f"error: {e}")
    content, width, height, layout = res.content, res.width, res.height, res.layout
    metrics_probe = flowed_probe(res, args.id) if args.mode == "metrics" and args.check else None

    if args.insert_into:
        at = tuple(float(v) for v in args.at.split(","))
        insert_into(args.insert_into, content, args.id, at, args.parent, out_path)
        offset = at
    else:
        content.set("id", args.id)
        write_tree(standalone_svg(content, width, height), out_path)
        offset = (0.0, 0.0)
    print(f"wrote {out_path} ({args.mode}, {fmt(width)} x {fmt(height)} mm, {len(layout.placed)} paragraphs)")

    status = 0
    if args.check:
        status = 1 if check(out_path, layout, offset, args.mode, metrics_probe) else 0
    if args.png:
        tmp = work_dir(out_path)
        try:
            src, png = os.path.join(tmp, "preview.svg"), os.path.join(tmp, "preview.png")
            shutil.copy2(out_path, src)
            run_inkscape([src, "--export-type=png", "--export-dpi=200",
                          "--export-background=white", "--export-background-opacity=1",
                          f"--export-id={args.id}", f"--export-filename={png}"])
            shutil.move(png, args.png)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print(f"preview {args.png}")
    sys.exit(status)


if __name__ == "__main__":
    main()
