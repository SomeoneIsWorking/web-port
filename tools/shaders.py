#!/usr/bin/env python3
"""Provision the pinned WGSL translator and convert SDL_GPU SPIR-V shaders."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from shader_depth import declare_depth
from shader_arrays import extract

ROOT = Path(__file__).resolve().parents[1]
NAGA_VERSION = "30.0.0"
TOOLS = ROOT / "build/tools"
NAGA = TOOLS / "naga/bin" / ("naga.exe" if os.name == "nt" else "naga")


def required_program(name: str) -> str:
    program = shutil.which(name)
    if program is None:
        raise RuntimeError(f"required shader tool {name} is missing")
    return program


def provision() -> Path:
    if not NAGA.is_file():
        cargo = required_program("cargo")
        temporary = ROOT / "scratch/shaders"
        temporary.mkdir(parents=True, exist_ok=True)
        environment = dict(
            os.environ,
            CARGO_HOME=str(TOOLS / "cargo"),
            CARGO_TARGET_DIR=str(TOOLS / "naga-build"),
            TMPDIR=str(temporary),
        )
        subprocess.run(
            [
                cargo,
                "install",
                "naga-cli",
                "--version",
                NAGA_VERSION,
                "--locked",
                "--root",
                str(TOOLS / "naga"),
            ],
            env=environment,
            check=True,
        )
    version = subprocess.run(
        [str(NAGA), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if version != NAGA_VERSION:
        raise RuntimeError(f"expected Naga {NAGA_VERSION}, found {version!r} at {NAGA}")
    return NAGA


def convert(
    source: Path,
    output: Path,
    *,
    stage: str | None = None,
    include: bool = False,
    depth_samplers: tuple[tuple[int, int], ...] = (),
    c_array: str | None = None,
) -> None:
    """Preserve SDL clip coordinates and split combined samplers into slot pairs."""
    if stage is not None and c_array is not None:
        raise ValueError("choose shader source stage or SPIR-V byte array, not both")
    source = source.resolve(strict=True)
    output = output.resolve()
    owned_paths = {output} | {
        output.with_suffix(output.suffix + suffix)
        for suffix in (
            ".source.spv",
            ".split.spv",
            ".generated.wgsl",
            ".depth.spvasm",
            ".pending",
        )
    }
    if source in owned_paths:
        raise ValueError(
            "shader source and output/intermediate files must be different paths"
        )
    if len(set(depth_samplers)) != len(depth_samplers):
        raise ValueError("depth sampler bindings must be unique")
    output.parent.mkdir(parents=True, exist_ok=True)
    naga = provision()
    optimizer = required_program("spirv-opt")
    # Stable sibling build outputs make rebuilds overwrite rather than accumulate.
    spirv = output.with_suffix(output.suffix + ".source.spv")
    split = output.with_suffix(output.suffix + ".split.spv")
    wgsl = output.with_suffix(output.suffix + ".generated.wgsl")
    if stage is not None:
        subprocess.run(
            [
                required_program("glslc"),
                f"-fshader-stage={stage}",
                str(source),
                "-o",
                str(spirv),
            ],
            check=True,
        )
        source_spirv = spirv
    elif c_array is not None:
        spirv.write_bytes(extract(source.read_text(), c_array))
        source_spirv = spirv
    else:
        source_spirv = source
    # SDL SPIR-V combines image+sampler at slot N; WGSL separates them at
    # 2N and 2N+1. SPIRV-Tools owns this IR transform and collision resolution.
    subprocess.run(
        [
            optimizer,
            "--split-combined-image-sampler",
            "--resolve-binding-conflicts",
            str(source_spirv),
            "-o",
            str(split),
        ],
        check=True,
    )
    if depth_samplers:
        assembly = subprocess.run(
            [required_program("spirv-dis"), "--raw-id", str(split)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        depth_assembly = output.with_suffix(output.suffix + ".depth.spvasm")
        depth_assembly.write_text(
            declare_depth(
                assembly, [(group, slot * 2) for group, slot in depth_samplers]
            )
        )
        subprocess.run(
            [required_program("spirv-as"), str(depth_assembly), "-o", str(split)],
            check=True,
        )
        subprocess.run([required_program("spirv-val"), str(split)], check=True)
    # SDL already normalizes Vulkan's viewport to the other GPU backends.
    # Naga's default SPIR-V Y inversion would therefore flip the image twice.
    subprocess.run(
        [str(naga), "--keep-coordinate-space", str(split), str(wgsl)], check=True
    )
    subprocess.run([str(naga), str(wgsl)], check=True)
    data = wgsl.read_bytes()
    if not data.strip():
        raise RuntimeError(f"shader translator produced empty output for {source}")
    if include:
        # A C string initializer, suitable for #include beside a char array.
        lines = [
            '"' + "".join(f"\\x{byte:02x}" for byte in data[i : i + 24]) + '"'
            for i in range(0, len(data), 24)
        ]
        data = ("\n".join(lines) + "\n").encode("ascii")
    pending = output.with_suffix(output.suffix + ".pending")
    pending.write_bytes(data)
    pending.replace(output)


def sampler_binding(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdecimal() for part in parts):
        raise argparse.ArgumentTypeError("depth sampler must be nonnegative GROUP:SLOT")
    return int(parts[0]), int(parts[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("provision")
    conversion = commands.add_parser("convert")
    conversion.add_argument("source", type=Path)
    conversion.add_argument("output", type=Path)
    conversion.add_argument("--stage", choices=("vert", "frag", "comp"))
    conversion.add_argument("--include", action="store_true")
    conversion.add_argument(
        "--c-array", help="SPIR-V unsigned char array name in source header"
    )
    conversion.add_argument(
        "--depth-sampler",
        action="append",
        default=[],
        type=sampler_binding,
        metavar="GROUP:SLOT",
    )
    args = parser.parse_args()
    if args.command == "provision":
        print(provision())
    else:
        convert(
            args.source,
            args.output,
            stage=args.stage,
            include=args.include,
            depth_samplers=tuple(args.depth_sampler),
            c_array=args.c_array,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
