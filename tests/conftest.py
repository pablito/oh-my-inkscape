# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "oh-my-inkscape"))

import omi_lib  # noqa: E402,F401


def _has_family(name):
    if not shutil.which("fc-list"):
        return False
    out = subprocess.run(["fc-list", f":family={name}", "file"], capture_output=True, text=True).stdout
    return any(line.strip().rstrip(":").lower().endswith((".ttf", ".otf")) for line in out.splitlines())


@pytest.fixture(scope="session")
def font_family():
    for name in ("Liberation Sans", "DejaVu Sans", "Nimbus Sans", "Noto Sans"):
        if _has_family(name):
            return name
    pytest.skip("no TrueType/OpenType sans font found through fontconfig")
