#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations: extract strings, update po/*.po, compile the catalogs Inkscape loads.

    python3 tools/i18n.py          # extract → po/oh-my-inkscape.pot, msgmerge po/*.po, msgfmt → locale/
    python3 tools/i18n.py --check  # also fail if a .po has untranslated or fuzzy entries

Needs GNU gettext (xgettext, msgmerge, msgfmt). Strings come from every .inx in the extension
folder (names, labels, options, gui-text, menu tips) and from _("…") calls in its Python code.
"""
import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "src", "oh-my-inkscape")
PO = os.path.join(ROOT, "po")
DOMAIN = "oh-my-inkscape"
POT = os.path.join(PO, f"{DOMAIN}.pot")
NOT_TRANSLATED = {"Oh My Inkscape"}  # brand name (submenu)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def inx_strings():
    found = []
    for path in sorted(glob.glob(os.path.join(EXT, "*.inx"))):
        rel = os.path.relpath(path, ROOT)
        for el in ET.parse(path).iter():
            tag = el.tag.split("}")[-1]
            texts = []
            if tag in ("name", "label", "option", "item", "menu-tip") and el.text and el.text.strip():
                if not (tag == "label" and el.get("appearance") == "url"):
                    texts.append(el.text.strip())
            for attr in ("gui-text", "gui-description"):
                if el.get(attr):
                    texts.append(el.get(attr))
            for t in texts:
                if t not in NOT_TRANSLATED:
                    found.append((t, rel))
    return found


def run(*cmd):
    subprocess.run(cmd, check=True)


def main():
    os.makedirs(PO, exist_ok=True)
    py_files = sorted(f for f in glob.glob(os.path.join(EXT, "**", "*.py"), recursive=True) if "_vendor" not in f)
    py_pot = POT + ".py"
    run("xgettext", "--language=Python", "--keyword=_", "--from-code=UTF-8", "--no-wrap", "--sort-by-file",
        "--package-name=oh-my-inkscape", "-o", py_pot, *[os.path.relpath(f, ROOT) for f in py_files])
    with open(py_pot, encoding="utf-8") as fh:
        py_part = fh.read()
    os.remove(py_pot)
    seen = set()
    entries = []
    for text, ref in inx_strings():
        if text in seen:
            continue
        seen.add(text)
        entries.append(f'#: {ref}\nmsgid "{esc(text)}"\nmsgstr ""\n')
    py_body = py_part.split('\n\n', 1)[1] if '\n\n' in py_part else ""
    header = py_part.split('\n\n', 1)[0].replace("charset=CHARSET", "charset=UTF-8")
    with open(POT, "w", encoding="utf-8") as fh:
        fh.write(header + "\n\n" + "\n".join(entries) + "\n" + py_body)
    os.chdir(ROOT)

    problems = 0
    for po in sorted(glob.glob(os.path.join(PO, "*.po"))):
        lang = os.path.splitext(os.path.basename(po))[0]
        run("msgmerge", "--quiet", "--update", "--backup=none", "--no-wrap", po, POT)
        out_dir = os.path.join(EXT, "locale", lang, "LC_MESSAGES")
        os.makedirs(out_dir, exist_ok=True)
        stats = subprocess.run(["msgfmt", "--check", "--statistics", "-o", os.path.join(out_dir, f"{DOMAIN}.mo"), po],
                               capture_output=True, text=True, check=True).stderr.strip()
        print(f"{lang}: {stats}")
        if "untranslated" in stats or "fuzzy" in stats:
            problems += 1
    if "--check" in sys.argv and problems:
        sys.exit("some catalogs are incomplete")


if __name__ == "__main__":
    main()
