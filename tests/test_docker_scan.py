from dataclasses import asdict
import io
import json
import tarfile

import pytest

from conftest import FakeSystem, NOW
from webpatch.cli import main
from webpatch.docker_io import (FILES, HINT_PATHS, LIST_PATH, TOP_QUERY, LocalDockerReader,
                               file_from_tar, parse_containers, validate_request)
from webpatch.docker_scan import attach_docker, scan_docker
from webpatch.service import scan
from webpatch.system import ProbeError
from webpatch.terminal import Terminal, render_scan, width

ID = 'a' * 64
SECOND = 'b' * 64
ROW = dict(id=ID, name='app', image='private/php:latest', image_id='sha256:' + 'c' * 64, state='running')
OS = 'ID=ubuntu\nVERSION_ID="22.04"\nVERSION_CODENAME=jammy\n'
STATUS = ('Package: php8.1-fpm\nStatus: install ok installed\nArchitecture: amd64\n'
          'Source: php8.1\nVersion: 8.1.2-1ubuntu2.27\n\n')


class DockerFixture:
    endpoint = '/fixture/docker.sock'

    def __init__(self, rows=None):
        self.rows = [dict(ROW)] if rows is None else rows
        self.after = self.rows
        self.calls = []
        self.files = {}
        self.paths = {}
        self.top = {}
        self.list_error = None
        for row in self.rows:
            ident = row['id']
            self.files.update({(ident, p): None for p in FILES})
            self.files[(ident, '/etc/os-release')] = OS
            self.files[(ident, '/var/lib/dpkg/status')] = STATUS
            self.paths.update({(ident, p): False for p in HINT_PATHS})
            self.top[ident] = ['php-fpm8.1']

    def containers(self, target):
        self.calls.append(('containers', target))
        if self.list_error:
            raise ProbeError(self.list_error)
        return self.rows if sum(op == 'containers' for op, _ in self.calls) == 1 else self.after

    def _get(self, op, mapping, key):
        self.calls.append((op, key))
        value = mapping[key]  # undeclared I/O is an error, never host fallback
        if isinstance(value, Exception):
            raise value
        return value

    def read_file(self, target):
        return self._get('read_file', self.files, target)

    def path_exists(self, target):
        return self._get('path_exists', self.paths, target)

    def processes(self, target):
        return self._get('processes', self.top, target)


def test_host_empty_and_affected_container_are_separate_and_exit_one(capsys):
    fake = FakeSystem({})
    code = main(['scan', '--format', 'json'], system=fake, docker_reader=DockerFixture(), now=NOW)
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report['overall'] == 'POTENTIALLY_AFFECTED'
    assert report['inventory']['packages'] == [] and report['assessments'] == []
    item = report['docker']['containers'][0]
    assert item['assessments'][0]['version_status'] == 'BELOW_VENDOR_FIX'
    assert not item['safe'] and not report['safe']
    assert item['environment']['scope'] == 'container'
    assert item['environment']['scope_sha256'] != report['inventory']['environment']['scope_sha256']


def test_custom_official_style_php_header_never_proves_version_or_safety():
    reader = DockerFixture()
    reader.files[(ID, '/var/lib/dpkg/status')] = ''
    reader.files[(ID, '/usr/local/include/php/main/php_version.h')] = '#define PHP_VERSION "8.3.99"\n'
    reader.paths[(ID, '/usr/local/sbin/php-fpm')] = True
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    item = result.containers[0]
    assert '8.3.99' in ' '.join(item.hints)
    assert not item.packages and not item.assessments
    assert item.overall == 'UNKNOWN' and not item.safe
    assert 'CONTAINER_CUSTOM_PHP_VERSION_UNVERIFIED' in item.gaps


def test_multiple_stopped_empty_and_denied_containers_remain_visible():
    reader = DockerFixture([dict(ROW), dict(ROW, id=SECOND, name='stopped', state='exited')])
    reader.files[(ID, '/var/lib/dpkg/status')] = ProbeError('DOCKER_PERMISSION_DENIED')
    reader.top[ID] = ProbeError('DOCKER_HTTP_409')
    reader.files[(SECOND, '/var/lib/dpkg/status')] = ''
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    assert len(result.containers) == 2
    assert all(c.overall == 'UNKNOWN' for c in result.containers)
    assert 'CONTAINER_PROCESSES_UNREADABLE' in result.containers[0].gaps
    assert 'CONTAINER_NOT_RUNNING' in result.containers[1].gaps
    assert 'CONTAINER_NO_PHP_OBSERVED_NOT_PROOF_OF_ABSENCE' in result.containers[1].gaps
    assert ('processes', SECOND) not in reader.calls


