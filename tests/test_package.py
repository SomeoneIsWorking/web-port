"""The package owns an exact public allowlist and content-addressed offline cache."""

import hashlib
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


def code_only(source):
    """Drop comments so a contract check reads the shipped code, not prose."""
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", without_blocks)


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


def test_release_addresses_every_cached_byte(tmp_path):
    """The version names the bytes, so the hashes must describe those same bytes."""
    destination, files = fixture(tmp_path)
    package_application(destination, files)
    release = manifest(destination)
    assert set(release["hashes"]) == set(release["files"])
    for name, expected in release["hashes"].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == expected


def test_install_verifies_each_cached_body(tmp_path):
    """A cache that can hold bytes the version does not name is the bug this fixes.

    The template is the shipped source of the worker, so assert its contract:
    it fetches past the HTTP cache and refuses a body that fails its hash.
    """
    destination, files = fixture(tmp_path)
    package_application(destination, files)
    source = code_only((destination / "service-worker.js").read_text())
    assert "cache.addAll" not in source
    assert 'fetch(url, {cache: "reload"})' in source
    assert "crypto.subtle.digest" in source
    assert "RELEASE.hashes[releaseName(url)]" in source


def test_unowned_output_and_unsafe_name_refused(tmp_path):
    destination, files = fixture(tmp_path)
    for name in ("../outside", "..\\outside", "query?file", "fragment#file"):
        with pytest.raises(ValueError, match="safe release filename"):
            package_application(destination, {**files, name: files["index.html"]})
    destination.mkdir()
    (destination / "unowned.data").touch()
    with pytest.raises(ValueError, match="unowned files"):
        package_application(destination, files)
