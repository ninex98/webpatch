"""Real signature rejection using a disposable copy; never alters APT lists."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

assert os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
report = json.loads(Path("ci-evidence/vm-root-scan.json").read_text())
commands = [json.loads(e["target"]) for e in report["evidence"] if e["operation"] == "run" and 'gpgv' in e["target"] and e["outcome"] == "EXIT_0"]
assert commands
raw = Path(commands[0][-1]).read_bytes()
assert b"Origin: Ubuntu" in raw
tampered = raw.replace(b"Origin: Ubuntu", b"Origin: Forged", 1)
with tempfile.TemporaryDirectory(prefix="webpatch-signature-test-") as folder:
    path = Path(folder) / "InRelease"
    path.write_bytes(tampered)
    result = subprocess.run([*commands[0][:-1], str(path)], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and "BADSIG" in result.stdout
Path("ci-evidence/signature-negative.json").write_text(json.dumps({
    "result": "PASS", "test": "modified signed Release rejected by real gpgv",
    "original_sha256": hashlib.sha256(raw).hexdigest(),
    "tampered_sha256": hashlib.sha256(tampered).hexdigest(),
    "gpgv_exit": result.returncode,
}, indent=2) + "\n")
