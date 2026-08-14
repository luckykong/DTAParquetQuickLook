#!/usr/bin/env python3
"""Generate the app icon (AppIcon.icns) with Pillow and iconutil.

Design: a rounded-square indigo→blue gradient with a clean white data-table
grid, representing the data preview the app provides.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
TOP = (99, 102, 241)     # indigo-500  #6366F1
BOTTOM = (37, 99, 235)   # blue-600    #2563EB


def make_icon(size: int) -> Image.Image:
    # Vertical gradient background.
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        r = int(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        gd.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Rounded-square mask.
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(result)

    # Data table.
    m = int(size * 0.24)
    tl, tr = m, size - m
    tt = int(size * 0.28)
    tb = size - int(size * 0.28)
    lw = max(2, int(size * 0.024))
    white = (255, 255, 255, 255)
    header_tint = (255, 255, 255, 66)

    # Outer frame.
    draw.rounded_rectangle([tl, tt, tr, tb], radius=int(size * 0.04), outline=white, width=lw)

    # Header row (filled + separator).
    header_h = (tb - tt) // 4
    header_bottom = tt + header_h
    draw.rectangle([tl + lw // 2, tt + lw // 2, tr - lw // 2, header_bottom], fill=header_tint)
    draw.line([(tl, header_bottom), (tr, header_bottom)], fill=white, width=lw)

    # Column separators (3 columns), below the header.
    for i in range(1, 3):
        x = tl + (tr - tl) * i // 3
        draw.line([(x, header_bottom), (x, tb)], fill=white, width=lw)

    # Row separators (3 data rows), below the header.
    for i in range(1, 3):
        y = header_bottom + (tb - header_bottom) * i // 3
        draw.line([(tl, y), (tr, y)], fill=white, width=lw)

    return result


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    iconset = repo / "build" / "AppIcon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    base = make_icon(SIZE)
    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, px in sizes.items():
        img = base if px == SIZE else base.resize((px, px), Image.LANCZOS)
        img.save(iconset / name)

    # iconutil may fail when writing directly into the repo (sandboxed);
    # generate into a temp dir and copy the result into Resources/.
    tmp_icns = Path(tempfile.mkdtemp()) / "AppIcon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(tmp_icns)], check=True)
    icns = repo / "Resources" / "AppIcon.icns"
    shutil.copy(tmp_icns, icns)
    print(f"wrote {icns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
