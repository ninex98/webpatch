"""Read-only census of current executable/mapped consumers of selected files.

This examines all visible PIDs, independently of comm names. It proves only the
bounded active mapping census; idle jobs, future executions and hidden scopes
need separate deployment/maintenance policy and never become implicitly safe.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import os
import re

from .coverage import runtime_id
from .planning import digest
from .runtime import start_ticks
from .runtime_evidence import mapping_digest
from .gates import evidence_deadline
from .system import Collector

MAX_PIDS = 16384
PF_KTHREAD = 0x00200000


def map_rows(raw):
    rows = []
    for line in raw.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 5 or not re.fullmatch(r'[0-9a-f]+-[0-9a-f]+', fields[0]):
            raise ValueError('CONSUMER_MAPS_MALFORMED')
        try:
            major, minor = (int(v, 16) for v in fields[3].split(':'))
            rows.append((os.makedev(major, minor), int(fields[4]), fields[5] if len(fields) == 6 else None))
        except (ValueError, OverflowError):
            raise ValueError('CONSUMER_MAPS_MALFORMED') from None
    return rows


def inactive_kernel_or_zombie(raw):
    try:
        fields = raw.rsplit(')', 1)[1].split()
        return fields[0] == 'Z' or bool(int(fields[6]) & PF_KTHREAD)
    except (IndexError, ValueError, AttributeError):
        return False


def census(report, *, system, package_ids, now=None, clock=None):
    if clock is None:
        fixed_now=now
        clock=(lambda:fixed_now) if fixed_now is not None else (lambda:datetime.now(timezone.utc))
    now=clock()
    if not now.tzinfo:
        raise ValueError('TIMEZONE_REQUIRED')
    if not package_ids or not all(isinstance(p, str) for p in package_ids):
        raise ValueError('CONSUMER_TARGETS_REQUIRED')
    selected = set(package_ids)
    collector = Collector(system, evidence_prefix='c')
    reasons, affected = [], []
    indexes, paths, file_identities = {}, {}, {}
    installed = {i['package_id']:i for i in (report.package_trust or {}).get('installed', [])}
    for package_id in sorted(selected):
        identity = installed.get(package_id)
        if identity and identity['status']=='AUTHENTICATED_METADATA_ONLY_ARCHIVE':
            continue
        if not identity or identity['status'] != 'AUTHENTICATED_RUNTIME_FILES' or not identity.get('files'):
            reasons.append('CONSUMER_PACKAGE_FILE_IDENTITY_UNKNOWN:' + package_id)
            continue
        for path, expected in identity['files'].items():
            actual, ident = collector.probe('fingerprint', path)
            if not actual or actual['sha256'] != expected:
                reasons.append('CONSUMER_FILE_CHANGED_OR_UNREADABLE:' + path)
                continue
            key = (actual['device'], actual['inode'])
            file_identities[path]=(actual['device'],actual['inode'],actual['sha256'])
            indexes.setdefault(key, set()).add(package_id)
            paths.setdefault(path, set()).add(package_id)
    before, _ = collector.probe('listdir', '/proc')
    pids = sorted((p for p in before or [] if p.isdigit()), key=int)
    if before is None or not pids or len(pids) > MAX_PIDS:
        reasons.append('CONSUMER_PROCESS_SET_UNAVAILABLE_OR_LIMIT')
    known = {r.pid:r for r in report.inventory.runtimes}
    for pid in pids[:MAX_PIDS]:
        initial, first_id = collector.probe('read_text', f'/proc/{pid}/stat')
        initial_ticks = start_ticks(initial)
        raw, maps_id = collector.probe('read_text', f'/proc/{pid}/maps')
        executable, exe_id = collector.probe('identity', f'/proc/{pid}/exe')
        descriptors,fd_id=collector.probe('file_descriptors',pid)
        unavailable = not initial_ticks or raw is None
        if descriptors is None:
            unavailable=True
            reasons.append('CONSUMER_PROCESS_DESCRIPTORS_UNREADABLE:'+pid)
        if executable is None and not (raw == '' and inactive_kernel_or_zombie(initial)):
            unavailable = True
        matched, mismatches, rows = set(), [], []
        fd_rows=[(f['device'],f['inode'],f['target']) for f in (descriptors or {}).get('files',[])]
        try:
            rows = map_rows(raw) if raw is not None else []
            if executable:
                matched.update(indexes.get((executable['device'], executable['inode']), ()))
            for device, inode, path in rows+fd_rows:
                matched.update(indexes.get((device, inode), ()))
                if path:
                    clean = path.removesuffix(' (deleted)')
                    if clean in paths and (device, inode) not in indexes:
                        matched.update(paths[clean])
                        mismatches.append(clean)
        except (ValueError, KeyError):
            unavailable = True
        final, last_id = collector.probe('read_text', f'/proc/{pid}/stat')
        later, _ = collector.probe('read_text', f'/proc/{pid}/maps')
        after_exe, _ = collector.probe('identity', f'/proc/{pid}/exe')
        later_descriptors,later_fd_id=collector.probe('file_descriptors',pid)
        if later_descriptors is None:
            unavailable=True
            reasons.append('CONSUMER_PROCESS_DESCRIPTORS_UNREADABLE:'+pid)
        if not initial_ticks or start_ticks(final) != initial_ticks:
            unavailable = True
        try:
            relevant = lambda values: sorted(r for r in values if (r[0],r[1]) in indexes or (r[2] and r[2].removesuffix(' (deleted)') in paths))
            if relevant(map_rows(later)) != relevant(rows) or after_exe != executable:
                unavailable = True
            later_fd_rows=[(f['device'],f['inode'],f['target']) for f in (later_descriptors or {}).get('files',[])]
            if relevant(later_fd_rows)!=relevant(fd_rows):
                unavailable=True
                reasons.append('CONSUMER_PROCESS_DESCRIPTORS_CHANGED:'+pid)
        except (ValueError, AttributeError):
            unavailable = True
        if unavailable:
            reasons.append('CONSUMER_PROCESS_UNSTABLE_OR_UNREADABLE:' + pid)
        if matched:
            runtime = known.get(int(pid))
            frame = [collector.probe(op, path)[0] for op, path in (
                ('readlink', f'/proc/{pid}/ns/mnt'), ('readlink', f'/proc/{pid}/ns/pid'), ('identity', f'/proc/{pid}/root'))]
            verified = (not unavailable and not mismatches and runtime is not None
                        and runtime.start_ticks == initial_ticks and runtime.association == 'VERIFIED_LOCAL_ASSOCIATION'
                        and runtime.namespace_sha256 == mapping_digest(frame)
                        and matched <= set(runtime.package_ids))
            affected.append({'pid':int(pid), 'start_ticks':initial_ticks, 'package_ids':sorted(matched),
                             'runtime_id':runtime_id(report.inventory, runtime) if runtime else None,
                             'service':runtime.service if runtime else None,
                             'status':'ACCOUNTED_ACTIVE_CONSUMER' if verified else 'UNACCOUNTED_OR_CHANGED_CONSUMER',
                             'mismatched_paths':sorted(set(mismatches)),
                             'open_file_descriptor_observations':len(relevant(fd_rows)),
                             'evidence_ids':[first_id,maps_id,exe_id,last_id,fd_id,later_fd_id]})
            if not verified:
                reasons.append('CONSUMER_NOT_ACCOUNTED:' + pid)
    after, _ = collector.probe('listdir', '/proc')
    if after is None or pids != sorted((p for p in after if p.isdigit()), key=int):
        reasons.append('CONSUMER_PROCESS_SET_CHANGED')
    for path,expected in file_identities.items():
        current,_=collector.probe('fingerprint',path)
        if current is None or tuple(current[k] for k in ('device','inode','sha256'))!=expected:
            reasons.append('CONSUMER_FILE_CHANGED_DURING_CENSUS:'+path)
    if not report.inventory.environment.scope_sha256:
        reasons.append('CONSUMER_SCOPE_UNKNOWN')
    if not affected:
        reasons.append('CONSUMER_NONE_OBSERVED_IS_NOT_COVERAGE')
    deadline = min(now + timedelta(minutes=5), evidence_deadline(report, now))
    if not datetime.fromisoformat(report.observed_at) <= now <= clock() < deadline:
        reasons.append('CONSUMER_EVIDENCE_EXPIRED_OR_CLOCK_REVERSED')
    result = {'schema_version':1, 'scope_sha256':report.inventory.environment.scope_sha256,
              'observed_at':now.isoformat(), 'expires_at':deadline.isoformat(),
              'package_ids':sorted(selected), 'visible_pid_count':len(pids), 'consumers':affected,
              'status':'VERIFIED_ACTIVE_MAPPING_CENSUS' if not reasons else 'BLOCKED',
              'blockers':sorted(set(reasons)), 'idle_and_future_consumers':'NOT_PROVEN',
              'file_descriptor_coverage':'VERIFIED_VISIBLE_FILE_DESCRIPTORS' if pids and not any(r.startswith(('CONSUMER_PROCESS_','CONSUMER_SCOPE_')) for r in reasons) else 'UNKNOWN',
              'executable':False, 'evidence':[asdict(e) for e in collector.evidence], 'census_sha256':''}
    result['census_sha256'] = digest(result)
    return result
