"""Real dpkg and installed .deb smoke checks. No exploits, services or writes here."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def run(argv, expected):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    assert result.returncode in expected, (argv, result.returncode, result.stderr)
    return result


def state_hash():
    digest = hashlib.sha256()
    for root in (Path("/etc/php"), Path("/etc/apache2"), Path("/etc/apt"), Path("/var/lib/apt/lists")):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                digest.update(str(path).encode())
                digest.update(path.read_bytes())
    digest.update(Path("/var/lib/dpkg/status").read_bytes())
    return digest.hexdigest()


def main():
    # This script is meant for a container; refuse a normal host invocation.
    assert Path("/.dockerenv").exists(), "Run only in the integration container"
    archive = Path("dist/webpatch_0.1.0_all.deb")
    control = subprocess.run(["dpkg-deb", "--ctrl-tarfile", str(archive)], capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(control.stdout)) as bundle:
        assert {m.name.removeprefix("./") for m in bundle if m.isfile()} == {"control"}
    source_hashes = {}
    for path in sorted(Path("src/webpatch").rglob("*")):
        if path.suffix in {".py", ".json"}:
            relative = path.relative_to("src")
            assert path.read_bytes() == (Path("/usr/lib/webpatch") / relative).read_bytes()
            source_hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    pairs = json.loads(Path("tests/fixtures/comparisons.json").read_text())
    for installed, fixed, expected in pairs:
        result = run(["/usr/bin/dpkg", "--compare-versions", installed, "ge", fixed], {0, 1})
        assert (result.returncode == 0) == expected, (installed, fixed)
    before = state_hash()
    report = json.loads(run(["webpatch", "scan", "--format", "json"], {1, 2}).stdout)
    assert report["inventory"]["environment"]["scope"] == "container"
    packages = report["inventory"]["packages"]
    assert {"fpm", "apache2", "cli"} <= {p["sapi"] for p in packages}
    assert len(report["assessments"]) == 2 * len(packages)
    assert report["safe"] is False
    assert all(a["runtime_status"] == "UNKNOWN" for a in report["assessments"])
    assert not any(e["outcome"] in {"COMMAND_TIMEOUT", "COMMAND_OUTPUT_LIMIT"} for e in report["evidence"])
    assert "PACKAGE_QUERY_FAILED_OR_WARNED" not in report["inventory"]["coverage_gaps"]
    proposal = json.loads(run(["webpatch", "plan", "--dry-run", "--format", "json"], {4}).stdout)
    assert proposal["actions"] == [] and proposal["executable"] is False
    assert report['schema_version'] == 2 and proposal['schema_version'] == 4
    assert report['inventory']['scan_scope']['completeness'] == 'UNKNOWN'
    assert proposal['admission_status'] == 'BLOCKED'
    assert any(g['category'] == 'execution_authorization' and g['status'] == 'NOT_RUN' for g in proposal['gates'])
    run(["webpatch", "apply"], {4})
    assert before == state_hash(), "scan/plan/apply changed package metadata or configuration"
    # Installed entry point must work independently of cwd and PYTHONPATH.
    result = subprocess.run(["/usr/bin/webpatch", "--version"], cwd="/", capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "0.1.0"
    print(json.dumps({"result": "PASS", "python": sys.version, "environment": report["inventory"]["environment"],
                      "dpkg_comparison_vectors": len(pairs), "state_sha256": before,
                      "packages": packages, "rule_sha256": report["rule_sha256"],
                      "source_sha256": source_hashes}, indent=2))


if __name__ == "__main__":
    main()
