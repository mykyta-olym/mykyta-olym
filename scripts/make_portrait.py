"""Turns a portrait photo into ASCII art, one version per theme. Run locally.

    python scripts/make_portrait.py photo.jpg art/

Needs Pillow and NumPy. The photo is never committed.

Three things decide whether a face survives the conversion:
- Density: 120 x 66 characters. At 28 rows a face is an unreadable blob.
- The red channel: skin is even and bright there, so the eyes, brows and mouth
  stand out. In plain grayscale the lower half of a face turns dark.
- A hand-traced outline removes the background, which would otherwise compete
  with the face. The points fit this one photo.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

COLS, ROWS = 120, 66
CROP = (105, 62, 550, 562)  # The head fills the frame, so the characters go to the face.
RAMP = " .'`,:;~-+=ilt1jfxzvnuYXJCLQ0OZmwpdbkhao*#MW&8%B@"
OUTLINE = [
    (330, 80), (372, 84), (410, 100), (440, 125), (460, 155), (474, 190), (484, 225), (492, 262),
    (497, 305), (498, 335), (490, 365), (476, 398), (462, 415), (452, 445), (438, 478), (434, 500),
    (470, 508), (530, 548), (585, 595), (620, 640), (0, 640), (0, 596), (50, 566), (112, 548),
    (172, 510), (190, 478), (186, 445), (178, 412), (164, 380), (154, 340), (153, 305), (160, 280),
    (163, 240), (172, 200), (192, 160), (222, 125), (262, 98), (298, 84),
]


def subject_mask(size):
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).polygon([(x * scale, y * scale) for x, y in OUTLINE], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.6))
    return np.asarray(mask, dtype=float) / 255


def tone(image, mask):
    red = np.asarray(image, dtype=float)[..., 0] / 255
    low, high = np.percentile(red[mask > 0.5], [2, 98.5])
    stretched = np.clip((red - low) / (high - low), 0, 1)
    sharpened = Image.fromarray((stretched * 255).astype("uint8")).filter(
        ImageFilter.UnsharpMask(radius=5, percent=90, threshold=0)
    )
    return np.asarray(sharpened, dtype=float) / 255


def to_lines(values):
    frame = Image.fromarray((values * 255).astype("uint8")).crop(CROP)
    small = np.asarray(frame.resize((COLS, ROWS), Image.BOX), dtype=float) / 255
    indices = np.clip((small * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row).rstrip() for row in indices]


def main():
    source, target = sys.argv[1], Path(sys.argv[2])
    image = Image.open(source).convert("RGB")
    mask = subject_mask(image.width)
    bright = tone(image, mask)
    versions = {"dark": bright * mask, "light": (1 - bright) * mask}
    for name, values in versions.items():
        with open(target / f"portrait-{name}.txt", "w", encoding="ascii", newline="\n") as handle:
            handle.write("\n".join(to_lines(values)) + "\n")


if __name__ == "__main__":
    main()
