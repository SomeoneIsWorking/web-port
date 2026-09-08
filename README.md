# web-port

Shared deterministic Emscripten dependencies for native game ports. This owns
the pthread-enabled SDL WebGPU, SDL_image, SDL_ttf, FreeType, zlib and FFmpeg
prefix. Titles consume its CMake package exports and validated manifest;
browser runtime behavior belongs to Lucent, and game validation belongs to titles.

The standalone normal verifier is `uv run --frozen python tools/verify.py`.
It checks Python lint, source structure, dependency/packaging refusals and actual
shader conversion. The builder and `run.sh` never run tests.

Build with Emscripten 4.0.16 selected through `EMSDK`:

```
uv run --frozen python tools/web_port.py
```

The default prefix is `build/prefix`. `--prefix` selects an explicit consumer
build path. `--sdl-source` is a development checkout override for the maintained
SDL fork; published builds use its pinned revision. No game files are build inputs.

This repository builds dependencies, not a game. See `docs/project-state.md`
for the measured state and `docs/codemap.md` for ownership.

`tools/package.py` receives one explicit map of redistributable release resources
and a pinned Lucent checkout. It adds Lucent's storage/isolation modules and renders
the service worker's exact content-addressed offline allowlist. It refuses unknown
files already in the destination. Titles own their page, app identity, icons and
native runtime artifact names; player files are never packaging inputs.

Shader conversion uses host `glslc`, SPIRV-Tools (`spirv-opt`, `spirv-dis`,
`spirv-as`, `spirv-val`) and Rust `cargo`. `tools/shaders.py provision` installs
Naga CLI 30.0.0 with its locked Cargo dependency graph under `build/tools/`.
SPIRV-Tools must support `--split-combined-image-sampler` and
`--resolve-binding-conflicts`; the verified host version is 2026.1.

```
uv run --frozen python tools/shaders.py convert material.frag material.inc --stage frag --include
```

Omit `--stage` for an existing SPIR-V module. `--c-array NAME` reads a named
SPIR-V byte array from an SDL_shadercross generated header. `--include` emits a nul-terminated
C string initializer; without it the output is plain WGSL. Combined SDL sampler
slot N becomes texture binding 2N and sampler binding 2N+1. Clip coordinates stay
unchanged because SDL normalizes Vulkan's viewport itself. A depth view sampled
through GLSL `sampler2D` requires `--depth-sampler GROUP:SLOT`: this declares the
actual depth image in SPIR-V before translation, preserving ordinary raw-depth
sampling, without changing it to hardware comparison sampling. Direct global
image loads are supported; unsupported image forwarding fails by instruction.
Failed conversion preserves the previous published output.

Run shader verification separately from provisioning:

```
uv run --frozen pytest -q tests/test_shaders.py
```
