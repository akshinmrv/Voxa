"""Fail unless a release tag matches the version it would publish. A tag pushed before the
release commit was pulled lands on the commit before it: the wheel then carries the previous
version, PyPI refuses it as a duplicate, and by then the GitHub release and the container
image are out under the new tag. The release workflow runs this before anything is published.

Usage:  python scripts/check_release_tag.py v1.11.0
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def problems(tag, pyproject, changelog):
    """What is wrong with publishing `tag` from a checkout whose pyproject.toml and
    CHANGELOG.md read as given; empty when nothing is. Pure."""
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    version = match.group(1) if match else None
    if not version:
        return ["pyproject.toml has no version"]
    if tag != f"v{version}":
        return [f"tag {tag} is on a commit whose pyproject.toml says {version}, so nothing "
                f"was published. Was it made before the release commit was pulled? Pull it "
                f"and move the tag there:\n"
                f"  git pull --ff-only && git tag -f {tag} && git push --force origin {tag}"]
    if not re.search(rf"^## \[{re.escape(version)}\]", changelog, re.MULTILINE):
        return [f"CHANGELOG.md has no '## [{version}]' section for the release notes to "
                f"point to"]
    return []


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__.strip().splitlines()[-1])
    found = problems(argv[0], (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
                     (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    if found:
        sys.exit("\n".join(found))
    print(f"{argv[0]} matches pyproject.toml and CHANGELOG.md")


if __name__ == "__main__":
    main(sys.argv[1:])