@pytest.mark.parametrize('failure', ['DOCKER_PERMISSION_DENIED', 'DOCKER_CONNECTION_FAILED', 'DOCKER_TIMEOUT'])
def test_daemon_failure_is_not_empty_success(failure):
    reader = DockerFixture(); reader.list_error = failure
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    assert result.status == 'UNKNOWN' and failure in result.gaps
    assert result.evidence[0].outcome == failure


def test_empty_daemon_and_drift_are_distinct():
    empty = scan_docker(DockerFixture([]), FakeSystem({}), now=NOW)
    assert empty.status == 'OBSERVED' and empty.listed_count == 0 and not empty.safe
    reader = DockerFixture(); reader.after = []
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    assert result.status == 'PARTIAL'
    assert 'CONTAINER_CHANGED_OR_DISAPPEARED' in result.containers[0].gaps


def test_container_limit_is_explicit(monkeypatch):
    monkeypatch.setattr('webpatch.docker_scan.MAX_CONTAINERS', 1)
    reader = DockerFixture([dict(ROW), dict(ROW, id=SECOND)])
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    assert result.status == 'PARTIAL' and result.listed_count == 2 and len(result.containers) == 1
    assert not any(isinstance(target, tuple) and target[0] == SECOND for _, target in reader.calls)


def test_expiry_and_unknown_vendor_keep_container_assessments_unknown():
    result = scan_docker(DockerFixture(), FakeSystem({}), now=NOW.replace(year=2027))
    assert result.containers[0].overall == 'UNKNOWN'
    assert all(a.version_status == 'UNKNOWN' for a in result.containers[0].assessments)
    reader = DockerFixture(); reader.files[(ID, '/etc/os-release')] = 'ID=alpine\nVERSION_ID=3.22\n'
    reader.files[(ID, '/lib/apk/db/installed')] = 'P:php83-fpm\nV:8.3.20-r1\n'
    item = scan_docker(reader, FakeSystem({}), now=NOW).containers[0]
    assert item.overall == 'UNKNOWN' and 'CONTAINER_APK_RULES_UNSUPPORTED' in item.gaps
    assert 'apk: php83-fpm 8.3.20-r1' in item.hints


def test_malformed_package_metadata_does_not_abort_other_containers():
    reader = DockerFixture([dict(ROW), dict(ROW, id=SECOND)])
    reader.files[(ID, '/var/lib/dpkg/status')] = STATUS + 'Package: php8.1-fpm\nPackage: duplicate\n'
    result = scan_docker(reader, FakeSystem({}), now=NOW)
    assert result.containers[0].overall == 'UNKNOWN'
    assert result.containers[1].overall == 'POTENTIALLY_AFFECTED'


@pytest.mark.parametrize('mode,container', [('off', False), ('auto', True)])
def test_opt_out_and_container_scope_never_access_docker(mode, container):
    reader = DockerFixture(); system = FakeSystem({'docker': container})
    result = attach_docker(scan(system, now=NOW), system, reader=reader, mode=mode, now=NOW)
    assert result.docker.status == 'NOT_CHECKED' and not reader.calls


def test_injected_system_never_discovers_native_socket(monkeypatch):
    monkeypatch.setattr('webpatch.docker_scan.local_endpoint', lambda *a: pytest.fail('host fallback'))
    system = FakeSystem({}); report = scan(system, now=NOW)
    assert attach_docker(report, system) is report


@pytest.mark.parametrize('method,path', [('POST', '/containers/create'), ('GET', '/containers/' + ID + '/json'),
    ('GET', '/images/json'), ('POST', '/containers/' + ID + '/exec'),
    ('GET', '/containers/' + ID + '/archive?path=%2Fetc%2Fshadow'), ('PUT', LIST_PATH)])
def test_read_boundary_rejects_mutations_secrets_and_unapproved_endpoints(method, path):
    with pytest.raises(ProbeError, match='NOT_ALLOWED'):
        validate_request(method, path)


def tar_bytes(name='status', kind=tarfile.REGTYPE, content=b'data', duplicate=False):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(name); item.type = kind
        item.size = len(content) if kind == tarfile.REGTYPE else 0
        item.linkname = '/etc/shadow' if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ''
        archive.addfile(item, io.BytesIO(content))
        if duplicate:
            archive.addfile(item, io.BytesIO(content))
    return stream.getvalue()


