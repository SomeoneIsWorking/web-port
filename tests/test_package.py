"""The package owns an exact public allowlist and content-addressed offline cache."""

import json
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package import package_application


def fixture(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("first release")
    return tmp_path / "release", {"index.html": index}


def manifest(destination):
    source = (destination / "service-worker.js").read_text()
    declaration = re.search(r"const RELEASE = (.+);", source)
    assert declaration is not None
    return json.loads(declaration.group(1))


def test_explicit_inputs_and_content_version(tmp_path):
    destination, files = fixture(tmp_path)
    (tmp_path / "XMen2.exe").write_text("restricted fixture must never be discovered")
    package_application(destination, files)
    first = manifest(destination)
    assert first["files"] == ["index.html", "isolation.mjs", "storage.mjs"]
    assert not (destination / "XMen2.exe").exists()
    files["index.html"].write_text("changed release")
    package_application(destination, files)
    assert first["version"] != manifest(destination)["version"]


def test_unowned_output_and_unsafe_name_refused(tmp_path):
    destination, files = fixture(tmp_path)
    for name in ("../outside", "..\\outside", "query?file", "fragment#file"):
        with pytest.raises(ValueError, match="safe release filename"):
            package_application(destination, {**files, name: files["index.html"]})
    destination.mkdir()
    (destination / "unowned.data").touch()
    with pytest.raises(ValueError, match="unowned files"):
        package_application(destination, files)
