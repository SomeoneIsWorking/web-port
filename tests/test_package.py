"""The package owns an exact public allowlist and content-addressed offline cache."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application


def fixture(tmp_path):
    runtime = tmp_path / "lucent/platforms/web"
    runtime.mkdir(parents=True)
    (runtime / "storage.mjs").write_text("storage")
    (runtime / "isolation.mjs").write_text("isolation")
    (runtime / "service-worker.js").write_text("const RELEASE = __LUCENT_WEB_RELEASE__;")
    index = tmp_path / "index.html"
    index.write_text("first release")
    return tmp_path / "release", {"index.html": index}, tmp_path / "lucent"


def manifest(destination):
    source = (destination / "service-worker.js").read_text()
    return json.loads(source.removeprefix("const RELEASE = ").removesuffix(";"))


def test_explicit_inputs_and_content_version(tmp_path):
    destination, files, lucent = fixture(tmp_path)
    (tmp_path / "XMen2.exe").write_text("restricted fixture must never be discovered")
    package_application(destination, files, lucent)
    first = manifest(destination)
    assert first["files"] == ["index.html", "isolation.mjs", "storage.mjs"]
    assert not (destination / "XMen2.exe").exists()
    files["index.html"].write_text("changed release")
    package_application(destination, files, lucent)
    assert first["version"] != manifest(destination)["version"]


def test_unowned_output_and_unsafe_name_refused(tmp_path):
    destination, files, lucent = fixture(tmp_path)
    for name in ("../outside", "..\\outside", "query?file", "fragment#file"):
        with pytest.raises(ValueError, match="safe release filename"):
            package_application(destination, {**files, name: files["index.html"]}, lucent)
    destination.mkdir()
    (destination / "unowned.data").touch()
    with pytest.raises(ValueError, match="unowned files"):
        package_application(destination, files, lucent)
