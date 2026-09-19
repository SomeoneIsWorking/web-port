"""Execute the packaged isolation module, because the failure it must report is
one the browser gives no other voice to: a service worker whose install was
refused never makes navigator.serviceWorker.ready resolve, and a page that only
awaited it says nothing to the player, forever.
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/isolation_verify.mjs"

WAITING_MODULE = """\
export async function prepareApplication(serviceWorker = "service-worker.js") {
  if (!globalThis.isSecureContext || !navigator.serviceWorker) {
    throw new Error("This application needs a secure browser with service workers.");
  }
  await navigator.serviceWorker.register(serviceWorker, {scope: "./"});
  await navigator.serviceWorker.ready;
  if (!globalThis.crossOriginIsolated) {
    const key = `web-port-isolation:${new URL(serviceWorker, location.href).pathname}`;
    if (sessionStorage.getItem(key)) {
      throw new Error("Browser isolation is unavailable. Enable service workers and reload this page.");
    }
    sessionStorage.setItem(key, "requested");
    location.reload();
    return false;
  }
  sessionStorage.removeItem(`web-port-isolation:${new URL(serviceWorker, location.href).pathname}`);
  return true;
}
"""


def _release(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("first release")
    destination = tmp_path / "release"
    package_application(destination, {"index.html": index})
    assert (destination / "isolation.mjs").is_file(), "every release carries the isolation owner"
    return destination


def _run(destination):
    node = shutil.which("node")
    assert node is not None, "the browser isolation verifier requires node"
    return subprocess.run(
        [node, str(HARNESS), str(destination)], capture_output=True, text=True
    )


def test_packaged_isolation_reports_a_refused_worker_install(tmp_path):
    result = _run(_release(tmp_path))
    if result.returncode != 0:
        raise AssertionError(f"{result.stdout}{result.stderr}")
    assert "isolation-verify: OK" in result.stdout


def test_the_verifier_fails_a_module_that_only_awaits_ready(tmp_path):
    """The superseded implementation left a page with a refused worker silent."""
    destination = _release(tmp_path)
    (destination / "isolation.mjs").write_text(WAITING_MODULE)
    result = _run(destination)
    assert result.returncode != 0, "a module that only awaits ready must be refused"
    assert "a refused worker install is reported" in result.stderr
