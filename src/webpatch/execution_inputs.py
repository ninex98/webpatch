"""Read-only facts needed by a bounded package execution contract."""
from dataclasses import asdict
import re

from .maintenance import SCRIPTS
from .planning import digest
from .system import Collector


def installed_controls(inspection, collector):
    records, blockers = [], []
    for archive in inspection['archives']:
        if 'installed' not in archive['roles']:
            continue
        if archive['status']!='INSPECTED_AUTHENTICATED_ARCHIVE':
            blockers.append('INSTALLED_CONTROL_ARCHIVE_UNKNOWN:'+archive['package_id'])
            continue
        base=archive['info_basename']
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?',base):
            blockers.append('INSTALLED_CONTROL_BASENAME_INVALID')
            continue
        for name in sorted(SCRIPTS|{'triggers'}):
            path='/var/lib/dpkg/info/'+base+'.'+name
            expected=archive['control_files'].get(name)
            actual, ident=collector.probe('archive_fingerprint',path)
            if expected is None:
                passed=actual is None and collector.evidence[-1].outcome=='FileNotFoundError'
            else:
                passed=(actual is not None and actual['sha256']==expected['sha256'] and actual.get('uid')==0
                        and actual.get('mode',0)&0o7777==expected['mode']&0o7777)
            records.append({'package_id':archive['package_id'],'path':path,
                            'status':'MATCHES_AUTHENTICATED_CONTROL' if passed else 'UNKNOWN',
                            'expected_sha256':expected['sha256'] if expected else None,
                            'observed_sha256':actual.get('sha256') if actual else None,'evidence_id':ident})
            if not passed: blockers.append('INSTALLED_CONTROL_CHANGED_OR_UNREADABLE:'+path)
    return records, blockers


def dpkg_configuration(collector):
    paths=['/etc/dpkg/dpkg.cfg']
    names,_=collector.probe('listdir','/etc/dpkg/dpkg.cfg.d')
    blockers=[]
    if names is None: blockers.append('DPKG_CONFIG_DIRECTORY_UNREADABLE')
    paths += ['/etc/dpkg/dpkg.cfg.d/'+n for n in names or [] if re.fullmatch(r'[0-9A-Za-z_-]+',n)]
    rows=[]
    for path in paths:
        raw,ident=collector.probe('read_text',path)
        if raw is None:
            if not (path=='/etc/dpkg/dpkg.cfg' and collector.evidence[-1].outcome=='FileNotFoundError'):
                blockers.append('DPKG_CONFIG_UNREADABLE:'+path)
            continue
        lines=[line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        unsupported=[line for line in lines if line not in {'no-debsig','log /var/log/dpkg.log'}]
        rows.append({'path':path,'status':'SUPPORTED_DEFAULT_OPTIONS' if not unsupported else 'UNKNOWN','evidence_id':ident})
        if unsupported: blockers.append('DPKG_SPECIAL_OPTIONS_REQUIRE_REVIEW:'+path)
    # A pre-existing policy must be preserved, never overwritten by an executor.
    existing,ident=collector.probe('archive_fingerprint','/usr/sbin/policy-rc.d')
    if existing is not None or collector.evidence[-1].outcome!='FileNotFoundError':
        blockers.append('EXISTING_SERVICE_START_POLICY_REQUIRES_REVIEW')
    return rows, blockers


def trigger_scope(inspection, collector):
    raw,ident=collector.probe('read_text','/var/lib/dpkg/triggers/File')
    pending,pending_id=collector.probe('read_text','/var/lib/dpkg/triggers/Unincorp')
    blockers=[]
    if raw is None: blockers.append('TRIGGER_REGISTRY_UNREADABLE')
    if pending is None or pending.strip(): blockers.append('PENDING_OR_UNREADABLE_TRIGGER_ACTIVATIONS')
    paths={p for a in inspection['archives'] if 'candidate' in a['roles'] for p in a['payload_paths']}
    handlers=set()
    for line in (raw or '').splitlines():
        parts=line.split()
        if len(parts)<2 or not parts[0].startswith('/'):
            blockers.append('TRIGGER_REGISTRY_UNSUPPORTED')
            continue
        target=parts[0].rstrip('/')
        for item in parts[1:]:
            name=item.removesuffix('/noawait')
            if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?',name):
                blockers.append('TRIGGER_HANDLER_INVALID')
                continue
            if any(p==target or p.startswith(target+'/') for p in paths): handlers.add(name)
    return {'status':'FILE_TRIGGER_CANDIDATES_IDENTIFIED' if not blockers else 'UNKNOWN',
            'package_names':sorted(handlers),'named_script_activations':'REQUIRES_EXPLICIT_REVIEW',
            'evidence_ids':[ident,pending_id]}, blockers


def audit_execution_inputs(inspection, *, system):
    collector=Collector(system,evidence_prefix='x')
    controls, reasons=installed_controls(inspection,collector)
    configuration, errors=dpkg_configuration(collector)
    reasons.extend(errors)
    triggers, errors=trigger_scope(inspection,collector)
    reasons.extend(errors)
    if not inspection['archives'] or inspection['status']!='READY_FOR_MAINTENANCE_REVIEW':
        reasons.append('AUTHENTICATED_MAINTENANCE_REVIEW_REQUIRED')
    result={'schema_version':1,'inspection_sha256':inspection['inspection_sha256'],
            'status':'READY_FOR_EXECUTION_POLICY_REVIEW' if not reasons else 'BLOCKED',
            'installed_controls':controls,'dpkg_configuration':configuration,'triggers':triggers,
            'blockers':sorted(set(reasons)),'executable':False,
            'evidence':[asdict(e) for e in collector.evidence],'audit_sha256':''}
    result['audit_sha256']=digest(result)
    return result
