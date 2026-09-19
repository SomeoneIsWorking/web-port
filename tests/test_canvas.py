"""Execute the packaged canvas module, because the gesture policy only counts
in the artefact a consumer actually ships. The module is loaded from a rendered
release directory in Node against a minimal DOM, and every assertion names the
property or event it read back.
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/canvas_verify.mjs"


def test_packaged_canvas_claims_the_browser_gestures(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("first release")
    destination = tmp_path / "release"
    package_application(destination, {"index.html": index})
    assert (destination / "canvas.mjs").is_file(), "every release carries the gesture owner"
    node = shutil.which("node")
    assert node is not None, "the browser canvas verifier requires node"
    result = subprocess.run(
        [node, str(HARNESS), str(destination)], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(f"{result.stdout}{result.stderr}")
    assert "canvas-verify: OK" in result.stdout


def test_the_verifier_fails_a_module_that_claims_nothing(tmp_path):
    """A harness that passes whatever it is given proves nothing about the real
    module, so feed it one that takes no gesture away and require a failure."""
    index = tmp_path / "index.html"
    index.write_text("first release")
    destination = tmp_path / "release"
    package_application(destination, {"index.html": index})
    (destination / "canvas.mjs").write_text(
        "export function safeAreaInsets() { return {top: 0, right: 0, bottom: 0, left: 0}; }\n"
        "export function claimCanvasGestures() { return () => {}; }\n"
    )
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(
        [node, str(HARNESS), str(destination)], capture_output=True, text=True
    )
    assert result.returncode != 0, "an inert module must not pass the gesture verifier"
