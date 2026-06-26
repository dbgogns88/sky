#!/usr/bin/env python3
"""Generate PWA icons for Sky Order Converter."""

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("Install Pillow first: pip install pillow")

STATIC = Path(__file__).resolve().parent.parent / "static"
BG = "#818CF8"
FG = "#FFFFFF"


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    margin = size * 0.18
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=size * 0.12,
        fill="#6366F1",
    )

    bolt = [
        (size * 0.56, size * 0.22),
        (size * 0.38, size * 0.52),
        (size * 0.50, size * 0.52),
        (size * 0.42, size * 0.78),
        (size * 0.64, size * 0.44),
        (size * 0.52, size * 0.44),
    ]
    draw.polygon(bolt, fill=FG)
    return img


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        path = STATIC / f"icon-{size}.png"
        draw_icon(size).save(path, "PNG")
        print(f"Created {path}")


if __name__ == "__main__":
    main()
