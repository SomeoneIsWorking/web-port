#!/usr/bin/env python3
"""Build the shared, pthread-enabled browser native dependency prefix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
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


# EVERY GIT PIN IN THE DECLARATIONS MUST BE ACCOUNTED FOR.
#
# Two shapes carry a revision. `web_library(name repo rev)` passes it as the
# third argument -- the helper's own `GIT_TAG "${revision}"` is a variable, not
# a pin -- and the other projects write a literal `GIT_TAG <40 hex>` inside
# their declaration, where the name is either on the ExternalProject_Add or on
# a `set(_sdl_source SOURCE_DIR ".../sources/sdl" ...)` that exists because SDL
# also accepts a local source override.
#
# Both are read, and then the count is CHECKED: a parser that quietly skipped a
# declaration it did not recognise would report "all pins verified" while never
# looking at that dependency, which is the exact failure this check exists to
# catch. That already happened twice while writing it -- one version dropped
# bzip2 because its declaration does not end on its own line, and the next
# dropped all five web_library dependencies because they carry no literal tag.
#
# ffmpeg is deliberately absent: it is a tarball pinned by SHA256, which
# ExternalProject re-fetches itself when the hash changes, so it has no
# checkout that can go stale.
_HELPER = re.compile(r"web_library\(\s*(?P<name>\w+)\s+\S+\s+(?P<rev>[0-9a-f]{40})")
_LITERAL_TAG = re.compile(r"GIT_TAG\s+(?P<rev>[0-9a-f]{40})")
_NAMES = re.compile(
    r'ExternalProject_Add\(\s*(?P<add>\w+)'
    r'|SOURCE_DIR\s+"\$\{CMAKE_BINARY_DIR\}/sources/(?P<explicit>\w+)"')


def pinned_revisions() -> dict[str, str]:
    """Every git-pinned dependency and the revision it must be at.

    Read from the file that DECLARES them, so this cannot drift from the build
    the way a second hand-maintained list would.
    """
    text = (ROOT / "cmake/Dependencies.cmake").read_text()
    pins = {m.group("name"): m.group("rev") for m in _HELPER.finditer(text)}
    names = [(m.start(), m.group("add") or m.group("explicit")) for m in _NAMES.finditer(text)]
    for tag in _LITERAL_TAG.finditer(text):
        owner = [name for position, name in names if position < tag.start()]
        if not owner:
            raise ValueError(f"a literal GIT_TAG at offset {tag.start()} belongs to no named project")
        pins[owner[-1]] = tag.group("rev")
    declared = len(_HELPER.findall(text)) + len(_LITERAL_TAG.findall(text))
    if len(pins) != declared:
        raise ValueError(f"{declared} git pin(s) declared but {len(pins)} attributed to a project; "
                         "cmake/Dependencies.cmake grew a shape this parser does not read")
    return pins


def _checkout(build: Path, name: str) -> Path | None:
    """Where ExternalProject put `name`'s working tree, or None if it has not
    been fetched yet. The two layouts are an explicit SOURCE_DIR under
    `sources/` and ExternalProject's own default under the project prefix."""
    for candidate in (build / "sources" / name, build / name / "src" / name):
        if (candidate / ".git").exists():
            return candidate
    return None


def _head(source: Path) -> str:
    return subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def validate_sources(build: Path, skip: set[str]) -> None:
    """Every checked-out dependency is at its pinned revision.

    ExternalProject writes a `-done` stamp and never looks at GIT_TAG again, so
    BUMPING A PIN DOES NOT MOVE THE SOURCE -- measured: an SDL pin bump
    configured, built, installed and wrote a fresh dependency contract over a
    prefix still compiled from the previous revision, reporting success at
    every step. That contract then certifies the wrong bytes to every consumer,
    which is worse than not checking at all.

    A dependency that has never been fetched is reported, not skipped: "no
    checkout" and "checkout at the right revision" must not print the same.
    """
    wrong, unfetched = [], []
    for name, revision in sorted(pinned_revisions().items()):
        if name in skip:
            continue
        source = _checkout(build, name)
        if source is None:
            unfetched.append(name)
            continue
        head = _head(source)
        if head != revision:
            wrong.append(f"{name}: checked out {head[:12]}, pinned {revision[:12]} ({source})")
    if wrong:
        raise ValueError(
            "dependency source(s) are not at their pinned revision:\n  " + "\n  ".join(wrong)
            + "\nExternalProject will not move them on its own; delete the matching "
              "stamp directory under build/dependencies and build again.")
    if unfetched:
        raise ValueError("dependency source(s) were never fetched, so their pin is unverified: "
                         + ", ".join(unfetched))


def refresh_stale_pins(build: Path, skip: set[str]) -> None:
    """Make a bumped pin take effect, by dropping the stamps that say done.

    Only the stamps. The `*-info.txt` files beside them are generated at
    CONFIGURE time and are build inputs, not records of completed work, so
    removing the whole directory breaks the build outright:
    `ninja: error: 'sdl/src/sdl-stamp/sdl-patch-info.txt', needed by
    'sdl/src/sdl-stamp/sdl-patch', missing and no known rule to make it`.
    """
    for name, revision in sorted(pinned_revisions().items()):
        if name in skip:
            continue
        source = _checkout(build, name)
        stamps = build / name / "src" / f"{name}-stamp"
        if source is None or not stamps.is_dir():
            continue
        head = _head(source)
        if head == revision:
            continue
        print(f"web-port: {name} is at {head[:12]} but is pinned to {revision[:12]}; re-running its steps")
        for stamp in stamps.iterdir():
            if stamp.is_file() and not stamp.name.endswith("-info.txt"):
                stamp.unlink()


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
    # A local SDL source has no pin to honour: the caller is building the tree
    # it handed us, which is the point of the override.
    overridden = {"sdl"} if args.sdl_source else set()
    refresh_stale_pins(build, overridden)
    subprocess.run(["cmake", "--build", str(build), "-j", str(args.jobs)],
                   cwd=ROOT, env=environment, check=True)
    validate_prefix(prefix)
    validate_sources(build, overridden)
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
