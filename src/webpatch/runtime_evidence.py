"""Bounded procfs observations; no configuration execution or request probes."""
import hashlib
import json
import os
import re

from .models import RuntimeFile, RuntimeEndpoint
from .system import SAFE_PATH


def php_mapping_rows(raw):
    if raw is None:
        return None
    rows = []
    for line in raw.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 5 or not re.fullmatch(r'[0-9a-f]+-[0-9a-f]+', parts[0]):
            return None
        if len(parts) == 6 and (parts[5].startswith('/usr/lib/php/') or
                re.search(r'/libphp[^/]*\.so(?: \(deleted\))?$', parts[5])):
            rows.append(tuple(parts))
    return sorted(rows)


def mapping_digest(rows):
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest() if rows is not None else None


def mapped_php_files(collector, inventory, pid, foreign, evidence, owner_lookup):
    start = len(evidence)
    def probe(op, path):
        value, ident = collector.probe(op, path)
        evidence.append(ident)
        return value
    raw = probe('read_text', f'/proc/{pid}/maps')
    rows = php_mapping_rows(raw)
    files, blockers = [], []
    if rows is None:
        return (), ('PHP_MAPPINGS_UNREADABLE_OR_MALFORMED',), None
    grouped = {}
    for row in rows:
        grouped.setdefault(row[5], []).append(row)
    for path, segments in sorted(grouped.items()):
        first = len(evidence)
        deleted = path.endswith(' (deleted)')
        disk = None if deleted or not SAFE_PATH.fullmatch(path) else probe('fingerprint', path)
        valid = disk is not None
        for segment in segments:
            try:
                major, minor = (int(v, 16) for v in segment[3].split(':'))
                valid = valid and (disk['inode'], disk['device']) == (int(segment[4]), os.makedev(major, minor))
            except (ValueError, OverflowError, KeyError):
                valid = False
        if foreign and disk and probe('fingerprint', f'/proc/{pid}/root{path}') != disk:
            valid = False
        owners = owner_lookup(collector, path, inventory, evidence) if disk else ()
        if disk and probe('fingerprint', path) != disk:
            valid = False
        if not valid:
            blockers.append('DELETED_PHP_MAPPING' if deleted else 'PHP_MAPPING_DIFFERS_OR_UNREADABLE')
        if not owners:
            blockers.append('PHP_MAPPING_PACKAGE_UNKNOWN')
        files.append(RuntimeFile(path, 'php_module', owners, disk.get('sha256') if disk else None,
            disk.get('device') if disk else None, disk.get('inode') if disk else None,
            'VERIFIED_LOCAL_FILE' if valid else 'UNKNOWN', tuple(evidence[start:start+1] + evidence[first:])))
    if php_mapping_rows(probe('read_text', f'/proc/{pid}/maps')) != rows:
        blockers.append('MAPPINGS_CHANGED_DURING_SCAN')
    return tuple(files), tuple(sorted(set(blockers))), mapping_digest(rows)


def unix_listeners(collector, pid, evidence):
    start = len(evidence)
    def probe(op, path):
        value, ident = collector.probe(op, path)
        evidence.append(ident)
        return value
    ns = probe('readlink', f'/proc/{pid}/ns/net')
    own = probe('readlink', '/proc/self/ns/net')
    if not ns or ns != own:
        return (), 'UNKNOWN'
    names = probe('listdir', f'/proc/{pid}/fd')
    raw = probe('read_text', f'/proc/{pid}/net/unix')
    if names is None or raw is None or len(names) > 1024:
        return (), 'UNKNOWN'
    owned, links = set(), {}
    for fd in names:
        if not fd.isdigit():
            return (), 'UNKNOWN'
        link = probe('readlink', f'/proc/{pid}/fd/{fd}')
        if link is None:
            return (), 'UNKNOWN'
        links[fd] = link
        match = re.fullmatch(r'socket:\[([0-9]+)\]', link)
        if match:
            owned.add(match[1])
    endpoints = []
    for line in raw.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 7:
            return (), 'UNKNOWN'
        if fields[6] in owned and fields[3:6] == ['00010000', '0001', '01']:
            if len(fields) == 8 and SAFE_PATH.fullmatch(fields[7]):
                endpoints.append((fields[7], fields[6]))
    # Only the process's own listener rows matter; unrelated socket churn is normal.
    for fd, link in links.items():
        if link.startswith('socket:[') and probe('readlink', f'/proc/{pid}/fd/{fd}') != link:
            return (), 'UNKNOWN'
    after = probe('read_text', f'/proc/{pid}/net/unix')
    if after is None:
        return (), 'UNKNOWN'
    current = {tuple(line.split()[3:]) for line in after.splitlines()[1:] if len(line.split()) >= 7 and line.split()[6] in owned}
    before = {tuple(line.split()[3:]) for line in raw.splitlines()[1:] if len(line.split()) >= 7 and line.split()[6] in owned}
    if before != current or probe('readlink', f'/proc/{pid}/ns/net') != ns:
        return (), 'UNKNOWN'
    ids = tuple(evidence[start:])
    return tuple(RuntimeEndpoint(path, inode, ns, ids) for path, inode in sorted(set(endpoints))), 'OBSERVED'
