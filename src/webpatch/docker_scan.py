"""Container observations stay separate from host inventory and repair admission."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import re
import shlex

from .discovery import sapi_for
from .docker_io import FILES, HINT_PATHS, MAX_CONTAINERS, LocalDockerReader, local_endpoint
from .models import ContainerObservation, DockerReport, Environment, Inventory, Package
from .rules import DpkgComparator, RuleEngine
from .sources import paragraphs
from .system import Collector, ProbeError


def parse_os(raw, container_id, image_id):
    values = {}
    for line in (raw or '').splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise ValueError('DOCKER_OS_RELEASE_INVALID')
        parts = shlex.split(value, comments=True)
        if len(parts) != 1:
            raise ValueError('DOCKER_OS_RELEASE_INVALID')
        values[key] = parts[0]
    scope = hashlib.sha256(json.dumps([container_id, image_id]).encode()).hexdigest()
    return Environment(values.get('ID', 'unknown'), values.get('VERSION_ID', 'unknown'),
                       values.get('VERSION_CODENAME', 'unknown'), 'container', None, scope)


def parse_dpkg(raw, evidence_id):
    result = []
    for row in paragraphs(raw):
        name = row.get('Package', '')
        if not re.match(r'^(php(?:[0-9-]|$)|libapache2-mod-php|libphp)', name):
            continue
        status = row.get('Status', '')
        if status.split()[-1:] in (['not-installed'], ['config-files']):
            continue
        version = row.get('Version', '')
        source = re.fullmatch(r'([a-z0-9][a-z0-9+.-]*)(?: \(([^()\s]+)\))?', row.get('Source', name))
        if not source or not version or not row.get('Architecture'):
            raise ValueError('DOCKER_PACKAGE_METADATA_INVALID')
        result.append(Package(name, version, row['Architecture'], source[1], source[2] or version,
                              status, sapi_for(name), evidence_id))
    return result


def inspect_container(row, reader, system, rules, now):
    item = ContainerObservation(**row)
    collector = Collector(reader, evidence_prefix='docker-' + item.id[:12] + '-')
    item.gaps = ['CONTAINER_RUNTIME_AND_ROUTES_UNVERIFIED', 'CONTAINER_CUSTOM_PATHS_NOT_EXHAUSTIVE',
                 'CONTAINER_PACKAGE_BYTES_UNAUTHENTICATED']
    if item.state != 'running':
        item.gaps.append('CONTAINER_NOT_RUNNING')
    documents = {}
    for path in FILES:
        raw, ident = collector.probe('read_file', (item.id, path))
        if collector.evidence[-1].outcome != 'OK':
            item.gaps.append('CONTAINER_FILE_READ_FAILED:' + path)
        documents[path] = (raw, ident)
    os_raw = documents['/etc/os-release'][0] or documents['/usr/lib/os-release'][0]
    if os_raw:
        # /etc/os-release is commonly a symlink. The regular fallback is sufficient
        # for OS metadata; the refused symlink read remains in evidence.
        item.gaps = [g for g in item.gaps if g not in {
            'CONTAINER_FILE_READ_FAILED:/etc/os-release',
            'CONTAINER_FILE_READ_FAILED:/usr/lib/os-release'}]
    try:
        item.environment = parse_os(os_raw, item.id, item.image_id)
        if not os_raw:
            item.gaps.append('CONTAINER_OS_UNIDENTIFIED')
        raw, ident = documents['/var/lib/dpkg/status']
        if raw is not None:
            item.packages = parse_dpkg(raw, ident)
        elif item.environment.os_id in {'ubuntu', 'debian'}:
            item.gaps.append('CONTAINER_PACKAGE_DATABASE_MISSING')
    except ValueError:
        item.gaps.append('CONTAINER_METADATA_INVALID')
        item.environment = parse_os(None, item.id, item.image_id)
        item.packages = []
    apk = documents['/lib/apk/db/installed'][0]
    if apk is not None:
        for record in apk.split('\n\n'):
            name = re.search(r'^P:(php[^\n]*)$', record, re.M)
            version = re.search(r'^V:([^\n]+)$', record, re.M)
            if name:
                item.hints.append('apk: ' + name[1] + (' ' + version[1] if version else ''))
        item.gaps.append('CONTAINER_APK_RULES_UNSUPPORTED')
    header = documents['/usr/local/include/php/main/php_version.h'][0]
    if header is not None:
        version = re.search(r'^\s*#\s*define\s+PHP_VERSION\s+"([^"\n]{1,128})"', header, re.M)
        item.hints.append('/usr/local/include/php/main/php_version.h' + (': ' + version[1] if version else ''))
        item.gaps.append('CONTAINER_CUSTOM_PHP_VERSION_UNVERIFIED')
    for path in HINT_PATHS:
        exists, _ = collector.probe('path_exists', (item.id, path))
        if exists:
            item.hints.append(path)
        elif exists is None:
            item.gaps.append('CONTAINER_PATH_CHECK_FAILED:' + path)
    if item.state == 'running':
        names, _ = collector.probe('processes', item.id)
        if names is None:
            item.gaps.append('CONTAINER_PROCESSES_UNREADABLE')
        else:
            item.hints.extend('process: ' + n for n in sorted(set(names))
                              if any(s in n.lower() for s in ('php', 'apache', 'httpd', 'lshttpd', 'lsphp')))
    comparison = Collector(system, evidence_prefix='docker-' + item.id[:12] + '-version-')
    item.assessments = rules.assess(Inventory(item.environment, packages=item.packages),
                                    DpkgComparator(comparison), now)
    if not rules.reviewed <= now < rules.expires:
        item.gaps.append('RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW')
    if not item.packages and not item.hints:
        item.gaps.append('CONTAINER_NO_PHP_OBSERVED_NOT_PROOF_OF_ABSENCE')
    if any(a.version_status == 'BELOW_VENDOR_FIX' for a in item.assessments):
        item.overall = 'POTENTIALLY_AFFECTED'
    item.evidence = collector.evidence + comparison.evidence
    return item


def scan_docker(reader, system, *, now=None, rules=None):
    now = now or datetime.now(timezone.utc)
    rules = rules or RuleEngine()
    result = DockerReport('UNKNOWN', endpoint=reader.endpoint)
    collector = Collector(reader, evidence_prefix='docker-list-')
    rows, _ = collector.probe('containers', '')
    if rows is None:
        result.gaps.append(collector.evidence[-1].outcome)
        result.evidence = collector.evidence
        return result
    result.listed_count = len(rows)
    result.status = 'OBSERVED'
    if len(rows) > MAX_CONTAINERS:
        result.status = 'PARTIAL'
        result.gaps.append('DOCKER_CONTAINER_LIMIT_REACHED')
    for row in rows[:MAX_CONTAINERS]:
        result.containers.append(inspect_container(row, reader, system, rules, now))
    after, _ = collector.probe('containers', '')
    if after is None or after != rows:
        result.status = 'PARTIAL'
        result.gaps.append('DOCKER_CONTAINER_SET_CHANGED_OR_UNREADABLE')
        after_by_id = {r['id']: r for r in after or []}
        for item, before in zip(result.containers, rows):
            if after_by_id.get(item.id) != before:
                item.gaps.append('CONTAINER_CHANGED_OR_DISAPPEARED')
    result.evidence = collector.evidence
    result.gaps.append('DOCKER_OTHER_DAEMONS_AND_RUNTIME_IDENTITY_UNVERIFIED')
    return result


def attach_docker(report, system, *, reader=None, native=False, mode='auto', endpoint=None, now=None):
    if mode == 'off':
        docker = DockerReport('NOT_CHECKED', gaps=['DOCKER_DISABLED'])
    elif report.inventory.environment.scope == 'container':
        docker = DockerReport('NOT_CHECKED', gaps=['DOCKER_CURRENT_CONTAINER_ONLY'])
    elif reader is not None:
        docker = scan_docker(reader, system, now=now)
    elif native:
        try:
            path = local_endpoint(endpoint)
            docker = (scan_docker(LocalDockerReader(path), system, now=now) if path else
                      DockerReport('NOT_DETECTED', gaps=['DOCKER_LOCAL_SOCKET_NOT_FOUND']))
        except ProbeError as exc:
            docker = DockerReport('UNKNOWN', gaps=[str(exc)])
    else:
        # Injected system tests must never fall back to the developer's Docker socket.
        return report
    affected = any(c.overall == 'POTENTIALLY_AFFECTED' for c in docker.containers)
    return replace(report, docker=docker, overall='POTENTIALLY_AFFECTED' if affected else report.overall)
