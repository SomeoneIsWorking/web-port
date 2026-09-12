# Ownership

| Subsystem | Responsibility | Location | Entry point |
|---|---|---|---|
| Native dependency prefix | Pinned browser-library sources, Emscripten CMake composition and installation | `CMakeLists.txt`, `cmake/Dependencies.cmake` | `web_port_dependencies` |
| Shader conversion | Pinned Naga provisioning, SDL sampler slots, depth-image declarations and atomic WGSL publication | `tools/shaders.py`, `tools/shader_depth.py`, `tools/shader_arrays.py` | `convert` |
| Browser private storage | OPFS mount/unmount on the application worker and bounded browser-file staging | `include/web_port/storage.h`, `src/web_storage.cpp`, `platforms/web/storage.mjs` | `web_port_mount_storage`, `FileStager` |
| Browser isolation | Service-worker registration, first-navigation reload and offline release cache | `platforms/web/isolation.mjs`, `platforms/web/service-worker.js` | `prepareApplication` |
| Release packaging | Exact redistributable resource map, content version and offline-worker rendering | `tools/package.py` | `package_application` |
| Build contract | Toolchain validation, locked build invocation and required prefix manifest | `tools/web_port.py` | `main` |
| Verification | Lint, source size and shipping-tool regression composition | `tools/verify.py`, `tests/` | `main` |

Game policy and executable identity belong to consuming titles.
