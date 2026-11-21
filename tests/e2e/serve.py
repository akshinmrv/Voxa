"""`voxa serve` for the console's end-to-end tests: the real server, its console and API, with
the dubbing pipeline it starts swapped for fake_voxa.py. Run as: python serve.py --port N"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import voxa  # noqa: E402
import voxa_server  # noqa: E402

# The server starts a dub as `python <voxa.__file__> …`; this is the only place it looks.
voxa.__file__ = str(Path(__file__).with_name("fake_voxa.py"))

if __name__ == "__main__":
    sys.exit(voxa_server.run_from_cli(sys.argv[1:]))
