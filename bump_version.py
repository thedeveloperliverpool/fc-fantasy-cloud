#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


VERSION_FILE = Path(__file__).with_name("version.json")
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d{1,2})$")


def load_version():
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = str(data.get("version", "1.0.00"))
    match = VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Unsupported version format: {version}. Expected X.Y.ZZ")
    return data, match
def main():
    data, match = load_version()
    major, minor, patch = (int(part) for part in match.groups())

    if len(sys.argv) > 1:
        base = sys.argv[1].strip()
        base_match = re.match(r"^(\d+)\.(\d+)$", base)
        if not base_match:
            raise SystemExit("Base version must look like 1.2")
        major, minor = (int(part) for part in base_match.groups())
        patch = 0
    else:
        patch += 1

    if patch > 99:
        minor += 1
        patch = 0

    data["version"] = f"{major}.{minor}.{patch:02d}"
    data.pop("bump_every", None)
    data.pop("pending_updates", None)
    VERSION_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(data["version"])


if __name__ == "__main__":
    main()
