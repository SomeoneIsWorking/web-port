#!/usr/bin/env python3
"""Build the shared, pthread-enabled browser native dependency prefix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
EMSCRIPTEN_VERSION = "4.0.16"
REQUIRED = (
    "lib/libSDL3.a", "lib/libSDL3_image.a", "lib/libSDL3_ttf.a",
    "lib/libfreetype.a", "lib/libzlibstatic.a", "lib/libavformat.a", "lib/libavcodec.a",
    "lib/libswscale.a", "lib/libswresample.a", "lib/libavutil.a", "lib/libbz2.a",
    "lib/cmake/SDL3/SDL3Config.cmake",
)


def emscripten(emsdk: Path | None) -> Path:
    found = shutil.which("emcc")
    directory = emsdk / "upstream/emscripten" if emsdk else Path(found).parent if found else None
    if directory is None or not (directory / "emcc").is_file():
        raise ValueError("Emscripten is missing; set EMSDK or pass --emsdk.")
    version = (directory / "emscripten-version.txt").read_text().strip().strip('"')
    if version != EMSCRIPTEN_VERSION:
        raise ValueError(f"web-port requires Emscripten {EMSCRIPTEN_VERSION}, found {version}")
    return directory.resolve()


def validate_prefix(prefix: Path) -> None:
    missing = [name for name in REQUIRED if not (prefix / name).is_file()]
    if missing:
        raise ValueError("incomplete web dependency prefix: " + ", ".join(missing))


def dependency_contract() -> str:
    digest = hashlib.sha256()
    for path in (ROOT / "cmake/Dependencies.cmake", ROOT / "cmake/bzip2/CMakeLists.txt"):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_install(prefix: Path) -> None:
    validate_prefix(prefix)
    path = prefix / "web-port-dependencies.json"
    contract = json.loads(path.read_text())
    if (contract.get("schema") != 1 or contract.get("emscripten") != EMSCRIPTEN_VERSION
            or contract.get("contract") != dependency_contract() or contract.get("pthread") is not True):
        raise ValueError("stale browser dependency prefix; rebuild through shared/web-port")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emsdk", type=Path, default=os.environ.get("EMSDK"))
    parser.add_argument("--prefix", type=Path, default=ROOT / "build/prefix")
    parser.add_argument("--sdl-source", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--configure-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    toolchain = emscripten(args.emsdk)
    build = ROOT / "build/dependencies"
    prefix = args.prefix.resolve()
    if args.check:
        validate_install(prefix)
        print(f"web-port: verified {len(REQUIRED)} outputs against the current dependency contract")
        return 0
    temporary = ROOT / "scratch/tool-tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(temporary))
    command = [
        str(toolchain / "emcmake"), "cmake", "-S", str(ROOT), "-B", str(build),
        "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_C_FLAGS=-pthread",
        "-DCMAKE_CXX_FLAGS=-pthread", f"-DCMAKE_INSTALL_PREFIX={prefix}",
        f"-DPython3_EXECUTABLE={sys.executable}",
    ]
    if args.sdl_source:
        command.append(f"-DWEB_PORT_SDL_SOURCE={args.sdl_source.resolve()}")
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    if args.configure_only:
        return 0
    subprocess.run(["cmake", "--build", str(build), "-j", str(args.jobs)],
                   cwd=ROOT, env=environment, check=True)
    validate_prefix(prefix)
    manifest = {
        "schema": 1, "emscripten": EMSCRIPTEN_VERSION, "pthread": True,
        "contract": dependency_contract(),
        "libraries": list(REQUIRED),
    }
    (prefix / "web-port-dependencies.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"web-port: verified {len(REQUIRED)} required prefix files in {prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
