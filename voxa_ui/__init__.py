"""The operator console that `voxa serve` serves: a static build of web/, copied into
static/ by `npm run build:console` (web/scripts/build-console.mjs) before the wheel is
built. A source checkout has no static/ until that has run."""
from pathlib import Path
from typing import Optional

STATIC_DIR = Path(__file__).parent / "static"
# Voxa's icon (scripts/make_icons.py draws them): .ico for Windows, .png for everything else.
ICON_DIR = Path(__file__).parent / "icons"


def static_dir() -> Optional[Path]:
    """The built console, or None when it hasn't been built."""
    return STATIC_DIR if (STATIC_DIR / "en" / "app" / "index.html").is_file() else None


def icon_path(kind: str = "ico") -> Path:
    """Voxa's icon as an .ico (Windows' windows and shortcuts) or a 512 px .png."""
    return ICON_DIR / f"voxa.{kind}"
