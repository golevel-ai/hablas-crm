"""Regression tests for deterministic frontend artifact manifests."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import ops


class HashTreeTests(unittest.TestCase):
    def run_hash(self, root, output, extras=None):
        command = ["python3", str(ops.ROOT / "scripts/ops/hash_tree.py"),
                   "--root", str(root), "--output", str(output)]
        for label, path in (extras or {}).items():
            command.extend(["--file", f"{label}={path}"])
        return subprocess.run(
            command,
            capture_output=True, text=True, timeout=10,
        )

    def test_manifest_is_deterministic_and_covers_every_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "dist"
            (root / "assets").mkdir(parents=True)
            (root / "index.html").write_text("<main>CRM</main>\n")
            (root / "assets/app.js").write_bytes(b"console.log('crm')\n")
            worker = base / "worker.mjs"
            worker.write_text("export default {}\n")
            wrangler = base / "wrangler.jsonc"
            wrangler.write_text('{"name":"crm"}\n')
            extras = {"worker.mjs": worker, "wrangler.jsonc": wrangler}
            first = base / "first.json"
            second = base / "second.json"

            self.assertEqual(self.run_hash(root, first, extras).returncode, 0)
            self.assertEqual(self.run_hash(root, second, extras).returncode, 0)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                list(json.loads(first.read_text())["files_sha256"]),
                ["assets/app.js", "index.html", "worker.mjs", "wrangler.jsonc"],
            )

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "dist"
            root.mkdir()
            target = base / "outside.txt"
            target.write_text("outside\n")
            (root / "linked.txt").symlink_to(target)

            result = self.run_hash(root, base / "manifest.json")
            self.assertEqual(result.returncode, 2)
            self.assertIn("contains a symlink", result.stderr)

    def test_manifest_inside_release_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dist"
            root.mkdir()
            (root / "index.html").write_text("CRM\n")

            result = self.run_hash(root, root / "manifest.json")
            self.assertEqual(result.returncode, 2)
            self.assertIn("outside the release tree", result.stderr)


if __name__ == "__main__":
    unittest.main()
