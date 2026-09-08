# Project goals

## G001 — One browser dependency build contract

Build pinned, redistributable native browser dependencies for consuming ports
through one Emscripten owner. Success requires a cold build, validated prefix,
repeatable incremental build, and consumers resolving that prefix without
desktop library fallback. Linux, Windows and macOS maintainers use the same
locked Python builder. Game files and title runtime policy are excluded.
