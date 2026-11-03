"""scripts/check_release_tag.py: a release tag must match the version it publishes."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_release_tag", ROOT / "scripts" / "check_release_tag.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

PYPROJECT = '[project]\nname = "voxa-dub"\nversion = "1.11.0"\n'
CHANGELOG = "## [Unreleased]\n\n## [1.11.0] - 2026-11-03\n\n### Added\n"


def test_a_tag_matching_the_version_and_changelog_passes():
    assert check.problems("v1.11.0", PYPROJECT, CHANGELOG) == []


def test_a_tag_on_the_commit_before_the_release_commit_is_caught():
    # 1.11.0's first tag: pushed before the release commit was pulled.
    found = check.problems("v1.11.0", PYPROJECT.replace("1.11.0", "1.10.0"), CHANGELOG)
    assert len(found) == 1
    assert "says 1.10.0" in found[0] and "git tag -f v1.11.0" in found[0]


def test_a_tag_without_the_v_prefix_is_caught():
    assert check.problems("1.11.0", PYPROJECT, CHANGELOG)


def test_a_version_missing_from_the_changelog_is_caught():
    found = check.problems("v1.11.0", PYPROJECT, "## [Unreleased]\n\n## [1.10.0] - x\n")
    assert found and "## [1.11.0]" in found[0]


def test_only_the_first_version_line_counts():
    # A dependency's `version = ...` further down must not be read as the project's.
    text = PYPROJECT + '\n[tool.other]\nversion = "9.9.9"\n'
    assert check.problems("v1.11.0", text, CHANGELOG) == []


def test_the_repository_itself_is_consistent():
    # Whatever main says, its version has a changelog section, so tagging it would pass.
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M).group(1)
    assert check.problems(f"v{version}", pyproject,
                          (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")) == []
