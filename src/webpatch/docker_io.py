"""Injectable local Docker reads. No exec, writes, remote contexts or CLI plugins."""
import http.client
import io
import json
import os
import re
import socket
import stat
import tarfile
import time
from typing import Protocol
from urllib.parse import quote

from .system import ProbeError

MAX_CONTAINERS = 64
MAX_JSON = 4 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
FILES = ('/etc/os-release', '/usr/lib/os-release', '/var/lib/dpkg/status',
         '/lib/apk/db/installed', '/usr/local/include/php/main/php_version.h')
HINT_PATHS = ('/usr/local/bin/php', '/usr/local/sbin/php-fpm', '/www/server/php', '/opt/php')
CONTAINER_ID = re.compile(r'[a-f0-9]{64}\Z')
LIST_PATH = '/containers/json?all=1'
TOP_QUERY = '/top?ps_args=-eo%20pid%2Ccomm'


class DockerReader(Protocol):
    endpoint: str
    def containers(self, target="") -> list[dict]: ...
    def read_file(self, target: tuple[str, str]) -> str | None: ...
    def path_exists(self, target: tuple[str, str]) -> bool: ...
    def processes(self, container_id: str) -> list[str]: ...


def check_id(value):
    if not isinstance(value, str) or not CONTAINER_ID.fullmatch(value):
        raise ProbeError('DOCKER_INVALID_CONTAINER_ID')


def archive_path(target, allowed):
    container_id, path = target
    check_id(container_id)
    if path not in allowed:
        raise ProbeError('DOCKER_PATH_NOT_ALLOWED')
    return '/containers/' + container_id + '/archive?path=' + quote(path, safe='')


def validate_request(method, path):
    if method == 'GET' and path == LIST_PATH:
        return
    prefix = r'/containers/[a-f0-9]{64}'
    if method == 'GET' and re.fullmatch(prefix + re.escape(TOP_QUERY), path):
        return
    allowed = FILES if method == 'GET' else HINT_PATHS if method == 'HEAD' else ()
    if any(re.fullmatch(prefix + re.escape('/archive?path=' + quote(p, safe='')), path) for p in allowed):
        return
    raise ProbeError('DOCKER_REQUEST_NOT_ALLOWED')


def parse_containers(raw):
    if not isinstance(raw, list) or len(raw) > 4096:
        raise ProbeError('DOCKER_INVALID_CONTAINER_LIST')
    result, seen = [], set()
    for row in raw:
        if not isinstance(row, dict):
            raise ProbeError('DOCKER_INVALID_CONTAINER_LIST')
        ident = row.get('Id'); check_id(ident)
        names = row.get('Names')
        if (ident in seen or not isinstance(names, list) or not names
                or any(not isinstance(n, str) or len(n) > 256 for n in names)
                or any(not isinstance(row.get(k), str) or len(row[k]) > 1024
                       for k in ('Image', 'ImageID', 'State'))):
            raise ProbeError('DOCKER_INVALID_CONTAINER_LIST')
        seen.add(ident)
        # Discard command, labels and other fields. Never retain environment or inspect JSON.
        result.append({'id': ident, 'name': sorted(names)[0].lstrip('/'),
                       'image': row['Image'], 'image_id': row['ImageID'], 'state': row['State']})
    return sorted(result, key=lambda r: r['id'])


def file_from_tar(data, path):
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            member = archive.next()
            if (member is None or member.name != path.rsplit('/', 1)[1]
                    or not member.isfile() or member.issparse()
                    or not 0 <= member.size <= MAX_FILE):
                raise ProbeError('DOCKER_FILE_NOT_REGULAR_OR_TOO_LARGE')
            stream = archive.extractfile(member)
            if stream is None:
                raise ProbeError('DOCKER_FILE_UNREADABLE')
            raw = stream.read(MAX_FILE + 1)
            if len(raw) != member.size or archive.next() is not None:
                raise ProbeError('DOCKER_ARCHIVE_AMBIGUOUS')
            return raw.decode('utf-8', 'strict')
    except (tarfile.TarError, UnicodeError, ValueError, EOFError) as exc:
        raise ProbeError('DOCKER_ARCHIVE_INVALID') from exc


