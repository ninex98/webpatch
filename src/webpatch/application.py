"""Explicit application probes with kernel-bound local process attribution.

Never imported or invoked by scan(). An HTTP body cannot authenticate a PID;
Linux SCM_CREDENTIALS from the matching one-time callback supplies that identity.
This proves a response from a process, not exhaustive routing or loaded file bytes.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import sys
import threading
import time
from typing import Protocol
from urllib.parse import urlsplit

from .coverage import runtime_id
from .gates import evidence_deadline
from .planning import check_bindings, stable_bindings, digest
from .system import Collector, ProbeError

MAX_RESPONSE = 65536
PROBE_SECONDS = 5


def probe_source():
    return files('webpatch').joinpath('data/application_probe.php').read_bytes()


def target_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in url):
        raise ValueError('PROBE_URL_INVALID')
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.port or not 1 <= parsed.port <= 65535
            or not re.fullmatch(r'/[A-Za-z0-9_./-]+\.php', parsed.path) or '..' in parsed.path.split('/')):
        raise ValueError('PROBE_REQUIRES_EXPLICIT_LOOPBACK_PHP_URL')
    return parsed.port, parsed.path


@dataclass(frozen=True)
class ProbeExchange:
    payload: bytes
    response: bytes
    peer_pid: int
    peer_uid: int
    peer_gid: int
    script_sha256: str


class ApplicationProbe(Protocol):
    def collect(self, url: str, script_path: str, challenge: str, scope: str) -> ProbeExchange: ...


def trusted_script(path):
    """Require the shipped collector at a root-controlled, non-symlink path.

    Its on-disk provenance does not by itself attest executing opcodes. The result
    therefore never upgrades loaded_configuration or full application coverage.
    """
    current = Path(path)
    if not current.is_absolute() or '..' in current.parts:
        raise ProbeError('PROBE_SCRIPT_PATH_INVALID')
    for item in (current, *current.parents):
        info = item.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise ProbeError('PROBE_SCRIPT_NOT_ROOT_CONTROLLED')
        if item != current and str(item).startswith('/var/www'):
            if any((item/name).exists() or (item/name).is_symlink() for name in ('.user.ini','.htaccess')):
                raise ProbeError('PROBE_DIRECTORY_OVERRIDES_UNSUPPORTED')
    if not current.is_file() or current.stat().st_size > MAX_RESPONSE:
        raise ProbeError('PROBE_SCRIPT_FILE_INVALID')
    with current.open('rb') as stream:
        data = stream.read(MAX_RESPONSE + 1)
    if data != probe_source():
        raise ProbeError('PROBE_SCRIPT_SOURCE_MISMATCH')
    return hashlib.sha256(data).hexdigest()


class LocalApplicationProbe:
    def collect(self, url, script_path, challenge, scope):
        if sys.platform != 'linux' or not hasattr(socket, 'SO_PASSCRED'):
            raise ProbeError('KERNEL_PEER_PROBE_UNSUPPORTED')
        port, path = target_url(url)
        try:
            before = trusted_script(script_path)
        except OSError as exc:
            raise ProbeError('PROBE_SCRIPT_UNREADABLE:' + type(exc).__name__) from exc
        # Abstract namespace works across systemd PrivateTmp without a target write.
        callback = 'webpatch-' + secrets.token_hex(24)
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            listener.settimeout(PROBE_SECONDS)
            listener.bind('\0' + callback)
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=PROBE_SECONDS)
            deadline = time.monotonic() + PROBE_SECONDS
            wire_socket = None
            def abort_http():
                active = wire_socket or connection.sock
                if active is not None:
                    try:
                        active.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
            timer = threading.Timer(PROBE_SECONDS, abort_http)
            timer.daemon = True
            timer.start()
            try:
                connection.request('GET', path, headers={'X-WebPatch-Challenge': challenge,
                    'X-WebPatch-Callback': callback, 'X-WebPatch-Scope': scope,
                    'Cache-Control': 'no-store', 'Connection': 'close'})
                wire_socket = connection.sock
                response = connection.getresponse()
                body = response.read(MAX_RESPONSE + 1)
                if response.status != 200 or response.getheader('Content-Type', '').split(';')[0] != 'application/json' or len(body) > MAX_RESPONSE:
                    raise ProbeError('PROBE_HTTP_RESPONSE_INVALID')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeError('PROBE_DEADLINE_EXCEEDED')
                listener.settimeout(remaining)
                data, ancillary, flags, _ = listener.recvmsg(MAX_RESPONSE, socket.CMSG_SPACE(struct.calcsize('3i')))
                if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                    raise ProbeError('PROBE_DATAGRAM_TRUNCATED')
                credentials = [struct.unpack('3i', value) for level, kind, value in ancillary
                               if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(value) == struct.calcsize('3i')]
                if len(credentials) != 1 or credentials[0][0] <= 0:
                    raise ProbeError('PROBE_KERNEL_CREDENTIALS_MISSING')
                if trusted_script(script_path) != before:
                    raise ProbeError('PROBE_SCRIPT_CHANGED')
                return ProbeExchange(data, body, *credentials[0], before)
            except (OSError, http.client.HTTPException) as exc:
                raise ProbeError('PROBE_TRANSPORT_FAILED:' + type(exc).__name__) from exc
            finally:
                timer.cancel()
                connection.close()


def validate_exchange(exchange, report, challenge, url, script_path, service):
    # The boundary object is produced only by an explicit capability, not loaded
    # from saved/untrusted JSON. Persisted probe receipts never authenticate peers.
    port, path = target_url(url)
    expected_source = hashlib.sha256(probe_source()).hexdigest()
    if exchange.script_sha256 != expected_source:
        raise ValueError('PROBE_SOURCE_IDENTITY_INVALID')
    if len(exchange.payload) > MAX_RESPONSE or len(exchange.response) > MAX_RESPONSE:
        raise ValueError('PROBE_RESPONSE_TOO_LARGE')
    payload, response = json.loads(exchange.payload), json.loads(exchange.response)
    if not isinstance(payload, dict) or set(payload) != {
        'protocol', 'challenge', 'scope', 'pid', 'sapi', 'script', 'source_sha256',
        'ini_file', 'ini_scanned', 'effective_ini_sha256', 'extensions_sha256', 'cached_script', 'request_path'}:
        raise ValueError('PROBE_PAYLOAD_INVALID')
    if payload['protocol'] != 1 or payload['challenge'] != challenge or payload['scope'] != report.inventory.environment.scope_sha256:
        raise ValueError('PROBE_CHALLENGE_OR_SCOPE_MISMATCH')
    if (not isinstance(response, dict) or set(response) != {'challenge', 'payload_sha256'}
            or response['challenge'] != challenge or response['payload_sha256'] != hashlib.sha256(exchange.payload).hexdigest()):
        raise ValueError('PROBE_HTTP_CALLBACK_MISMATCH')
    if (type(payload['pid']) is not int or payload['pid'] != exchange.peer_pid
            or payload['script'] != script_path or payload['source_sha256'] != expected_source
            or payload['request_path'] != path or payload['cached_script'] is not False):
        raise ValueError('PROBE_PROCESS_OR_SCRIPT_MISMATCH')
    runtime = next((r for r in report.inventory.runtimes if r.pid == exchange.peer_pid), None)
    if (runtime is None or runtime.association != 'VERIFIED_LOCAL_ASSOCIATION' or not runtime.start_ticks
            or runtime.service != service or runtime.sapi not in {'fpm', 'apache2'}):
        raise ValueError('PROBE_PEER_NOT_A_VERIFIED_SCOPED_RUNTIME')
    if payload['sapi'] != {'fpm': 'fpm-fcgi', 'apache2': 'apache2handler'}[runtime.sapi]:
        raise ValueError('PROBE_SAPI_MISMATCH')
    for key in ('effective_ini_sha256', 'extensions_sha256'):
        if not isinstance(payload[key], str) or not re.fullmatch('[a-f0-9]{64}', payload[key]):
            raise ValueError('PROBE_CONFIGURATION_DIGEST_INVALID')
    paths = [payload['ini_file']]
    if not isinstance(payload['ini_scanned'], list) or len(payload['ini_scanned']) > 256:
        raise ValueError('PROBE_CONFIGURATION_LIST_INVALID')
    paths += payload['ini_scanned']
    if not all(isinstance(p, str) and re.fullmatch(r'/etc/php/[0-9]+\.[0-9]+/(?:fpm|apache2)/(?:php.ini|conf.d/[A-Za-z0-9_.-]+\.ini)', p) for p in paths):
        raise ValueError('PROBE_CONFIGURATION_PATH_UNSUPPORTED')
    observed_paths = {e.target for e in report.evidence if e.operation == 'read_text' and e.outcome == 'OK'}
    if not set(paths) <= observed_paths:
        raise ValueError('PROBE_CONFIGURATION_INPUT_NOT_OBSERVED')
    return runtime, payload


def collect_application_evidence(report, *, system, probe, url, script_path, service, now=None, clock=None, validity_seconds=300):
    if type(validity_seconds) is not int or not 1 <= validity_seconds <= 1800:
        raise ValueError('PROBE_VALIDITY_OUTSIDE_CONTRACT')
    if clock is None:
        fixed_now = now
        clock = (lambda: fixed_now) if fixed_now is not None else (lambda: datetime.now(timezone.utc))
    now = clock()
    if not now.tzinfo:
        raise ValueError('TIMEZONE_REQUIRED')
    target_url(url)
    collector = Collector(system, evidence_prefix='a')
    challenge = secrets.token_hex(32)
    blockers, runtime, payload = [], None, None
    try:
        if not report.inventory.environment.scope_sha256 or not datetime.fromisoformat(report.observed_at) <= now < evidence_deadline(report, now):
            raise ValueError('PROBE_SCOPE_OR_SCAN_VALIDITY_UNKNOWN')
        bindings = stable_bindings(report)
        if not check_bindings(collector, bindings, report):
            raise ValueError('PROBE_STATE_DRIFT_BEFORE_REQUEST')
        exchange = probe.collect(url, script_path, challenge, report.inventory.environment.scope_sha256)
        runtime, payload = validate_exchange(exchange, report, challenge, url, script_path, service)
        if not check_bindings(collector, bindings, report):
            raise ValueError('PROBE_STATE_DRIFT_AFTER_REQUEST')
        if not now <= clock() < min(now + timedelta(seconds=validity_seconds), evidence_deadline(report, now)):
            raise ValueError('PROBE_EXPIRED_DURING_COLLECTION')
    except (ValueError, TypeError, KeyError, ProbeError) as exc:
        reason = str(exc)
        blockers.append(reason if reason.startswith(('PROBE_', 'KERNEL_', 'STATE_')) else 'PROBE_INVALID_EVIDENCE')
    receipt = {'schema_version': 1, 'status': 'VERIFIED_PROCESS_RESPONSE' if not blockers else 'BLOCKED',
        'scope_sha256': report.inventory.environment.scope_sha256, 'url': url, 'service': service,
        'observed_at': now.isoformat(), 'expires_at': min(now + timedelta(seconds=validity_seconds), evidence_deadline(report, now)).isoformat(),
        'runtime_id': runtime_id(report.inventory, runtime) if runtime else None,
        'challenge_sha256': hashlib.sha256(challenge.encode()).hexdigest(),
        'peer_pid': runtime.pid if runtime else None,
        'configuration': {k: payload[k] for k in ('ini_file', 'ini_scanned', 'effective_ini_sha256', 'extensions_sha256')} if payload else None,
        'configuration_status': 'OBSERVED_EFFECTIVE_PHP_SETTINGS' if not blockers else 'UNKNOWN',
        'loaded_configuration_file_bytes': 'UNKNOWN', 'application_route_coverage': 'SINGLE_PROBE_REQUEST_ONLY',
        'blockers': blockers, 'executable': False, 'evidence': [asdict(e) for e in collector.evidence],
        'receipt_sha256': ''}
    receipt['receipt_sha256'] = digest(receipt)
    return receipt
