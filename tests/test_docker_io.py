import json
import socketserver
import threading
import tempfile
from http.server import BaseHTTPRequestHandler

import pytest

from webpatch.docker_io import LIST_PATH, TOP_QUERY, LocalDockerReader, local_endpoint
from webpatch.system import ProbeError
from test_docker_scan import ID, STATUS, tar_bytes


@pytest.fixture
def daemon(tmp_path):
    replies = {}
    calls = []
    lengths = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.command, self.path))
            code, body = replies[self.path]
            self.send_response(code)
            self.send_header('Content-Length', str(lengths.get(self.path, len(body))))
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self):
            calls.append((self.command, self.path))
            self.send_response(replies[self.path][0]); self.end_headers()

        def log_message(self, *args):
            pass

    temporary = tempfile.TemporaryDirectory(prefix='wp-docker-', dir='/tmp')
    path = temporary.name + '/docker.sock'
    server = socketserver.UnixStreamServer(path, Handler)
    replies['advertised_lengths'] = lengths
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    try:
        yield LocalDockerReader(path), replies, calls
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
        temporary.cleanup()


def test_real_unix_transport_reads_list_tar_top_and_head_only(daemon):
    reader, replies, calls = daemon
    replies[LIST_PATH] = (200, json.dumps([dict(Id=ID, Names=['/app'], Image='php', ImageID='sha256:x',
                                             State='running', Command='secret', Labels={'key': 'secret'})]).encode())
    path = '/containers/' + ID + '/archive?path=%2Fvar%2Flib%2Fdpkg%2Fstatus'
    replies[path] = (200, tar_bytes(content=STATUS.encode()))
    replies['/containers/' + ID + TOP_QUERY] = (200, b'{"Titles":["PID","COMMAND"],"Processes":[["123","php-fpm"]]}')
    hint = '/containers/' + ID + '/archive?path=%2Fusr%2Flocal%2Fbin%2Fphp'
    replies[hint] = (200, b'')
    assert reader.containers()[0]['id'] == ID
    assert reader.read_file((ID, '/var/lib/dpkg/status')) == STATUS
    assert reader.processes(ID) == ['php-fpm']
    assert reader.path_exists((ID, '/usr/local/bin/php'))
    assert all(method in {'GET', 'HEAD'} for method, _ in calls)


@pytest.mark.parametrize('code,body,reason', [(403, b'secret', 'PERMISSION_DENIED'),
    (500, b'secret', 'HTTP_500'), (200, b'{', 'INVALID_JSON'), (404, b'secret', 'MISSING')])
def test_http_failures_are_explicit_and_never_leak_bodies(daemon, code, body, reason):
    reader, replies, _ = daemon; replies[LIST_PATH] = (code, body)
    with pytest.raises(ProbeError, match=reason) as failure:
        reader.containers()
    assert 'secret' not in str(failure.value)


def test_response_limit_and_deadline(daemon, monkeypatch):
    reader, replies, _ = daemon; replies[LIST_PATH] = (200, b' ' * 100)
    monkeypatch.setattr('webpatch.docker_io.MAX_JSON', 32)
    with pytest.raises(ProbeError, match='TOO_LARGE'):
        reader.containers()
    reader.deadline = 0
    with pytest.raises(ProbeError, match='TIME_LIMIT'):
        reader.containers()


def test_missing_file_is_distinct_from_denial(daemon):
    reader, replies, _ = daemon
    path = '/containers/' + ID + '/archive?path=%2Fvar%2Flib%2Fdpkg%2Fstatus'
    replies[path] = (404, b'')
    assert reader.read_file((ID, '/var/lib/dpkg/status')) is None


def test_truncated_http_body_cannot_be_accepted_as_valid_metadata(daemon):
    reader, replies, _ = daemon
    replies[LIST_PATH] = (200, b'[]')
    replies['advertised_lengths'][LIST_PATH] = 100
    with pytest.raises(ProbeError, match='TRUNCATED'):
        reader.containers()


def test_connection_failure_is_explicit(tmp_path):
    with pytest.raises(ProbeError, match='CONNECTION_FAILED'):
        LocalDockerReader(str(tmp_path / 'missing.sock')).containers()


def test_local_discovery_does_not_use_remote_environment(monkeypatch):
    monkeypatch.setenv('DOCKER_HOST', 'tcp://remote.example:2375')
    monkeypatch.setenv('DOCKER_CONTEXT', 'remote')
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/fixture/runtime')
    seen = []
    def missing(path):
        seen.append(path)
        raise FileNotFoundError()
    monkeypatch.setattr('webpatch.docker_io.os.stat', missing)
    assert local_endpoint() is None
    assert all(path.startswith('/') for path in seen)
    assert '/fixture/runtime/docker.sock' in seen


@pytest.mark.parametrize('path', ['tcp://localhost:2375', 'ssh://server', 'relative.sock', '/bad\x00socket'])
def test_explicit_endpoint_requires_local_absolute_path(path):
    with pytest.raises(ValueError):
        LocalDockerReader(path)
