"""Archive a completed GitHub run's evidence; never commit binary packages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

run, stage = sys.argv[1:]
output = Path(stage)
output.mkdir(parents=True, exist_ok=True)
def gh(*args):
    return subprocess.check_output(["gh", *args, "--repo", "ninex98/webpatch"])
metadata = json.loads(gh("run", "view", run, "--json", "databaseId,headSha,status,conclusion,url,jobs"))
(output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
assert metadata["status"] == "completed", "Run has not completed"
(output / "actions.log").write_bytes(gh("run", "view", run, "--log"))
download = Path("ci-evidence") / run
subprocess.run(["gh", "run", "download", run, "--repo", "ninex98/webpatch", "--dir", str(download)], check=True)
hashes = {}
for path in sorted(download.rglob("*")):
    if not path.is_file(): continue
    relative = path.relative_to(download)
    hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix != ".deb":
        destination = output / "artifacts" / str(relative).replace("ci-evidence/", "results/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
commit = metadata["headSha"]
sources = {}
for name in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], text=True).splitlines():
    if name.startswith(("src/", "tests/", "scripts/", ".github/")) or name == "pyproject.toml":
        sources[name] = hashlib.sha256(subprocess.check_output(["git", "show", f"{commit}:{name}"])).hexdigest()
(output / "ci-manifest.json").write_text(json.dumps({"commit": commit, "source_sha256": sources, "artifact_sha256": hashes}, indent=2) + "\n")
print(metadata["url"], metadata["conclusion"])
assert metadata["conclusion"] == "success"
assert all(j["conclusion"] == "success" for j in metadata["jobs"])