class LocalDockerReader:
    def __init__(self, endpoint):
        if not isinstance(endpoint, str) or not endpoint.startswith('/') or '\x00' in endpoint:
            raise ValueError('DOCKER_LOCAL_SOCKET_REQUIRED')
        if not hasattr(socket, 'AF_UNIX'):
            raise ProbeError('DOCKER_UNIX_SOCKET_UNSUPPORTED')
        self.endpoint = endpoint
        self.deadline = time.monotonic() + 45

    def _request(self, method, path, limit):
        validate_request(method, path)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError('DOCKER_SCAN_TIME_LIMIT')
        connection = http.client.HTTPConnection('localhost', timeout=min(3, remaining))
        channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            channel.settimeout(min(3, remaining))
            channel.connect(self.endpoint)
            connection.sock = channel
            connection.request(method, path, headers={'Host': 'localhost', 'Connection': 'close'})
            response = connection.getresponse()
            if response.status in (403, 401):
                raise ProbeError('DOCKER_PERMISSION_DENIED')
            if response.status == 404:
                return None
            if response.status != 200:
                raise ProbeError('DOCKER_HTTP_' + str(response.status))
            result = bytearray()
            while method != 'HEAD':
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeError('DOCKER_SCAN_TIME_LIMIT')
                channel.settimeout(min(3, remaining))
                chunk = response.read1(min(65536, limit + 1 - len(result)))
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > limit:
                    raise ProbeError('DOCKER_RESPONSE_TOO_LARGE')
            if method != 'HEAD' and response.length not in (None, 0):
                raise ProbeError('DOCKER_RESPONSE_TRUNCATED')
            return bytes(result)
        except PermissionError as exc:
            raise ProbeError('DOCKER_PERMISSION_DENIED') from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProbeError('DOCKER_TIMEOUT') from exc
        except (OSError, http.client.HTTPException) as exc:
            raise ProbeError('DOCKER_CONNECTION_FAILED') from exc
        finally:
            connection.close()
            channel.close()

    def _json(self, path):
        raw = self._request('GET', path, MAX_JSON)
        if raw is None:
            raise ProbeError('DOCKER_ENDPOINT_OR_CONTAINER_MISSING')
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ProbeError('DOCKER_INVALID_JSON') from exc

    def containers(self, target=""):
        return parse_containers(self._json(LIST_PATH))

    def read_file(self, target):
        path = archive_path(target, FILES)
        raw = self._request('GET', path, MAX_FILE + 65536)
        return None if raw is None else file_from_tar(raw, target[1])

    def path_exists(self, target):
        return self._request('HEAD', archive_path(target, HINT_PATHS), 0) is not None

    def processes(self, container_id):
        check_id(container_id)
        raw = self._json('/containers/' + container_id + TOP_QUERY)
        if (not isinstance(raw, dict) or raw.get('Titles') != ['PID', 'COMMAND']
                or not isinstance(raw.get('Processes'), list) or len(raw['Processes']) > 4096):
            raise ProbeError('DOCKER_PROCESS_LIST_UNSUPPORTED')
        names = []
        for row in raw['Processes']:
            if (not isinstance(row, list) or len(row) != 2 or not all(isinstance(v, str) for v in row)
                    or not row[0].isdigit() or len(row[1]) > 256):
                raise ProbeError('DOCKER_PROCESS_LIST_INVALID')
            # Only process names; never command arguments or process environments.
            names.append(row[1])
        return names


def local_endpoint(explicit=None):
    """Check conventional sockets only; DOCKER_HOST/contexts never redirect a scan."""
    if explicit:
        return explicit
    if not hasattr(os, 'getuid') or not hasattr(socket, 'AF_UNIX'):
        return None
    candidates = ['/var/run/docker.sock', '/run/docker.sock', f'/run/user/{os.getuid()}/docker.sock']
    runtime = os.environ.get('XDG_RUNTIME_DIR', '')
    if runtime.startswith('/'):
        candidates.append(runtime.rstrip('/') + '/docker.sock')
    for path in dict.fromkeys(candidates):
        try:
            if stat.S_ISSOCK(os.stat(path).st_mode):
                return path
        except PermissionError:
            return path  # let the reader record denial instead of pretending absence
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProbeError('DOCKER_SOCKET_DISCOVERY_FAILED') from exc
    return None
