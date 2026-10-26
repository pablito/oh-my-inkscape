# SPDX-License-Identifier: GPL-3.0-or-later
"""Font files (via fontconfig) and advance-width measuring (via fontTools)."""
import os
import subprocess

from fontTools.ttLib import TTFont

from ..i18n import _

STYLE_NAMES = {
    "regular": ["Regular", "Roman", "Book", "Normal", "Medium"],
    "bold": ["Bold"],
    "italic": ["Italic", "Oblique"],
    "bold_italic": ["Bold Italic", "Bold Oblique", "BoldItalic", "BoldOblique"],
}


SPACE_EM = {"\u00a0": None, "\u2002": 0.5, "\u2003": 1.0, "\u2009": 0.2, "\u202f": 0.2}


class Face:
    def __init__(self, path):
        self.path = path
        font = TTFont(path, fontNumber=0, lazy=True)
        try:
            self.cmap = font.getBestCmap()
            self.adv = dict(font["hmtx"].metrics)
            self.upm = font["head"].unitsPerEm
            self.ascent = font["hhea"].ascent / self.upm
            self.descent = -font["hhea"].descent / self.upm
        finally:
            font.close()
        self.missing = set()

    def width(self, text, size, measure_only=False):
        total = 0
        for ch in text:
            glyph = self.cmap.get(ord(ch))
            if glyph is None and ch in SPACE_EM:
                if SPACE_EM[ch] is None:
                    glyph = self.cmap.get(0x20)
                else:
                    total += SPACE_EM[ch] * self.upm
                    if not measure_only:
                        self.missing.add(ch)
                    continue
            if glyph is None:
                if not measure_only:
                    self.missing.add(ch)
                glyph = ".notdef"
            total += self.adv.get(glyph, (self.upm // 2, 0))[0]
        return total * size / self.upm


class FontError(Exception):
    pass


def _fc(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


GENERIC_FAMILIES = {"sans-serif", "sans", "serif", "monospace", "mono", "cursive", "fantasy", "system-ui"}


def resolve_family(family, log):
    """Family name fontconfig actually uses for `family` (resolves aliases such as sans-serif)."""
    if _fc(["fc-list", f":family={family}", "family"]).strip():
        return family
    resolved = _fc(["fc-match", family, "-f", "%{family[0]}"]).strip() or family
    if family.lower() not in GENERIC_FAMILIES:
        log(_("The font family '{family}' is not installed: Inkscape and this measurement fall back to "
              "'{fallback}'.").format(family=family, fallback=resolved))
    return resolved


def find_font_file(family, variant):
    out = _fc(["fc-list", f":family={family}", "-f", "%{file}|%{style}|%{fontformat}\n"])
    wanted = [w.lower() for w in STYLE_NAMES[variant]]
    best = None
    for line in out.splitlines():
        try:
            path, styles, fmt = line.split("|")
        except ValueError:
            continue
        if fmt not in ("TrueType", "CFF") or not path.lower().endswith((".ttf", ".otf", ".ttc", ".otc")):
            continue
        names = [s.strip().lower() for s in styles.split(",")]
        for rank, w in enumerate(wanted):
            if w in names and (best is None or rank < best[0]):
                best = (rank, path)
    return best[1] if best else None


class Fonts:
    def __init__(self, style, log):
        self.log = log
        family = resolve_family(style["font_family"], log)
        overrides = style.get("fonts") or {}
        self.faces = {}
        for variant in STYLE_NAMES:
            path = overrides.get(variant) or find_font_file(family, variant)
            if path:
                try:
                    self.faces[variant] = Face(os.path.expanduser(path))
                except (OSError, ValueError) as e:
                    raise FontError(_("Cannot read the font file {path}: {error}").format(path=path, error=e))
        if "regular" not in self.faces:
            raise FontError(_("No TrueType/OpenType file found for the font family '{family}'. "
                              "Check that it is installed (fc-list), or set fonts.regular in a style file.")
                            .format(family=style["font_family"]))
        for variant in ("bold", "italic", "bold_italic"):
            if variant not in self.faces:
                fallback = self.faces.get("bold") if variant == "bold_italic" and "bold" in self.faces else self.faces["regular"]
                log(_("No {variant} file for '{family}': measuring with {file}; Inkscape may synthesize the "
                      "style and widths can differ.").format(variant=variant, family=family,
                                                             file=os.path.basename(fallback.path)))
                self.faces[variant] = fallback

    def face(self, bold, italic):
        return self.faces[("bold_italic" if italic else "bold") if bold else ("italic" if italic else "regular")]

    def report_missing(self):
        for variant, face in self.faces.items():
            if face.missing:
                self.log(_("{file} lacks the characters {chars}: Inkscape will substitute another font and "
                           "widths will not match.").format(file=os.path.basename(face.path),
                                                            chars="".join(sorted(face.missing))))
