"""Authenticated package control review. Scripts are data and never executed."""
from dataclasses import asdict
from datetime import datetime, timezone
import re

from .planning import digest, check_bindings
from .system import Collector
from .trust import source_identity

SCRIPTS = {'preinst', 'postinst', 'prerm', 'postrm', 'config'}
REVIEW_FILES = SCRIPTS | {'triggers', 'conffiles'}


def conffiles(control_files):
    record = control_files.get('conffiles')
    if record is None:
        return []
    if record['text'] is None:
        raise ValueError('CONFFILE_LIST_OPAQUE')
    rows, seen = [], set()
    for line in record['text'].splitlines():
        fields = line.split()
        flag = None
        if len(fields) == 2 and fields[0] == 'remove-on-upgrade':
            flag, path = fields
        elif len(fields) == 1:
            path = fields[0]
        else:
            raise ValueError('CONFFILE_LIST_UNSUPPORTED')
        if not re.fullmatch(r'/(?:[A-Za-z0-9_.+@-]+/)*[A-Za-z0-9_.+@-]+', path) or '..' in path.split('/') or path in seen:
            raise ValueError('CONFFILE_PATH_AMBIGUOUS_OR_UNSUPPORTED')
        seen.add(path)
        rows.append({'path': path, 'flag': flag})
    return rows


