"""What pyproject.toml has to keep, for reasons a dependency bot can't see."""
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")     # Python 3.11+; the other CI jobs cover 3.10

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
INTEL_MAC = "sys_platform == 'darwin' and platform_machine == 'x86_64'"


def _dependencies():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]


@pytest.mark.parametrize("bound", ["numpy<2", "numba<0.63"])
def test_intel_macs_keep_their_upper_bounds(bound):
    # PyTorch stops at 2.2.2 on an Intel Mac, built against NumPy 1, so NumPy 2 breaks
    # torch.from_numpy and every transcription; numba has no Intel Mac wheels after 0.62.
    # Dependabot offers to raise both, since it doesn't read the marker.
    assert f"{bound}; {INTEL_MAC}" in _dependencies()


def test_the_licence_files_are_named():
    # The default LICEN[CS]E* glob would also ship any LICENSE_*.md in a local checkout.
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE", "NOTICE.md"]
