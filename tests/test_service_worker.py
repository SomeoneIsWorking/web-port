"""Execute the rendered service worker, because a cache that can hold bytes the
release does not name is the defect this contract exists to prevent. The worker
is the shipped artefact's source, so this test loads it in Node with stubbed
caches/fetch and dispatches a real install event in both directions.
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/sw_verify.mjs"


def test_rendered_worker_verifies_release_bytes(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("first release")
    destination = tmp_path / "release"
    package_application(destination, {"index.html": index})
    node = shutil.which("node")
    assert node is not None, "the browser release verifier requires node"
    result = subprocess.run(
        [node, str(HARNESS), str(destination)], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(f"{result.stdout}{result.stderr}")
    assert "sw-verify: OK" in result.stdout
