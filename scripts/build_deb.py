#!/usr/bin/env python3
"""Build only, never install. Run in a disposable Linux container/CI runner."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "linux":
        raise SystemExit("Build the .deb in the provided Docker image or Ubuntu CI VM.")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="webpatch-deb-") as temporary:
        stage = Path(temporary) / "webpatch"
        control = stage / "DEBIAN"
        control.mkdir(parents=True)
        (control / "control").write_text(
            "Package: webpatch\nVersion: 0.1.0\nSection: admin\nPriority: optional\n"
            "Architecture: all\nDepends: python3 (>= 3.10), dpkg\n"
            "Maintainer: WebPatch contributors <webpatch@example.invalid>\n"
            "Description: Evidence-driven web runtime maintenance preview\n"
            " Read-only PHP/Node inventory and explicitly confirmed scoped maintenance.\n")
        shutil.copytree(ROOT / "src/webpatch", stage / "usr/lib/webpatch/webpatch",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        binary = stage / "usr/bin/webpatch"
        binary.parent.mkdir(parents=True)
        binary.write_text(
            "#!/usr/bin/python3 -I\nimport sys\nsys.dont_write_bytecode = True\n"
            "sys.path.insert(0, '/usr/lib/webpatch')\nfrom webpatch.cli import main\n"
            "raise SystemExit(main())\n")
        binary.chmod(0o755)
        doc = stage / "usr/share/doc/webpatch"
        doc.mkdir(parents=True)
        for source, target in (("README.md", "README.md"), ("LICENSE", "copyright"),
                               ("docs/design.md", "docs/design.md"), ("docs/cli.md", "docs/cli.md"),
                               ("docs/phase-3.md", "docs/phase-3.md"), ("docs/phase-4.md", "docs/phase-4.md")):
            (doc / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, doc / target)
        env = dict(os.environ)
        env.setdefault("SOURCE_DATE_EPOCH", "1792627200")
        artifact = output / "webpatch_0.1.0_all.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(stage), str(artifact)],
                       check=True, env=env)
        print(artifact)


if __name__ == "__main__":
    main()
