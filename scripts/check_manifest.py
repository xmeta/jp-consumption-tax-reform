#!/usr/bin/env python3
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
if not MANIFEST.exists():
    raise SystemExit("MANIFEST.sha256 is missing")

expected = {}
for line in MANIFEST.read_text(encoding="utf-8").splitlines():
    digest, rel = line.split("  ", 1)
    expected[rel] = digest

raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"])
tracked = sorted(p.decode("utf-8") for p in raw.split(b"\0") if p)
tracked = [p for p in tracked if p != "MANIFEST.sha256"]
errors = []
if set(expected) != set(tracked):
    errors.append(
        f"path set mismatch: expected={len(expected)} tracked={len(tracked)}"
    )

for rel in sorted(set(expected) & set(tracked)):
    actual = sha256((ROOT / rel).read_bytes()).hexdigest()
    if actual != expected[rel]:
        errors.append(f"hash mismatch: {rel}")

if errors:
    print("\n".join("ERROR: " + e for e in errors))
    sys.exit(1)

print(f"manifest validation: OK ({len(tracked)} files)")
