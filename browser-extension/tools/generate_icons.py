"""Generates the extension icons (16/48/128 px) from vector-ish primitives.

Run once from the repository root:

    ai-service/.venv/Scripts/python.exe browser-extension/tools/generate_icons.py

The icons are deliberately simple: a blue shield with a cyan edge and a white
exclamation mark on a transparent background, matching the dashboard palette
(#3b82f6 blue, #22d3ee cyan, white).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parents[1] / "icons"

BLUE = (59, 130, 246, 255)      # --accent
DEEP = (29, 78, 216, 255)       # --accent-soft (bottom of the shield)
CYAN = (34, 211, 238, 255)      # highlight edge
WHITE = (255, 255, 255, 255)


def shield_points(size: int) -> list[tuple[float, float]]:
    """Shield outline: rounded top corners, tapering to a point at the bottom."""
    w = size
    h = size
    left = 0.10 * w
    right = 0.90 * w
    top = 0.08 * h
    shoulder = 0.52 * h
    bottom = 0.95 * h
    mid = 0.50 * w
    return [
        (mid, top),
        (right, top + 0.10 * h),
        (right, shoulder),
        (mid, bottom),
        (left, shoulder),
        (left, top + 0.10 * h),
        (mid, top),
    ]


def draw_icon(size: int) -> Image.Image:
    # Render at 4x for antialiasing, then downscale.
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pts = shield_points(big)

    # Vertical gradient for the shield body: iterate horizontal bands.
    bands = 64
    top_y = min(p[1] for p in pts)
    bottom_y = max(p[1] for p in pts)
    for i in range(bands):
        y0 = top_y + (bottom_y - top_y) * i / bands
        y1 = top_y + (bottom_y - top_y) * (i + 1) / bands + 1
        t = i / (bands - 1)
        color = tuple(
            int(BLUE[c] + (DEEP[c] - BLUE[c]) * t) for c in range(3)
        ) + (255,)
        # Clip each band to the shield by drawing the polygon with a y-offset
        # rectangle via a mask: simpler to draw the full polygon per band using
        # a temporary image.
        band = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        band_draw = ImageDraw.Draw(band)
        band_draw.polygon(pts, fill=color)
        band_draw.rectangle([0, y0, big, y1], fill=None)
        # Mask the band to the current y slice:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rectangle([0, y0, big, y1], fill=255)
        sliced = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        sliced.paste(band, (0, 0), mask)
        img = Image.alpha_composite(img, sliced)

    draw = ImageDraw.Draw(img)

    # Cyan edge stroke for the glow accent.
    draw.line(pts, fill=CYAN, width=max(2, big // 32), joint="curve")

    # White exclamation mark.
    bar_w = max(4, big // 7)
    cx = big * 0.50
    draw.rounded_rectangle(
        [cx - bar_w / 2, big * 0.26, cx + bar_w / 2, big * 0.60],
        radius=bar_w / 2,
        fill=WHITE,
    )
    dot_r = bar_w * 0.62
    draw.ellipse(
        [cx - dot_r, big * 0.67 - dot_r, cx + dot_r, big * 0.67 + dot_r],
        fill=WHITE,
    )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        icon = draw_icon(size)
        path = OUT_DIR / f"icon{size}.png"
        icon.save(path)
        print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    main()
