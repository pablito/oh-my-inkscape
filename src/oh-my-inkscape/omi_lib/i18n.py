# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext for Oh My Inkscape messages; catalogs live in <extension dir>/locale/<lang>/LC_MESSAGES/oh-my-inkscape.mo.

The language follows LANGUAGE / LC_ALL / LC_MESSAGES / LANG; Inkscape sets LANGUAGE to its UI
language when it runs an extension.
"""
import gettext
import os

DOMAIN = "oh-my-inkscape"
LOCALEDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locale")

_translation = gettext.translation(DOMAIN, LOCALEDIR, fallback=True)


def _(message):
    return _translation.gettext(message)
