#!/usr/bin/env python3
from hashlib import sha256
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"

raw = subprocess.check_output(
    ["git", "-C", str(ROOT), "ls-files", "-z"],
)
paths = sorted(
    p.decode("utf-8") for p in raw.split(b"\0") if p
)
paths = [p for p in paths if p != "MANIFEST.sha256"]

lines = []
for rel in paths:
    data = (ROOT / rel).read_bytes()
    lines.append(f"{sha256(data).hexdigest()}  {rel}")

MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {MANIFEST.name}: {len(lines)} files")
