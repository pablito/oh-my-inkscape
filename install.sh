#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Install Oh My Inkscape into Inkscape's user extensions folder.
#
#   ./install.sh             copy src/oh-my-inkscape → <extensions>/oh-my-inkscape
#   ./install.sh --link      symlink instead (edits in the repo apply after restarting Inkscape)
#   ./install.sh --uninstall remove it
#
# The folder is $INKSCAPE_EXTENSIONS_DIR if set; for the Snap build ~/snap/inkscape/common/extensions
# (its launcher overrides the user extensions folder); for Flatpak
# ~/.var/app/org.inkscape.Inkscape/config/inkscape/extensions; otherwise
# <inkscape --user-data-directory>/extensions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src/oh-my-inkscape"

base="${INKSCAPE_EXTENSIONS_DIR:-}"
inkscape_bin="$(command -v inkscape 2>/dev/null || true)"
if [[ -z "$base" && "$inkscape_bin" == /snap/* ]]; then
  # the Snap launcher sets INKSCAPE_EXTENSIONS_DIR to $SNAP_USER_COMMON/extensions
  base="$HOME/snap/inkscape/common/extensions"
elif [[ -z "$base" && -z "$inkscape_bin" ]] && command -v flatpak >/dev/null 2>&1 \
     && flatpak info org.inkscape.Inkscape >/dev/null 2>&1; then
  base="$HOME/.var/app/org.inkscape.Inkscape/config/inkscape/extensions"
fi
if [[ -z "$base" && -n "$inkscape_bin" ]]; then
  data="$(inkscape --user-data-directory 2>/dev/null | tail -n 1 || true)"
  [[ -n "$data" ]] && base="$data/extensions"
fi
if [[ -z "$base" ]]; then
  case "$(uname -s)" in
    Darwin) base="$HOME/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions" ;;
    *) base="${XDG_CONFIG_HOME:-$HOME/.config}/inkscape/extensions" ;;
  esac
fi
dest="$base/oh-my-inkscape"

case "${1:-}" in
  --uninstall)
    rm -rf "$dest"
    echo "Removed $dest"
    exit 0 ;;
  --link)
    mkdir -p "$base"
    rm -rf "$dest"
    ln -s "$SRC" "$dest"
    echo "Linked $dest -> $SRC" ;;
  "")
    mkdir -p "$base"
    rm -rf "$dest"
    cp -R "$SRC" "$dest"
    find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
    echo "Installed into $dest" ;;
  *)
    echo "usage: $0 [--link|--uninstall]" >&2
    exit 2 ;;
esac
echo "Restart Inkscape, then look under Extensions → Oh My Inkscape."
