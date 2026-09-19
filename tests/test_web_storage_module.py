"""Execute the packaged storage module, because the readiness contract only
counts in the artefact a consumer actually ships. The module is loaded from a
rendered release directory in Node against a fake Storage Manager, and the
interesting browser is the one that never answers its own permission prompt.
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/storage_verify.mjs"

BLOCKING_MODULE = """\
export async function persistentStorage() {
  if (!globalThis.isSecureContext || !navigator.storage?.getDirectory) {
    throw new Error("This browser cannot provide private persistent storage.");
  }
  const persistent = await navigator.storage.persist();
  return {root: await navigator.storage.getDirectory(), persistent};
}
"""


def _release(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("first release")
    destination = tmp_path / "release"
    package_application(destination, {"index.html": index})
    assert (destination / "storage.mjs").is_file(), "every release carries the storage owner"
    return destination


def _run(destination):
    node = shutil.which("node")
    assert node is not None, "the browser storage verifier requires node"
    return subprocess.run(
        [node, str(HARNESS), str(destination)], capture_output=True, text=True
    )


def test_packaged_storage_answers_without_waiting_for_a_permission_prompt(tmp_path):
    result = _run(_release(tmp_path))
    if result.returncode != 0:
        raise AssertionError(f"{result.stdout}{result.stderr}")
    assert "storage-verify: OK" in result.stdout


def test_the_verifier_fails_a_module_that_awaits_the_prompt(tmp_path):
    """The superseded implementation hung a Firefox player at the first status
    line. A harness that passed it would certify exactly that regression."""
    destination = _release(tmp_path)
    (destination / "storage.mjs").write_text(BLOCKING_MODULE)
    result = _run(destination)
    assert result.returncode != 0, "a module that awaits persist() must be refused"
    assert "did not answer within" in result.stderr
