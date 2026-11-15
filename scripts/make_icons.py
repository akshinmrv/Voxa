"""Draw Voxa's icons from its mark: five rounded bars, sky blue on a near-black rounded square.

The same mark as web/app/icon.tsx (the site's and the console's PNG icon). Writes:

  voxa_ui/icons/voxa.ico   Voxa Studio's window, taskbar and shortcuts (16 to 256 px)
  voxa_ui/icons/voxa.png   512 px, for Linux launchers and wherever a PNG is wanted
  web/app/favicon.ico      the site's and the console's favicon (16 to 256 px)

Up to 32 px the bars are laid on whole pixels, so they stay apart instead of blurring into one
another; larger sizes are drawn four times over and scaled down. Needs Pillow. Run from the
repository root:  python scripts/make_icons.py
"""
import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

BARS = (0.4, 0.75, 1.0, 0.55, 0.35)       # web/app/icon.tsx
INK = "#38bdf8"
GROUND = "#0a0a0b"
ROOT = Path(__file__).resolve().parent.parent


def _ground(draw: ImageDraw.ImageDraw, size: int) -> None:
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=round(size * 0.22), fill=GROUND)


def smooth(size: int) -> Image.Image:
    """Drawn at four times the size, then scaled down."""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _ground(draw, big)
    width, gap = big * 0.11, big * 0.075
    x = (big - (len(BARS) * width + (len(BARS) - 1) * gap)) / 2
    for height in BARS:
        h = height * 0.6 * big
        draw.rounded_rectangle([x, (big - h) / 2, x + width, (big + h) / 2],
                               radius=width / 2, fill=INK)
        x += width + gap
    return img.resize((size, size), Image.LANCZOS)


def crisp(size: int) -> Image.Image:
    """On whole pixels: bars of whole widths and gaps, centred, with heights of the same parity
    as the icon so each sits exactly in the middle."""
    width = max(2, size // 8)
    gap = max(1, size // 16)
    total = len(BARS) * width + (len(BARS) - 1) * gap
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _ground(draw, size)
    x = (size - total) // 2
    for height in BARS:
        h = max(2, round(height * 0.62 * size))
        if (size - h) % 2:
            h += 1
        top = (size - h) // 2
        draw.rounded_rectangle([x, top, x + width - 1, top + h - 1],
                               radius=width / 2 if width > 2 else 0, fill=INK)
        x += width + gap
    return img


def icon(size: int) -> Image.Image:
    return crisp(size) if size <= 32 else smooth(size)


def _dib(img: Image.Image) -> bytes:
    """A 32-bit bitmap entry: header, colour rows bottom-up, then an empty AND mask (the alpha
    channel does the transparency)."""
    width, height = img.size
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = img.tobytes("raw", "BGRA")
    rows = [pixels[y * width * 4:(y + 1) * width * 4] for y in range(height)]
    mask = bytes(((width + 31) // 32) * 4 * height)
    return header + b"".join(reversed(rows)) + mask


def write_ico(path: Path, sizes) -> None:
    """An .ico with every size its own drawing, not one image scaled. 256 px is a PNG, as
    usual; the smaller ones are bitmaps, since .NET Framework's System.Drawing.Icon, which sets
    the window's icon through pywebview, misreads smaller PNG entries."""
    images = []
    for size in sizes:
        if size >= 256:
            buf = io.BytesIO()
            icon(size).save(buf, format="PNG", optimize=True)
            images.append((size, buf.getvalue()))
        else:
            images.append((size, _dib(icon(size))))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        side = 0 if size >= 256 else size                   # 0 stands for 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + blobs)


def main() -> None:
    write_ico(ROOT / "voxa_ui" / "icons" / "voxa.ico", (16, 20, 24, 32, 40, 48, 64, 256))
    icon(512).save(ROOT / "voxa_ui" / "icons" / "voxa.png", optimize=True)
    write_ico(ROOT / "web" / "app" / "favicon.ico", (16, 32, 48, 256))
    for path in ("voxa_ui/icons/voxa.ico", "voxa_ui/icons/voxa.png", "web/app/favicon.ico"):
        print(f"{path}: {(ROOT / path).stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
