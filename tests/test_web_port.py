"""Refusals at the actual dependency manifest and toolchain boundary."""

from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from web_port import EMSCRIPTEN_VERSION, REQUIRED, emscripten, validate_prefix
import web_port


def test_prefix_requires_every_declared_output(tmp_path):
    for name in REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    validate_prefix(tmp_path)
    (tmp_path / "lib/libavcodec.a").unlink()
    with pytest.raises(ValueError, match="lib/libavcodec.a"):
        validate_prefix(tmp_path)


def test_toolchain_version_is_measured(tmp_path):
    root = tmp_path / "upstream/emscripten"
    root.mkdir(parents=True)
    (root / "emcc").touch()
    version = root / "emscripten-version.txt"
    version.write_text(EMSCRIPTEN_VERSION)
    assert emscripten(tmp_path) == root
    version.write_text("0.0.0")
    with pytest.raises(ValueError, match="found 0.0.0"):
        emscripten(tmp_path)


def test_installed_contract_refuses_changed_build_recipe(tmp_path, monkeypatch):
    monkeypatch.setattr(web_port, "ROOT", tmp_path)
    for name in ("cmake/Dependencies.cmake", "cmake/bzip2/CMakeLists.txt"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original recipe")
    for name in REQUIRED:
        path = tmp_path / "prefix" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    manifest = {"schema": 1, "emscripten": EMSCRIPTEN_VERSION, "pthread": True,
                "contract": web_port.dependency_contract()}
    (tmp_path / "prefix/web-port-dependencies.json").write_text(json.dumps(manifest))
    web_port.validate_install(tmp_path / "prefix")
    (tmp_path / "cmake/Dependencies.cmake").write_text("changed source revision")
    with pytest.raises(ValueError, match="stale browser dependency prefix"):
        web_port.validate_install(tmp_path / "prefix")