def inspect_maintenance(report, proposal, *, system, package_cache, now=None):
    """Bind exact old/new control archives and local conffile conflicts for review."""
    now = now or datetime.now(timezone.utc)
    collector = Collector(system, evidence_prefix='m')
    blockers, records = [], []
    trust = report.package_trust or {}
    if not datetime.fromisoformat(proposal.created_at) <= now < datetime.fromisoformat(proposal.expires_at):
        blockers.append('MAINTENANCE_PLAN_EXPIRED_OR_CLOCK_REVERSED')
    if not check_bindings(collector, proposal.bindings, report):
        blockers.append('MAINTENANCE_INPUT_STATE_DRIFT')
    names, listing_id = collector.probe('listdir', package_cache)
    if names is None:
        blockers.append('MAINTENANCE_CACHE_UNREADABLE')
    requirements = {}
    for target in proposal.targets:
        requirements.setdefault((target.name, target.architecture, target.version), set()).add('candidate')
        requirements.setdefault((target.name, target.architecture, target.installed_version), set()).add('installed')
    for change in proposal.changes:
        for role, version in (('installed', change.old_version), ('candidate', change.new_version)):
            if version:
                requirements.setdefault((change.name, change.architecture, version), set()).add(role)
    if not requirements:
        blockers.append('MAINTENANCE_NO_EXACT_PACKAGE_SET')
    for (name, arch, version), roles in sorted(requirements.items()):
        start = len(collector.evidence)
        errors, verified, archive_path, expected_hash = [], None, None, None
        candidates = [c for c in trust.get('candidates', []) if (c['name'], c['architecture'], c['version']) == (name, arch, version)]
        hashes = {c['sha256'] for c in candidates}
        if len(hashes) != 1:
            errors.append('CONTROL_ARCHIVE_ORIGIN_AMBIGUOUS_OR_UNKNOWN')
        else:
            expected_hash = next(iter(hashes))
            for filename in [n for n in names or [] if n.startswith(name + '_') and n.endswith('.deb')][:32]:
                path = package_cache.rstrip('/') + '/' + filename
                before, _ = collector.probe('archive_fingerprint', path)
                if not before or before['sha256'] != expected_hash or before['size'] not in {c['size'] for c in candidates}:
                    continue
                archive, _ = collector.probe('package_archive', (path,expected_hash))
                after, _ = collector.probe('archive_fingerprint', path)
                if not archive or archive.get('archive_sha256') != expected_hash or before != after:
                    errors.append('CONTROL_ARCHIVE_CHANGED_OR_UNREADABLE')
                    continue
                control = archive.get('control', {})
                try:
                    identity = (control['Package'], control['Architecture'], control['Version'], *source_identity(control))
                    if not any(identity == (c['name'], c['architecture'], c['version'], c['source_name'], c['source_version']) for c in candidates):
                        raise ValueError('CONTROL_ARCHIVE_IDENTITY_MISMATCH')
                    if not archive.get('control_metadata_complete'):
                        raise ValueError('CONTROL_METADATA_UNAVAILABLE')
                    controls = archive['control_files']
                    configs = conffiles(controls)
                    for script in SCRIPTS & controls.keys():
                        if controls[script]['text'] is None:
                            errors.append('MAINTAINER_SCRIPT_OPAQUE:' + script)
                    if 'triggers' in controls and controls['triggers']['text'] is None:
                        errors.append('TRIGGER_DECLARATIONS_OPAQUE')
                    for config in configs:
                        if config['flag']:
                            errors.append('CONFFILE_REMOVAL_REQUIRES_REVIEW:' + config['path'])
                        elif config['path'] not in archive.get('payload_files', {}):
                            errors.append('CONFFILE_PAYLOAD_UNVERIFIED:' + config['path'])
                    verified, archive_path = archive, path
                    break
                except (KeyError, ValueError, TypeError) as exc:
                    errors.append(str(exc) if str(exc).startswith(('CONTROL_', 'CONFFILE_')) else 'CONTROL_METADATA_INVALID')
            if verified is None:
                errors.append('AUTHENTICATED_CONTROL_ARCHIVE_UNAVAILABLE')
        record = {'package_id': name + ':' + arch, 'version': version, 'roles': sorted(roles),
                  'archive_sha256': expected_hash, 'archive_path': archive_path,
                  'control_files': {k: v for k, v in verified['control_files'].items() if k in REVIEW_FILES} if verified else {},
                  'conffiles': conffiles(verified['control_files']) if verified else [],
                  'payload_configuration': {c['path']: verified.get('payload_files', {}).get(c['path']) for c in conffiles(verified['control_files'])} if verified else {},
                  'payload_paths':sorted(verified.get('payload_entries',verified.get('payload_files',{}))) if verified else [],
                  'execution_files':{p:h for p,h in verified.get('payload_files',{}).items()
                      if p.startswith(('/bin/','/sbin/','/lib/','/usr/bin/','/usr/sbin/','/usr/lib/'))
                      or verified.get('payload_entries',{}).get(p,{}).get('mode',0)&0o111} if verified else {},
                  'info_basename':name+(':'+arch if verified and verified['control'].get('Multi-Arch')=='same' else ''),
                  'pre_depends':verified['control'].get('Pre-Depends','') if verified else None,
                  'status': 'INSPECTED_AUTHENTICATED_ARCHIVE' if verified and not errors else 'UNKNOWN',
                  'blockers': sorted(set(errors)),
                  'evidence_ids': [listing_id, *[e.id for e in collector.evidence[start:]]],
                  'provenance_evidence_ids': sorted({e for c in candidates for e in c.get('evidence_ids', [])})}
        records.append(record)
        blockers.extend(name + ':' + b for b in record['blockers'])
    conflicts = []
    for record in records:
        if 'installed' not in record['roles'] or record['status'] != 'INSPECTED_AUTHENTICATED_ARCHIVE':
            continue
        for path, expected in record['payload_configuration'].items():
            actual, evidence_id = collector.probe('fingerprint', path)
            status = 'UNCHANGED_FROM_AUTHENTICATED_ARCHIVE' if actual and expected and actual['sha256'] == expected else 'LOCAL_CHANGE_OR_UNREADABLE'
            conflicts.append({'package_id': record['package_id'], 'path': path, 'status': status,
                              'expected_sha256': expected, 'observed_sha256': actual.get('sha256') if actual else None,
                              'evidence_id': evidence_id})
            if status != 'UNCHANGED_FROM_AUTHENTICATED_ARCHIVE':
                blockers.append('CONFFILE_LOCAL_DECISION_REQUIRED:' + path)
    if not check_bindings(collector, proposal.bindings, report):
        blockers.append('MAINTENANCE_INPUT_STATE_DRIFT')
    result = {'schema_version': 1, 'plan_sha256': proposal.plan_sha256, 'scope_sha256': report.inventory.environment.scope_sha256,
              'expires_at': proposal.expires_at, 'status': 'READY_FOR_MAINTENANCE_REVIEW' if not blockers else 'BLOCKED',
              'archives': records, 'local_conffiles': conflicts, 'blockers': sorted(set(blockers)),
              'installation_effects': 'REQUIRES_OPERATOR_REVIEW', 'trigger_cascade': 'NOT_PROVEN',
              'executable': False, 'evidence': [asdict(e) for e in collector.evidence], 'inspection_sha256': ''}
    result['inspection_sha256'] = digest(result)
    return result
