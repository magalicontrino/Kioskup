#!/usr/bin/env python3
"""Local preview server for the static site.

chdir happens before http.server is imported: the module resolves os.getcwd()
at import time, which fails if the launcher's cwd is not readable.
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

PORT = 8181

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), SimpleHTTPRequestHandler).serve_forever()
