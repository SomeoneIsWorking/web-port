# Project state

## Comparison baseline

Previously each title would cross-build browser dependencies independently.

| ID | Capability | State | Evidence or remaining gap |
|---|---|---|---|
| S001 | Shared pthread-enabled browser native dependency prefix | partial | All twelve required SDL/image/ttf/font/compression/media outputs compiled and installed against SDL fork `3b879610`; consumer gameplay remains. |
| S002 | Linux maintainer build | partial | Emscripten 4.0.16 prefix build, three negative contract tests and Ruff passed. An unchanged second build performed zero compilations. Cold hosted qualification remains. |
| S003 | Windows and macOS maintainer builds | missing | Hosted build jobs and matching host execution evidence required. |
| S004 | Browser runtime qualification | missing | Consuming title must execute actual SDL WebGPU and media paths. |
| S005 | Explicit offline release packaging | partial | Exact input map, content version and unowned-output refusals pass two tests. The framework worker reached isolated reload on a host without isolation headers and after the server stopped. Real consumer offline gameplay remains. |
| S006 | Browser applications stage and access files through private origin storage | partial | Worker mount/write/unmount/remount/read/remove passed in isolated Chromium, including six invalid mounts; bounded Blob staging and persistence-grant reporting passed. SDK OPFS worker shutdown on the browser main thread and complete consumer offline relaunch remain unqualified. |

Current focus: complete and verify the shared prefix for X-Men 2 and LF2.

Android is not a shipping target: Android toolchain and packaging belong to
`shared/android-port`; this repository builds browser artifacts.
