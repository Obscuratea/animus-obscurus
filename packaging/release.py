#!/usr/bin/env python3
"""Publish the current VERSION as a GitHub Release (what the in-app updater looks for).

Run packaging/build_windows.py first, then: python3 packaging/release.py [--yes]
Uploads the Update zip + its .sha256 (read by the updater) and the full Windows zip,
with this version's section of CHANGELOG.md as the release notes. Needs `gh` logged in.
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ver = re.search(r'^VERSION = "([^"]+)"', open(os.path.join(ROOT, "server.py")).read(), re.M).group(1)
log = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
m = re.search(rf"^## {re.escape(ver)}\b.*?\n(.*?)(?=^## |\Z)", log, re.M | re.S)
if not m:
    sys.exit(f"CHANGELOG.md has no '## {ver}' section")
# Major (x.0.0) and minor (x.y.0) releases get a fresh "Latest release features" image + text in the README.
if ver.split(".")[-1] == "0" and f"v{ver}" not in open(os.path.join(ROOT, "README.md"), encoding="utf-8").read():
    sys.exit(f"README.md's 'Latest release features' section doesn't mention v{ver}; update the image (docs/latest-release.png) and text first")
d = os.path.join(ROOT, "dist")
files = [os.path.join(d, f"Animus-Obscurus-Update-v{ver}.zip"), os.path.join(d, f"Animus-Obscurus-Update-v{ver}.zip.sha256"),
         os.path.join(d, f"Animus-Obscurus-Windows-v{ver}.zip")]
for f in files:
    if not os.path.exists(f):
        sys.exit(f"missing {f}; run packaging/build_windows.py first")
if "--yes" not in sys.argv and input(f"Publish v{ver} to GitHub Releases? [y/N] ").lower() != "y":
    sys.exit("cancelled")
subprocess.run(["gh", "release", "create", f"v{ver}", *files, "--title", f"Animus Obscurus {ver}", "--notes", m.group(1).strip()], cwd=ROOT, check=True)
