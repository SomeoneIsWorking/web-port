"""Verify the browser runtime C++ against its Emscripten compile database."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "src/web_storage.cpp",
    ROOT / "tests/test_web_storage.cpp",
)
FORMATTED = (*SOURCES, ROOT / "include/web_port/storage.h")


def verify(environment: dict[str, str]) -> None:
    emsdk_value = environment.get("EMSDK")
    if not emsdk_value:
        raise RuntimeError("Set EMSDK to the pinned Emscripten SDK before verifying web-port C++")
    emsdk = Path(emsdk_value).resolve()
    emscripten = emsdk / "upstream/emscripten"
    emcmake = emscripten / "emcmake"
    sysroot = emscripten / "cache/sysroot/include"
    for required in (emcmake, sysroot / "emscripten/threading.h"):
        if not required.is_file():
            raise FileNotFoundError(f"Incomplete Emscripten SDK: {required}")
    for name in ("cmake", "clang-format", "clang-tidy"):
        if not shutil.which(name):
            raise RuntimeError(f"web-port C++ verification requires {name} on PATH")

    for source in FORMATTED:
        subprocess.run(["clang-format", "--dry-run", "--Werror", str(source)], check=True)

    build = ROOT / "build/runtime-tests"
    subprocess.run(
        [str(emcmake), "cmake", "-S", str(ROOT / "tests"), "-B", str(build),
         "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"],
        cwd=ROOT, env=environment, check=True,
    )
    subprocess.run(["cmake", "--build", str(build)], cwd=ROOT, env=environment, check=True)
    subprocess.run(
        ["clang-tidy", "-p", str(build),
         "--extra-arg=--target=wasm32-unknown-emscripten",
         f"--extra-arg=-isystem{sysroot / 'c++/v1'}",
         f"--extra-arg=-isystem{sysroot}",
         *(str(source) for source in SOURCES)],
        cwd=ROOT, env=environment, check=True,
    )


if __name__ == "__main__":
    verify(dict(os.environ))
