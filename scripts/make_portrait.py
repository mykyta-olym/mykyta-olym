"""Turns a portrait photo into ASCII art. Run locally; the photo is never committed.

    python scripts/make_portrait.py photo.png art/portrait.txt

Needs Pillow and NumPy. Works like a pencil sketch: dark features become dense
glyphs and skin stays nearly empty, because raw brightness produces a uniform
block of characters with no face in it. The mask values fit the source photo.
"""

import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

RAMP = " .,:;!|lj%kH@M"
COLS, ROWS = 52, 28


def subject_mask(size):
    """Head, neck and shoulders, as fractions of the square photo."""
    s = size * 4
    mask = Image.new("L", (s, s), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0.235 * s, 0.115 * s, 0.785 * s, 0.84 * s), fill=255)
    draw.polygon(
        [(0.29 * s, 0.70 * s), (0.70 * s, 0.70 * s), (0.72 * s, 0.82 * s), (0.97 * s, 1.0 * s),
         (0.0 * s, 1.0 * s), (0.14 * s, 0.88 * s), (0.28 * s, 0.82 * s)],
        fill=255,
    )
    return mask.resize((size, size), Image.LANCZOS)


def sketch(image, dark=1.6, detail=8.0, floor=0.2):
    """Returns tone in 0..1, where 1 is the densest glyph."""
    size = image.width
    gray = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
    lum = np.asarray(gray, dtype=float) / 255
    wide = np.asarray(gray.filter(ImageFilter.GaussianBlur(size * 0.05)), dtype=float) / 255
    tight = np.asarray(gray.filter(ImageFilter.GaussianBlur(size * 0.006)), dtype=float) / 255
    local = np.clip(wide - tight, 0, 1)
    tone = dark * np.clip((0.42 - lum) / 0.42, 0, 1) ** 0.9 + detail * local
    return np.clip(tone - floor * 0.25, 0, 1)


def to_ascii(image, **options):
    tone = sketch(image, **options)
    alpha = np.asarray(subject_mask(image.width), dtype=float) / 255
    tone_image = Image.fromarray((tone * alpha * 255).astype("uint8"))
    small = np.asarray(tone_image.resize((COLS, ROWS), Image.BOX), dtype=float) / 255
    # Keep a faint outline of the skin so the head has a silhouette.
    edge = np.asarray(Image.fromarray((alpha * 255).astype("uint8")).resize((COLS, ROWS), Image.BOX), dtype=float) / 255
    small = np.where((edge > 0.5) & (small < 0.08), 0.09, small)
    indices = np.clip((small * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row).rstrip() for row in indices]


def main():
    source, target = sys.argv[1], sys.argv[2]
    lines = to_ascii(Image.open(source).convert("RGB"))
    with open(target, "w", encoding="ascii", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
