"""Assemble a versioned Linux release directory; never publish or install."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

from package_version import ROOT, package_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    version = package_version()
    if args.tag != f'v{version}':
        parser.error(f'Tag must match the source version: v{version}')
    package = ROOT / 'dist' / f'webpatch_{version}_all.deb'
    for field, expected in [('Package', 'webpatch'), ('Version', version), ('Architecture', 'all')]:
        actual = subprocess.check_output(['dpkg-deb', '--field', str(package), field], text=True).strip()
        if actual != expected:
            raise SystemExit(f'Package {field} mismatch')
    output = ROOT / 'dist' / 'release'
    if output.exists():
        raise SystemExit('dist/release already exists; use a clean build directory')
    output.mkdir()
    for source in [package, ROOT / 'install.sh', ROOT / 'LICENSE']:
        shutil.copyfile(source, output / source.name)
    (output / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
        for path in sorted(output.iterdir())), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
