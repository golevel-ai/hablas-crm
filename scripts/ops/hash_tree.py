#!/usr/bin/env python3
"""Create a deterministic SHA-256 manifest for a release directory."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--file", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    if (args.root.is_symlink() or args.output.is_symlink() or not root.is_dir()
            or not output.parent.is_dir()):
        print("BLOCKED: release root or manifest parent is absent", file=sys.stderr)
        return 2
    if output == root or root in output.parents:
        print("BLOCKED: manifest output must be outside the release tree", file=sys.stderr)
        return 2

    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            print("BLOCKED: release tree contains a symlink", file=sys.stderr)
            return 2
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        files[relative] = digest

    for value in args.file:
        label, separator, raw_path = value.partition("=")
        path = Path(raw_path)
        if (not separator or not label or "/" in label or "\\" in label
                or path.is_symlink() or not path.is_file() or label in files):
            print("BLOCKED: invalid or unavailable labeled release file", file=sys.stderr)
            return 2
        files[label] = hashlib.sha256(path.read_bytes()).hexdigest()

    if not files:
        print("BLOCKED: release tree is empty", file=sys.stderr)
        return 2

    tree = hashlib.sha256()
    for relative, digest in sorted(files.items()):
        tree.update(relative.encode() + b"\0" + bytes.fromhex(digest))

    manifest = {
        "algorithm": "sha256(path\\0sha256(content))",
        "tree_sha256": tree.hexdigest(),
        "files_sha256": files,
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "files": len(files), "tree_sha256": tree.hexdigest()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
