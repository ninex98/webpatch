"""Record source and artifact hashes, without storing binaries or environment secrets."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
paths = [Path("pyproject.toml")]
for root in ("src/webpatch", "tests", "scripts", ".github"):
    paths.extend(p for p in Path(root).rglob("*") if p.is_file()
                 and "__pycache__" not in p.parts and p.suffix in {".py", ".json", ".sh", ".yml", ".md"})
hashes = lambda files: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
record = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
          "python": sys.version, "platform": platform.platform(),
          "source_sha256": hashes(paths),
          "artifact_sha256": hashes(p for p in destination.rglob("*") if p.is_file() and p.name != "manifest.json")}
(destination / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
