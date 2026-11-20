"""Draw VoxaSetup.exe's two pictures from Voxa's mark (the five bars of make_icons.py).

  installer/windows/welcome.bmp  164 x 314, the welcome and finish pages' left panel: the
                                 mark and "Voxa Studio" on the app's near-black, a quiet
                                 waveform along its foot
  installer/windows/header.bmp   150 x 57, the other pages' header, on the white NSIS draws
                                 them on: the mark and "Voxa"

NSIS wants 24-bit bitmaps, so there is no transparency. Each is drawn four times over and
scaled down. The wordmark uses Segoe UI Bold (Windows), else DejaVu Sans Bold. Needs Pillow.
Run from the repository root:  python scripts/make_installer_art.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BARS = (0.4, 0.75, 1.0, 0.55, 0.35)       # the mark, as in make_icons.py and web/app/icon.tsx
INK = (56, 189, 248)                      # #38bdf8
GROUND = (13, 13, 15)                     # the console's surface-0, #0d0d0f
TEXT = (237, 237, 239)
MUTED = (161, 161, 170)
SCALE = 4
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "installer" / "windows"


def font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("C:/Windows/Fonts/segoeuib.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit("no bold font found: install DejaVu Sans")


def mark(draw: ImageDraw.ImageDraw, cx: float, cy: float, height: float) -> float:
    """The five bars, centred on (cx, cy), the tallest `height` high. Returns their width."""
    width, gap = height * 0.18, height * 0.125
    total = len(BARS) * width + (len(BARS) - 1) * gap
    x = cx - total / 2
    for bar in BARS:
        h = bar * height
        draw.rounded_rectangle([x, cy - h / 2, x + width, cy + h / 2], radius=width / 2,
                               fill=INK)
        x += width + gap
    return total


def welcome() -> Image.Image:
    w, h = 164 * SCALE, 314 * SCALE
    img = Image.new("RGB", (w, h), GROUND)
    draw = ImageDraw.Draw(img, "RGBA")
    # A waveform along the foot, faint: speech going by.
    bars, foot = 40, h * 0.86
    step = w / bars
    for i in range(bars):
        amp = (0.25 + 0.75 * abs(math.sin(i * 0.55) * math.cos(i * 0.17))) * h * 0.06
        x = i * step + step * 0.2
        draw.rounded_rectangle([x, foot - amp, x + step * 0.55, foot + amp],
                               radius=step * 0.27, fill=INK + (60,))
    mark(draw, w / 2, h * 0.30, h * 0.15)
    title = font(round(h * 0.075))
    draw.text((w / 2, h * 0.46), "Voxa", font=title, fill=TEXT, anchor="mm")
    sub = font(round(h * 0.042))
    draw.text((w / 2, h * 0.525), "Studio", font=sub, fill=MUTED, anchor="mm")
    return img.resize((164, 314), Image.LANCZOS)


def header() -> Image.Image:
    w, h = 150 * SCALE, 57 * SCALE
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    used = mark(draw, w * 0.30, h / 2, h * 0.52)
    word = font(round(h * 0.36))
    draw.text((w * 0.30 + used / 2 + h * 0.14, h / 2), "Voxa", font=word, fill=GROUND,
              anchor="lm")
    return img.resize((150, 57), Image.LANCZOS)


def main() -> None:
    welcome().save(OUT / "welcome.bmp")
    header().save(OUT / "header.bmp")
    print("wrote", OUT / "welcome.bmp", "and", OUT / "header.bmp")


if __name__ == "__main__":
    main()
