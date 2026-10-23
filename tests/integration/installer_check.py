"""Real package installation in disposable containers, with offline release transport."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path('/work')
RELEASE = ROOT / 'dist/release'


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, **kwargs)


def main():
    assert Path('/.dockerenv').exists(), 'Installation tests must run in a disposable container'
    version = run(['python3', 'scripts/package_version.py'], check=True).stdout.strip()
    asset = f'webpatch_{version}_all.deb'
    checks = []
    with tempfile.TemporaryDirectory(prefix='webpatch-installer-test-') as directory:
        work = Path(directory)
        commands = work / 'bin'
        commands.mkdir()
        source = work / 'release'
        shutil.copytree(RELEASE, source)
        events = work / 'events'
        env = dict(os.environ, PATH=f'{commands}:/usr/sbin:/usr/bin:/sbin:/bin',
                   FIXTURE_RELEASE=str(source), FIXTURE_EVENTS=str(events), FIXTURE_VERSION=version)
        # Only transport is replaced on the successful path; apt-get/dpkg and CLI are real.
        curl = commands / 'curl'
        curl.write_text('''#!/usr/bin/python3
import json, os, pathlib, shutil, sys
a=sys.argv[1:]
with open(os.environ['FIXTURE_EVENTS'],'a') as f: f.write(json.dumps(a)+'\\n')
assert a[a.index('--proto')+1] == '=https'
assert a[a.index('--proto-redir')+1] == '=https'
base='https://github.com/ninex98/webpatch/releases/'
version=os.environ['FIXTURE_VERSION']
if os.environ.get('FAIL_DOWNLOAD'): sys.exit(22)
if a[-1] == base+'latest':
    print(os.environ.get('LATEST_URL',base+'tag/v'+version),end='')
else:
    assert a[-1].startswith(base+'download/v'+version+'/'), a[-1]
    shutil.copyfile(pathlib.Path(os.environ['FIXTURE_RELEASE'])/a[-1].rsplit('/',1)[1],a[a.index('--output')+1])
''')
        curl.chmod(0o755)

        def invoke(label, arguments=(), additions=None, success=False, contains=None):
            before = Path('/var/lib/dpkg/status').read_bytes()
            result = run(['sh', str(ROOT / 'install.sh'), *arguments], cwd='/', env=env | (additions or {}))
            if success:
                assert result.returncode == 0, (label, result.stdout, result.stderr)
            else:
                assert result.returncode != 0, (label, result.stdout)
                assert before == Path('/var/lib/dpkg/status').read_bytes(), label
            if contains:
                assert contains in result.stdout + result.stderr, (label, result.stdout, result.stderr)
            checks.append({'case': label, 'status': 'PASS', 'exit_code': result.returncode})

        invoke('invalid-version', ['--version', '../0.1.0'], contains='Version must')
        invoke('missing-version', ['--version'], contains='requires a value')
        invoke('unknown-option', ['--yes'], contains='Unknown option')
        uname = commands / 'uname'
        uname.write_text('#!/bin/sh\nprintf "Darwin\\n"\n'); uname.chmod(0o755)
        invoke('unsupported-os', contains='Unsupported OS')
        uname.unlink()
        sed = commands / 'sed'
        sed.write_text('#!/bin/sh\nprintf "unsupported\\n"\n'); sed.chmod(0o755)
        invoke('unsupported-distribution', contains='Unsupported distribution')
        sed.unlink()
        invoke('latest-download-failed', additions={'FAIL_DOWNLOAD': '1'}, contains='Cannot resolve')
        invoke('unexpected-latest-url', additions={'LATEST_URL': 'https://example.invalid/v0.1.0'}, contains='Unexpected latest')
        invoke('package-download-failed', ['--version', version], {'FAIL_DOWNLOAD': '1'}, contains='Package download failed')
        sums = source / 'SHA256SUMS'
        original = sums.read_bytes()
        sums.write_text('')
        invoke('missing-checksum', ['--version', version], contains='Missing or duplicate')
        sums.write_bytes(original + original)
        invoke('duplicate-checksum', ['--version', version], contains='Missing or duplicate')
        sums.write_text(f'not-a-hash  {asset}\n')
        invoke('malformed-checksum', ['--version', version], contains='Invalid SHA256')
        sums.write_bytes(original)
        package = source / asset
        package.write_bytes(package.read_bytes() + b'corruption')
        invoke('corrupted-package', ['--version', version], contains='Checksum mismatch')
        shutil.copyfile(RELEASE / asset, package)

        # A valid digest alone must not admit the wrong package/version/architecture.
        for field, value in [('Package', 'other'), ('Version', '99.0.0'), ('Architecture', 'amd64')]:
            stage = work / field
            run(['dpkg-deb', '--raw-extract', str(RELEASE / asset), str(stage)], check=True)
            control = stage / 'DEBIAN/control'
            control.write_text('\n'.join(f'{field}: {value}' if line.startswith(field+':') else line
                                         for line in control.read_text().splitlines()) + '\n')
            run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(package)], check=True)
            sums.write_text(f'{hashlib.sha256(package.read_bytes()).hexdigest()}  {asset}\n')
            invoke('wrong-'+field.lower(), ['--version', version], contains='Unexpected package')
        shutil.copyfile(RELEASE / asset, package)
        sums.write_bytes(original)
        apt = commands / 'apt-get'
        apt.write_text('#!/bin/sh\nexit 42\n'); apt.chmod(0o755)
        invoke('apt-failure-reported', ['--version', version], contains='APT installation failed')
        apt.unlink()
        invoke('install-latest', success=True, contains=f'Installed WebPatch {version}')
        invoke('reinstall-pinned', ['--version', version], success=True)
        old = work / 'old'
        run(['dpkg-deb', '--raw-extract', str(RELEASE / asset), str(old)], check=True)
        control = old / 'DEBIAN/control'
        control.write_text(control.read_text().replace('Version: '+version, 'Version: 0.0.0'))
        init = old / 'usr/lib/webpatch/webpatch/__init__.py'
        init.write_text(init.read_text().replace(f'"{version}"', '"0.0.0"'))
        old_package = work / 'old.deb'
        run(['dpkg-deb', '--root-owner-group', '--build', str(old), str(old_package)], check=True)
        run(['dpkg', '--install', str(old_package)], check=True)
        assert run(['/usr/bin/webpatch', '--version'], check=True).stdout.strip() == '0.0.0'
        invoke('upgrade-from-older-version', ['--version', version], success=True)
        # Downgrade refusal must happen before any package download.
        events.write_text('')
        invoke('downgrade-refused', ['--version', '0.0.0'], contains='Refusing downgrade')
        assert not events.read_text(), 'Downgrade fetched an asset'
        assert run(['/usr/bin/webpatch', '--version'], cwd='/', check=True).stdout.strip() == version
        before = Path('/var/lib/dpkg/status').read_bytes()
        scan = run(['/usr/bin/webpatch', 'scan', '--format', 'json'], cwd='/')
        assert scan.returncode in {1, 2}, scan.stderr
        report = json.loads(scan.stdout)
        assert report['safe'] is False and report['overall'] == 'UNKNOWN'
        assert report['inventory']['scan_scope']['completeness'] == 'UNKNOWN'
        assert before == Path('/var/lib/dpkg/status').read_bytes()
        assert not report['inventory']['packages'], 'Fixture intentionally has no PHP'
        checks.append({'case': 'installed-read-only-empty-inventory-stays-unknown', 'status': 'PASS', 'exit_code': scan.returncode})
    print(json.dumps({'result': 'PASS', 'environment': Path('/etc/os-release').read_text(),
                      'architecture': run(['dpkg', '--print-architecture'], check=True).stdout.strip(),
                      'version': version, 'package_sha256': hashlib.sha256((RELEASE/asset).read_bytes()).hexdigest(),
                      'checks': checks, 'live_github_release_download': 'NOT_RUN'}, indent=2))


if __name__ == '__main__':
    main()
