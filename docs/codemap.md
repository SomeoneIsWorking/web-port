# Ownership

| Subsystem | Responsibility | Location | Entry point |
|---|---|---|---|
| Native dependency prefix | Pinned browser-library sources, Emscripten CMake composition and installation | `CMakeLists.txt`, `cmake/Dependencies.cmake` | `web_port_dependencies` |
| Shader conversion | Pinned Naga provisioning, SDL sampler slots, depth-image declarations and atomic WGSL publication | `tools/shaders.py`, `tools/shader_depth.py`, `tools/shader_arrays.py` | `convert` |
| Release packaging | Exact redistributable resource map, content version and Lucent offline-worker rendering | `tools/package.py` | `package_application` |
| Build contract | Toolchain validation, locked build invocation and required prefix manifest | `tools/web_port.py` | `main` |
| Verification | Lint, source size and shipping-tool regression composition | `tools/verify.py`, `tests/` | `main` |

Browser runtime platform behavior belongs to Lucent. Game policy and executable
identity belong to consuming titles. This project contains neither.
