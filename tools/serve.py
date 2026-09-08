#!/usr/bin/env python3
"""Serve a local browser build with the isolation required by native pthreads."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class IsolatedFiles(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    directory = args.directory.resolve(strict=True)
    if not directory.is_dir():
        parser.error("directory must be an existing browser build directory")
    handler = partial(IsolatedFiles, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving {directory} at http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
