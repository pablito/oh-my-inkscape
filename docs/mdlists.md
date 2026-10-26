# Markdown Lists — reference

Typesets a Markdown subset as SVG text with real hanging indents: bullets and numbers sit at
`x_marker`, and the first line and every continuation line of an item start at the same text edge.
The same engine (`src/oh-my-inkscape/omi_lib/mdlists`) powers the Inkscape extension and the
`cli/md2svg.py` command.

## Markdown accepted

| Markdown | Result |
|---|---|
| `# Title`, `## Title`, `### Title` | Heading, size and gaps from `headings.<level>` (deeper levels reuse the last defined one) |
| blank-line separated lines | Paragraph; single newlines inside it become spaces |
| line ending in two spaces or `\` | Forced line break inside the paragraph |
| `- x`, `* x`, `+ x`, `• x`, `– x` | Bullet item; the drawn bullet comes from `bullets[depth]`, not from the source character |
| `1. x`, `1) x`, `2a) x`, `a) x`, `c1) x`, `iv. x` | Ordered item; the marker is drawn **exactly as written** (no renumbering) |
| child items indented under the parent's text (2–4 spaces) | Nested list; its marker starts at the parent's text edge (+ `nested_indent_mm`) |
| indented line after an item, or a lazy unindented line | Continuation of the item's paragraph |
| blank line + indented paragraph under an item | Second paragraph of the same item, aligned on the hanging indent |
| `**bold**`, `__bold__`, `*italic*`, `_italic_`, `***both***` | Bold / italic (the matching font files are used for measuring) |
| `` `code` `` | Backticks removed, text kept in the body font |
| `\*`, `\_`, `\#` | Literal characters |

A `*` that is not followed by a non-space character and closed later (e.g. `A*`, `D*`) stays literal.
A bullet list directly followed by an ordered list (or vice versa) is split into two lists, each with
its own hanging indent. Tables, links, images and block quotes are not interpreted.

## Style keys

JSON for `--style` (CLI) or the *Style file* field (extension). Lengths in mm, sizes in pt.

| Key | Default | Meaning |
|---|---|---|
| `font_family` | `sans-serif` | Family name as known to fontconfig/Inkscape (`fc-list : family`); aliases such as `sans-serif` are resolved with `fc-match` |
| `fonts` | `{}` | Optional explicit files: `regular`, `bold`, `italic`, `bold_italic` (`.ttf`/`.otf`) |
| `font_size_pt` | 9 | Body size |
| `line_height` | 1.2 | Multiple of the font size (also written as CSS `line-height`) |
| `width_mm` | 90 | Column width (the extension takes it from the frame) |
| `color` | `#000000` | Fill |
| `paragraph_gap_mm` | 1.5 | Between top-level blocks (paragraphs, lists) |
| `item_gap_mm` | 0.5 | Between list items, and between blocks inside one item |
| `list_indent_mm` | 0 | Marker x of a top-level list, from the block's left edge |
| `nested_indent_mm` | 0 | Extra offset of a nested list's marker from its parent's text edge |
| `marker_gap` | `"\u2002"` (en space) | Space between marker and text: a string measured in the font (`" "`, `"\u2002"`, `"\u2003"`; space characters missing from the font are measured as a fraction of the em) or a number in mm |
| `hang` | `list` | `list`: all items of a list share the text edge of the widest marker. `item`: each item's text starts at `x_marker + width(marker + gap)` |
| `bullets` | `["•","–","▪"]` | Bullet per nesting depth (cycled) |
| `marker_bold` | false | Draw markers in bold |
| `nobreak` | brackets, number + next word | Regexes whose matches never break across lines (their spaces become no-break spaces): the defaults keep `[9.131, 9.141]` and `−1 ZOC` / `4 ore` together. `[]` disables |
| `smart_punctuation` | true | `'` → ’/‘, `"` → “ ”, `--` → –, `---` → —, `...` → … |
| `safety` | 1.0 | Width multiplier for measuring (e.g. 1.04 = 4 % margin) |
| `headings` | see `style.py` | `{ "1": {size_pt, bold, italic, gap_before_mm, gap_after_mm}, ... }` |

## Line modes

| Mode | What is written | Trade-off |
|---|---|---|
| `metrics` (fixed lines) | Line breaks computed from the font files with fontTools; each line is a `<tspan x y>` | Exact and identical everywhere; editing a word in Inkscape does not re-wrap: regenerate instead |
| `flowed` (auto-wrapping) | Each paragraph is SVG2 text with `inline-size`, plus SVG 1.1 fallback lines (Inkscape's own line breaks, read from its plain-SVG export) | Inkscape re-wraps a paragraph as you edit it, but items below don't move if it grows: regenerate to restack. Browsers and other tools, which ignore `inline-size`, draw the fallback lines |

Kerning is ignored when measuring, which makes fixed lines slightly conservative (kerning is mostly
negative). Characters missing from the font are reported, because Inkscape would substitute another
font and the measured widths would be wrong.

## The extension

*Extensions → Oh My Inkscape → Markdown Lists…*

- **New block**: select a rectangle. The block takes the rectangle's position and width, minus the
  inner margin, and is inserted just above it in the same layer.
- **Regenerate**: select the block or its rectangle and run the extension again. By default the text
  comes from the block (its *Description* in *Object → Object Properties*, or the Markdown file it
  was made from) and the settings are the ones stored in the block. Choose *this dialog* as the text
  source, or untick *Reuse the block's own settings*, to replace them. Moving or resizing the
  rectangle and regenerating re-fits the block; if the rectangle was deleted, the block stays where
  it was.
- The block is a group with `omi:*` attributes (namespace `urn:oh-my-inkscape:1`) holding the
  settings, the frame id and the source file; the Markdown is in its `<desc>`.
- Live preview works; with auto-wrapping lines each preview runs Inkscape once in the background,
  so it takes a second or two.

## The command line

```bash
python3 cli/md2svg.py text.md --style style.json [--mode metrics|flowed] \
  (--out block.svg | --insert-into page.svg --at X,Y [--parent LAYER_ID] [--id NAME]) \
  [--set key=value ...] [--check] [--png preview.png]
```

- `--out`: standalone SVG, page = the block, 1 user unit = 1 mm.
- `--insert-into`: group `<id>` inserted at `X,Y` mm from the page's top-left, or replaced in place
  if it exists; the page is copied to `page.svg.bak` first when overwritten.
- `--set` overrides any style key (`--set width_mm=80 --set headings.2.size_pt=10`), values parsed
  as JSON when possible.
- `--check` asks Inkscape (`--query-all`) for every paragraph's bounding box and reports overflows;
  exit status 1 if any. `--png` renders a 200 dpi preview.
- Inkscape is needed for `flowed`, `--check` and `--png`. Snap/Flatpak builds cannot read the host
  `/tmp` or hidden top-level directories of `$HOME`; the CLI hands Inkscape copies in a directory it
  can read and removes them afterwards. Set `INKSCAPE=/path/to/inkscape` to choose the binary.

## SVG structure

Groups `<id>` → `<id>-listN` → `<id>-itemN` → paragraphs `<id>-pN`. With fixed lines each line is
`<id>-pN-lK` and the marker `<id>-pN-m` inside the same `<text>`; with auto-wrapping text the marker
is a separate `<text id="<id>-pN-m">`. Each line occupies `font_size × line_height`; the first
baseline sits at the half-leading position computed from the regular face's hhea ascent/descent.
