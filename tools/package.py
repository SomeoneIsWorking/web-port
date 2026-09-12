"""Stage explicit redistributable browser inputs and render their offline cache."""

from __future__ import annotations

import hashlib
import json
import argparse
import re
from pathlib import Path
import shutil


def package_application(destination: Path, files: dict[str, Path]) -> None:
    """Package only the caller's exact asset map, never a build-tree glob."""
    inputs = dict(files)
    runtime = Path(__file__).resolve().parents[1] / "platforms/web"
    for name in ("storage.mjs", "isolation.mjs"):
        if name in inputs:
            raise ValueError(f"Reserved shared runtime resource: {name}")
        inputs[name] = runtime / name
    if "index.html" not in inputs:
        raise ValueError("Browser package requires index.html")
    for name, source in inputs.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name == "service-worker.js":
            raise ValueError(f"Expected one safe release filename: {name}")
        if not source.is_file():
            raise FileNotFoundError(f"Browser release input is missing: {source}")
    template = (runtime / "service-worker.js").read_text()
    marker = "__WEB_PORT_RELEASE__"
    if template.count(marker) != 1:
        raise ValueError("web-port service worker must have exactly one release marker")
    destination.mkdir(parents=True, exist_ok=True)
    allowed = set(inputs) | {"service-worker.js", ".nojekyll"}
    unexpected = {item.name for item in destination.iterdir()} - allowed
    if unexpected:
        raise ValueError(f"Release directory contains unowned files: {sorted(unexpected)}")
    digest = hashlib.sha256()
    digest.update(template.encode())
    for name, source in sorted(inputs.items()):
        digest.update(name.encode() + b"\0")
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        shutil.copyfile(source, destination / name)
    release = {"version": digest.hexdigest(), "files": sorted(inputs)}
    (destination / "service-worker.js").write_text(template.replace(marker, json.dumps(release)))
    (destination / ".nojekyll").write_text("")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--file", action="append", default=[], metavar="NAME=PATH")
    args = parser.parse_args()
    files = {}
    for item in args.file:
        name, separator, path = item.partition("=")
        if not separator or name in files:
            parser.error(f"Expected one unique NAME=PATH: {item}")
        files[name] = Path(path)
    package_application(args.destination, files)


if __name__ == "__main__":
    main()
