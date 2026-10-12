#!/usr/bin/env python3
"""Check every pinned line of a requirements-style file against PyPI.

Usage: python check_pypi.py requirements.txt

Reports:
  - dependencies checked (number of lines checked)
  - packages not on PyPI (count)
  - versions not on PyPI (count)
  - oldest pinned release (by upload_time of the first file under "urls")
"""
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

PYPI = "https://pypi.org/pypi"
LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?:={1,2}\s*([^\s;,#=]+))?")


def fetch_json(url):
    """Return parsed JSON, or None on HTTP 404. Other errors propagate."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse_line(line):
    """Return (name, version_or_None), or None if the line isn't a package."""
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith("-"):
        return None
    m = LINE_RE.match(line)
    return (m.group(1), m.group(2)) if m else None


def main(path):
    checked = 0
    missing_packages = []
    missing_versions = []
    oldest = None  # (datetime, "name==version (year)")

    with open(path, encoding="utf-8") as f:
        for raw in f:
            parsed = parse_line(raw)
            if not parsed:
                continue
            name, version = parsed
            checked += 1

            if version is None:
                # Unpinned: can only verify that the package exists.
                if fetch_json(f"{PYPI}/{name}/json") is None:
                    missing_packages.append(name)
                continue

            data = fetch_json(f"{PYPI}/{name}/{version}/json")
            if data is None:
                # Distinguish a missing package from a missing version.
                if fetch_json(f"{PYPI}/{name}/json") is None:
                    missing_packages.append(name)
                else:
                    missing_versions.append(f"{name}=={version}")
                continue

            urls = data.get("urls") or []
            if not urls:
                continue  # release exists but has no files
            uploaded = datetime.fromisoformat(urls[0]["upload_time"])
            if oldest is None or uploaded < oldest[0]:
                oldest = (uploaded, f"{name}=={version} ({uploaded.year})")

    print(f"Dependencies checked: {checked}")
    print(f"Packages not on PyPI: {len(missing_packages)}")
    print(f"Versions not on PyPI: {len(missing_versions)}")
    print(f"Oldest pinned release: {oldest[1] if oldest else 'n/a'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <requirements-file>")
    main(sys.argv[1])