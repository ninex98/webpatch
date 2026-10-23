"""Native acceptance on disposable containers only, without host filesystem/socket mounts.

Run from the project venv. Native Docker API tests use only IDs created here;
version comparisons execute dpkg in our disposable Debian/Ubuntu container.
No product code executes a container command. No host package changes.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src'),
               str(Path(__file__).resolve().parents[1] / 'tests')]
from conftest import FakeSystem, NOW
from webpatch.cli import main
from webpatch.docker_io import LocalDockerReader
from webpatch.system import CommandResult


def command(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True, timeout=90)


def snapshot(ident):
    template = '{{json .State}}|{{.RestartCount}}|{{.Image}}|{{.HostConfig.ReadonlyRootfs}}'
    return {'state': command('docker', 'inspect', '--format', template, ident).stdout,
            'diff': command('docker', 'diff', ident).stdout}


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package-image', required=True)
    parser.add_argument('--custom-image', required=True)
    parser.add_argument('--empty-image', required=True)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output); destination.mkdir(parents=True, exist_ok=True)
    containers = []
    label = 'webpatch-docker-check-' + uuid.uuid4().hex[:10]
    try:
        for suffix, image, running in [('packages', args.package_image, True),
                                       ('custom', args.custom_image, True),
                                       ('empty', args.empty_image, True),
                                       ('stopped', args.custom_image, False)]:
            entrypoint, arguments = (('/usr/local/sbin/php-fpm', ['-F']) if suffix == 'custom'
                                     else ('/bin/sleep', ['600']))
            ident = command('docker', 'create', '--name', label + '-' + suffix,
                '--label', 'webpatch.disposable=' + label, '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--entrypoint', entrypoint, image, *arguments).stdout.strip()
            containers.append(ident)
            if running:
                command('docker', 'start', ident)
        before = {ident: snapshot(ident) for ident in containers}

        class TestReader(LocalDockerReader):
            def containers(self, target=''):
                return [r for r in super().containers(target) if r['id'] in containers]

        class TestSystem(FakeSystem):
            def run(self, argv):
                if argv[:2] == ('/usr/bin/dpkg', '--compare-versions'):
                    result = command('docker', 'exec', containers[0], *argv, check=False)
                    return CommandResult(result.returncode, result.stdout, result.stderr)
                return super().run(argv)

        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(['scan', '--format', 'json'], system=TestSystem({}),
                        docker_reader=TestReader(args.socket), now=NOW)
        report = json.loads(stream.getvalue())
        (destination / 'native-report.json').write_text(stream.getvalue())
        assert code in {1, 2} and not report['safe']
        docker = report['docker']
        assert docker['status'] == 'OBSERVED', docker['gaps']
        assert docker['listed_count'] == 4
        items = {c['id']: c for c in docker['containers']}
        package_item, custom, empty, stopped = [items[i] for i in containers]
        assert package_item['packages'] and package_item['assessments']
        assert any(a['version_status'] in {'MEETS_VENDOR_FIX', 'BELOW_VENDOR_FIX'} for a in package_item['assessments'])
        assert any('/usr/local/' in h for h in custom['hints']), custom
        assert any('php_version.h:' in h for h in custom['hints']), custom
        assert any(h.startswith('process: php-fpm') for h in custom['hints']), custom
        assert custom['overall'] == 'UNKNOWN'
        assert not empty['packages'] and not empty['hints'] and empty['overall'] == 'UNKNOWN'
        assert 'CONTAINER_NOT_RUNNING' in stopped['gaps']
        assert not any(g.startswith(('CONTAINER_FILE_READ_FAILED', 'CONTAINER_PROCESSES_UNREADABLE'))
                       for item in items.values() for g in item['gaps']), [i['gaps'] for i in items.values()]
        after = {ident: snapshot(ident) for ident in containers}
        assert before == after, 'container state or filesystem changed'
        stream = io.StringIO()
        with redirect_stdout(stream):
            main(['scan', '--lang', 'zh'], system=TestSystem({}),
                 docker_reader=TestReader(args.socket), now=NOW)
        (destination / 'native-zh.txt').write_text(stream.getvalue())
        assert before == {ident: snapshot(ident) for ident in containers}
        environment = {
            'status': 'PASS', 'date_policy': 'Frozen rule evaluation at ' + NOW.isoformat(),
            'docker_server': command('docker', 'version', '--format', '{{.Server.Version}}').stdout.strip(),
            'images': {image: command('docker', 'image', 'inspect', '--format', '{{.Id}}', image).stdout.strip()
                       for image in (args.package_image, args.custom_image, args.empty_image)},
            'container_ids': containers, 'before': before, 'after': after,
            'checks': ['four independent container inventories', 'native dpkg comparisons',
                       'official PHP custom header', 'stopped and non-PHP containers',
                       'unchanged container state and filesystem', 'Chinese CLI rendering'],
        }
        (destination / 'native-result.json').write_text(json.dumps(environment, indent=2) + '\n')
        print(json.dumps({'status': 'PASS', 'containers': 4, 'output': str(destination)}))
    finally:
        for ident in containers:
            command('docker', 'rm', '-f', ident, check=False)


if __name__ == '__main__':
    run()
