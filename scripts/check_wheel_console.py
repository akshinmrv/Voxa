"""Fail unless the wheel ships the operator console. `voxa serve` serves it from
voxa_ui/static; a wheel built without running `npm run build:console` first would leave
everyone who installs it with no UI. CI and the release both run this.

Usage:  python scripts/check_wheel_console.py dist/*.whl
"""
import sys
import zipfile

REQUIRED = (
    "voxa_ui/__init__.py",
    "voxa_ui/static/404.html",
    "voxa_ui/static/en/app/index.html",
    "voxa_ui/static/az/app/jobs/view/index.html",
    # The engines package and the worker scripts it runs in the engines' environments.
    "voxa_engines/__init__.py",
    "voxa_engines/workers/chatterbox_worker.py",
)
# The landing page's media, which build-console.mjs leaves out of the package.
EXCLUDED = ("voxa_ui/static/demo/", "voxa_ui/static/tts-samples/")


def main(paths):
    wheels = [p for p in paths if p.endswith(".whl")]
    if len(wheels) != 1:
        sys.exit(f"expected one wheel, got {wheels}")
    names = set(zipfile.ZipFile(wheels[0]).namelist())
    missing = [n for n in REQUIRED if n not in names]
    unwanted = sorted(n for n in names if n.startswith(EXCLUDED))
    if missing or unwanted:
        sys.exit(f"{wheels[0]}: missing {missing}; should not ship {unwanted[:3]}")
    count = sum(n.startswith("voxa_ui/static/") for n in names)
    print(f"{wheels[0]}: console present ({count} files)")


if __name__ == "__main__":
    main(sys.argv[1:])