@pytest.mark.parametrize('options', [{'name': '../status'}, {'kind': tarfile.SYMTYPE}, {'kind': tarfile.LNKTYPE},
                                      {'kind': tarfile.DIRTYPE}, {'duplicate': True}, {'content': b'\xff'}])
def test_tar_never_follows_links_extracts_paths_or_accepts_ambiguous_files(options):
    with pytest.raises(ProbeError):
        file_from_tar(tar_bytes(**options), '/var/lib/dpkg/status')


def test_tar_reads_regular_file_only():
    assert file_from_tar(tar_bytes(content=STATUS.encode()), '/var/lib/dpkg/status') == STATUS


def test_container_list_discards_commands_labels_and_rejects_bad_identity():
    row = dict(Id=ID, Names=['/web'], Image='php:test', ImageID='sha256:xyz', State='running',
               Command='SECRET', Labels={'secret': 'SECRET'})
    parsed = parse_containers([row])
    assert 'SECRET' not in json.dumps(parsed)
    for value in ([row, row], [dict(row, Id='../escape')], [dict(row, Names='not-a-list')], {'bad': 1}):
        with pytest.raises(ProbeError):
            parse_containers(value)


@pytest.mark.parametrize('lang', ['zh', 'en'])
@pytest.mark.parametrize('columns', [42, 100])
def test_container_output_is_actionable_and_escapes_controls(lang, columns):
    reader = DockerFixture(); reader.rows[0]['name'] = 'app\x1b[31m\u202e'
    system = FakeSystem({})
    report = attach_docker(scan(system, now=NOW), system, reader=reader, now=NOW)
    stream = io.StringIO(); render_scan(report, Terminal(stream=stream, lang=lang, columns=columns))
    text = stream.getvalue()
    assert '\x1b' not in text and '\u202e' not in text
    assert all(width(line) <= columns for line in text.splitlines())
    assert ('容器' if lang == 'zh' else 'containers') in text
    assert 'sudo webpatch fix' not in text
    assert ('重建' if lang == 'zh' else 'rebuild') in text


def test_default_cli_automatically_connects_local_docker(monkeypatch, capsys):
    reader = DockerFixture()
    monkeypatch.setattr('webpatch.cli.LocalSystem', lambda: FakeSystem({}))
    monkeypatch.setattr('webpatch.docker_scan.local_endpoint', lambda explicit: '/fixture/auto.sock')
    monkeypatch.setattr('webpatch.docker_scan.LocalDockerReader', lambda endpoint: reader)
    assert main(['scan', '--format', 'json'], now=NOW) == 1
    assert json.loads(capsys.readouterr().out)['docker']['listed_count'] == 1
    assert reader.calls


def test_no_socket_and_discovery_failure_have_distinct_results(monkeypatch):
    system = FakeSystem({}); report = scan(system, now=NOW)
    monkeypatch.setattr('webpatch.docker_scan.local_endpoint', lambda explicit: None)
    assert attach_docker(report, system, native=True, now=NOW).docker.status == 'NOT_DETECTED'
    def failed(explicit):
        raise ProbeError('DOCKER_SOCKET_DISCOVERY_FAILED')
    monkeypatch.setattr('webpatch.docker_scan.local_endpoint', failed)
    result = attach_docker(report, system, native=True, now=NOW)
    assert result.docker.status == 'UNKNOWN'
    assert result.docker.gaps == ['DOCKER_SOCKET_DISCOVERY_FAILED']


def test_container_evidence_does_not_authorize_host_plan():
    from webpatch.planning import plan
    system = FakeSystem({})
    report = attach_docker(scan(system, now=NOW), system, reader=DockerFixture(), now=NOW)
    proposal = plan(report, system=system, now=NOW)
    assert proposal.status == 'BLOCKED' and not proposal.executable
    assert not proposal.actions


def test_os_symlink_falls_back_to_regular_metadata_with_evidence_retained():
    reader = DockerFixture()
    reader.files[(ID, '/etc/os-release')] = ProbeError('DOCKER_FILE_NOT_REGULAR_OR_TOO_LARGE')
    reader.files[(ID, '/usr/lib/os-release')] = OS
    item = scan_docker(reader, FakeSystem({}), now=NOW).containers[0]
    assert item.environment.os_id == 'ubuntu'
    assert 'CONTAINER_FILE_READ_FAILED:/etc/os-release' not in item.gaps
    assert any(e.outcome == 'DOCKER_FILE_NOT_REGULAR_OR_TOO_LARGE' for e in item.evidence)
