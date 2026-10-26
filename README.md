# Oh My Inkscape

A growing collection of Inkscape extensions. They all live under **Extensions → Oh My Inkscape**
and share one installer, one Python library and one translation catalog.

*Leggi in italiano: [README.it.md](README.it.md).*

| Extension | What it does |
|---|---|
| **Markdown Lists** | Typesets Markdown (headings, paragraphs, bulleted, numbered and nested lists, bold, italic) inside a rectangle, with real hanging indents. The block remembers its text and settings and can be regenerated after you edit the text or resize the frame. |

Inkscape has no lists, tab stops or paragraph indents; Markdown Lists places every marker and every
line at computed coordinates instead. It can write fixed lines (computed from the font files, exact
and portable) or auto-wrapping text that Inkscape keeps re-wrapping while you edit, with fallback
lines so browsers show it correctly too. Details: [docs/mdlists.md](docs/mdlists.md).

## Requirements

- Inkscape 1.2 or later (developed with 1.4); Linux, including the Snap and Flatpak builds.
  macOS and Windows should work but are untested.
- fontconfig (`fc-list`, `fc-match`), which Inkscape already uses on Linux.
- Nothing else: fontTools is bundled, lxml comes with Inkscape.

## Install

```bash
git clone https://github.com/pablito/oh-my-inkscape.git
cd oh-my-inkscape
./install.sh          # copies src/oh-my-inkscape into Inkscape's extensions folder
```

Restart Inkscape. `./install.sh --link` symlinks instead of copying (for development),
`./install.sh --uninstall` removes it. The target is `$INKSCAPE_EXTENSIONS_DIR` if set,
`~/snap/inkscape/common/extensions` for the Snap build (its launcher moves the user extensions
folder there), `~/.var/app/org.inkscape.Inkscape/config/inkscape/extensions` for Flatpak, otherwise
`<inkscape --user-data-directory>/extensions`. To install by hand, copy the folder `src/oh-my-inkscape` into the
folder shown in *Edit → Preferences → System → User extensions*.

## Markdown Lists in 30 seconds

1. Draw a rectangle where the text should go.
2. With the rectangle selected, open *Extensions → Oh My Inkscape → Markdown Lists…*.
3. Paste Markdown in the *Text* tab (or choose a `.md` file), set the font in *Type*, press *Apply*.
4. To change the text later, edit the block's *Description* in *Object → Object Properties*
   (Ctrl+Shift+O), or resize the rectangle; select the block or the rectangle and run the extension
   again.

The command-line version, for scripts and batch work:

```bash
python3 cli/md2svg.py rules.md --set font_family='"Nimbus Sans"' --set width_mm=88 --out rules.svg --check
```

## Development

```bash
python3 -m pytest tests          # needs lxml, fontTools (or the bundled copy) and one TTF/OTF sans font
python3 tools/i18n.py --check    # extract strings, update po/*.po, compile locale/*.mo (GNU gettext)
```

Layout:

```
src/oh-my-inkscape/        installed as-is into Inkscape's extensions folder
  omi_<name>.inx/.py       one pair per extension (menu entry + entry point)
  omi_lib/                 shared library: i18n, mdlists engine, _vendor/fontTools
  locale/                  compiled translations (domain "oh-my-inkscape")
cli/                       command-line tools using omi_lib
po/                        translation sources (.pot, it.po)
docs/                      per-extension reference
tests/                     pytest
```

Adding an extension: create `omi_<name>.inx` (with `translationdomain="oh-my-inkscape"` and the
`Oh My Inkscape` submenu) and `omi_<name>.py`, put reusable code in `omi_lib/<name>/`, wrap
user-facing Python messages in `_()` from `omi_lib.i18n`, then run `tools/i18n.py` and translate the
new entries in `po/it.po`.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). Bundled fontTools 4.61.1
(`src/oh-my-inkscape/omi_lib/_vendor/fontTools`, unmodified) is MIT-licensed, see
`src/oh-my-inkscape/omi_lib/_vendor/licenses/`.
