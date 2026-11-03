"""The operator console that `voxa serve` serves: a static build of web/, copied into
static/ by `npm run build:console` (web/scripts/build-console.mjs) before the wheel is
built. A source checkout has no static/ until that has run."""
from pathlib import Path
from typing import Optional

STATIC_DIR = Path(__file__).parent / "static"


def static_dir() -> Optional[Path]:
    """The built console, or None when it hasn't been built."""
    return STATIC_DIR if (STATIC_DIR / "en" / "app" / "index.html").is_file() else None
