"""Explicit controlled-startup plans and measured configuration snapshots.

Preparation may restart declared services only after exact hash confirmation.
It never installs packages. Immutable snapshot views connect startup inputs to
subsequent in-process observations without using mtimes as loaded-state proof.
"""
from dataclasses import asdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import PurePosixPath
import re
import secrets
from importlib.resources import files

from .application import target_url, collect_application_evidence
from .coverage import runtime_id
from .gates import evidence_deadline
from .planning import digest, stable_bindings, state_digest, lock_blockers, check_bindings
from .platform_proof import authenticate_service
from .service import scan
from .system import Collector, ProbeError

STATE_DIRECTORY = re.compile(r'/var/lib/webpatch(?:-[a-z0-9-]+)?\Z')


def implementation_digest():
    root = files('webpatch')
    names = ('preparation.py','service_control.py','platform_proof.py','receipts.py','application.py',
             'system.py','trust.py','planning.py','data/application_probe.php')
    return digest({name:hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest() for name in names})


def restricted_ini_value(raw):
    match = re.fullmatch(r'''\s*(?:"([^"\\]*)"|'([^'\\]*)'|([^;"'\\]*?))\s*(?:;.*)?''',raw)
    if not match:
        raise ValueError('PREPARATION_CONFIGURATION_VALUE_AMBIGUOUS')
    if match[1] is not None: return match[1]
    if match[2] is not None: return match[2]
    return match[3].strip()


def configuration_roots(report, service):
    branch = {'jammy':'8.1','noble':'8.3'}.get(report.inventory.environment.codename)
    if report.inventory.environment.os_id != 'ubuntu' or not branch:
        raise ValueError('PREPARATION_RELEASE_UNSUPPORTED')
    if service == f'php{branch}-fpm.service':
        return (f'/etc/php/{branch}/fpm',)
    if service == 'apache2.service':
        return ('/etc/apache2', f'/etc/php/{branch}/apache2')
    raise ValueError('PREPARATION_SERVICE_UNSUPPORTED')


def static_inputs(report):
    return [asdict(b) for b in stable_bindings(report) if not (b.operation=='run' and '/usr/bin/systemctl' in b.target)]


def preparation_plan(report, *, system, services, probes, package_cache, state_dir='/var/lib/webpatch', now=None,
                     package_lock_owned=False):
    now = now or datetime.now(timezone.utc)
    if not STATE_DIRECTORY.fullmatch(state_dir): raise ValueError('PREPARATION_STATE_DIRECTORY_INVALID')
    if not isinstance(services,(list,tuple)) or not services or len(services)>16 or len(set(services))!=len(services):
        raise ValueError('PREPARATION_SERVICES_INVALID')
    if not isinstance(probes,(list,tuple)) or not probes or len(probes)>64:
        raise ValueError('PREPARATION_PROBES_REQUIRED')
    services = sorted(services)
    collector = Collector(system, evidence_prefix='s')
    blockers, definitions, configuration = [], [], []
    if report.inventory.environment.scope == 'container': blockers.append('CONTAINER_REBUILD_REQUIRED')
    if not package_lock_owned: blockers.extend(lock_blockers(collector))
    validated_probes = []
    for probe in probes:
        if not isinstance(probe,dict) or set(probe) != {'service','url','script','pool_listener'} or probe['service'] not in services:
            raise ValueError('PREPARATION_PROBE_INVALID')
        target_url(probe['url'])
        if not isinstance(probe['script'],str) or not probe['script'].startswith('/var/www/') or '..' in PurePosixPath(probe['script']).parts:
            raise ValueError('PREPARATION_PROBE_SCRIPT_UNSUPPORTED')
        if PurePosixPath(probe['url'].split(':',2)[-1]).name != PurePosixPath(probe['script']).name:
            raise ValueError('PREPARATION_PROBE_URL_SCRIPT_MISMATCH')
        if probe['pool_listener'] is not None and not re.fullmatch(r'/[A-Za-z0-9_./-]+',probe['pool_listener']):
            raise ValueError('PREPARATION_POOL_LISTENER_INVALID')
        validated_probes.append(dict(probe))
    if {p['service'] for p in validated_probes} != set(services):
        blockers.append('PREPARATION_EVERY_SERVICE_REQUIRES_PROBE')
    for service in services:
        roots = configuration_roots(report, service)
        runtimes = [r for r in report.inventory.runtimes if r.service == service]
        if not runtimes or any(r.association != 'VERIFIED_LOCAL_ASSOCIATION' for r in runtimes):
            blockers.append('PREPARATION_RUNTIME_NOT_VERIFIED:' + service)
        proof = authenticate_service(report, system=system, service=service, package_cache=package_cache)
        definitions.append(proof)
        if proof['status'] != 'AUTHENTICATED_SERVICE_DEFINITION': blockers.extend(proof['blockers'])
        if not proof.get('unit_source'): blockers.append('PREPARATION_UNIT_SOURCE_UNAVAILABLE:' + service)
        for root in roots:
            inputs = {e.target for e in report.evidence if e.operation=='read_text' and e.target.startswith(root+'/') and e.outcome=='OK'}
            if root == '/etc/apache2': inputs.add('/etc/apache2/envvars')
            if not inputs: blockers.append('PREPARATION_CONFIGURATION_EMPTY:' + root)
            files = []
            loaded_modules = {f.path for r in runtimes for f in r.files if f.role=='php_module'}
            for path in sorted(inputs):
                raw, ident = collector.probe('read_text',path)
                info, _ = collector.probe('fingerprint',path)
                if (raw is None or info is None or info.get('uid') != 0 or info.get('mode',0) & 0o022
                        or '..' in PurePosixPath(path).parts):
                    blockers.append('PREPARATION_CONFIGURATION_UNTRUSTED:' + path)
                    continue
                # Absolute/dynamic includes were already bounded by the adapter.
                # Active PHP code hooks cannot be treated as pure configuration.
                for line in raw.splitlines():
                    keys = r'auto_prepend_file|auto_append_file|ffi\.preload|opcache\.preload|extension|zend_extension|extension_dir|enable_dl|session\.auto_start|user_ini\.filename'
                    match = re.match(r'''^\s*(?:php_(?:admin_)?(?:value|flag)\[\s*["']?)?('''+keys+r''')(?:["']?\s*\])?\s*=\s*(.*)''',line,re.I)
                    match = match or re.match(r'^\s*php_(?:admin_)?(?:value|flag)\s+('+keys+r')\s+(.+)',line,re.I)
                    if not match: continue
                    key = match[1].lower()
                    try:
                        value = restricted_ini_value(match[2])
                    except ValueError:
                        blockers.append('PREPARATION_CONFIGURATION_VALUE_AMBIGUOUS:' + path)
                        continue
                    if key in {'auto_prepend_file','auto_append_file','ffi.preload','opcache.preload'} and value:
                        blockers.append('PREPARATION_PHP_CODE_HOOK_UNSUPPORTED:' + path)
                    if key in {'enable_dl','session.auto_start'} and value.lower() not in {'','off','false','0','no'}:
                        blockers.append('PREPARATION_DYNAMIC_LOADING_UNSUPPORTED:' + path)
                    if key=='user_ini.filename' and value not in {'','.user.ini'}:
                        blockers.append('PREPARATION_USER_INI_NAME_UNSUPPORTED:' + path)
                    if key in {'extension','zend_extension'} and not any(value==p or (not value.startswith('/') and value in {PurePosixPath(p).name,PurePosixPath(p).stem}) for p in loaded_modules):
                        blockers.append('PREPARATION_NEW_OR_UNKNOWN_MODULE:' + path)
                    if key=='extension_dir' and value and value not in {str(PurePosixPath(p).parent) for p in loaded_modules}:
                        blockers.append('PREPARATION_EXTENSION_DIRECTORY_UNKNOWN:' + path)
                if re.search(r'^\s*pm\s*=\s*ondemand\b',raw,re.M):
                    blockers.append('PREPARATION_ONDEMAND_POOL_REQUIRES_STABLE_MAINTENANCE_PROFILE:' + path)
                files.append({'path':path,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'size':len(raw.encode()),'evidence_id':ident})
            if len(files)>512 or sum(f['size'] for f in files)>8*1024*1024:
                blockers.append('PREPARATION_CONFIGURATION_LIMIT')
            configuration.append({'service':service,'root':root,'files':files})
        if service.endswith('-fpm.service'):
            pools = {r.target for r in report.inventory.config_relations if r.kind=='fpm_pool' and any(r.path.startswith(root+'/') for root in roots)}
            declared = {p['pool_listener'] for p in validated_probes if p['service']==service}
            if not pools or pools != declared or any(not p.startswith('/') for p in pools):
                blockers.append('PREPARATION_EVERY_POOL_REQUIRES_EXPLICIT_PROBE:' + service)
    for gap in report.inventory.coverage_gaps:
        if gap.startswith(('CONFIG_INCLUDE_OUTSIDE','CONFIG_DYNAMIC_INCLUDE','CONFIG_UNREADABLE','FPM_DYNAMIC_OR_CHROOT','FPM_REPEATED_INCLUDE','CONFIG_CHANGED_DURING_SCAN')):
            blockers.append('PREPARATION_CONFIGURATION_COVERAGE:' + gap)
    if not report.inventory.environment.scope_sha256:
        blockers.append('PREPARATION_SCOPE_UNKNOWN')
    expiry = evidence_deadline(report,now)
    if not datetime.fromisoformat(report.observed_at) <= now < expiry:
        blockers.append('PREPARATION_EVIDENCE_EXPIRED')
    result = {'schema_version':1, 'kind':'controlled_service_preparation', 'scope_sha256':report.inventory.environment.scope_sha256,
        'created_at':now.isoformat(),'expires_at':expiry.isoformat(),'state_directory':state_dir,
        'implementation_sha256':implementation_digest(),'rule_sha256':report.rule_sha256,
        'package_cache':package_cache,'services':services,'probes':sorted(validated_probes,key=lambda p:(p['service'],p['url'])),
        'configuration':configuration,'definitions':definitions,'static_inputs_sha256':digest(static_inputs(report)),
        'runtime_ids':sorted(runtime_id(report.inventory,r) for r in report.inventory.runtimes if r.service in services),
        'actions':['Create private read-only configuration snapshots and authenticated temporary service definitions',
                   'Reload systemd definitions and restart the declared services',
                   'Warm and verify the explicitly declared loopback probes; record kernel/process/configuration evidence'],
        'interruption':'Requests on every declared service may be interrupted; preparation does not install packages.',
        'status':'READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION' if not blockers else 'BLOCKED',
        'blockers':sorted(set(blockers)), 'evidence':[asdict(e) for e in collector.evidence], 'preparation_sha256':''}
    result['preparation_sha256'] = digest(result)
    return result


def preparation_semantics(document):
    return {'scope':document['scope_sha256'],'services':document['services'],'probes':document['probes'],
            'state_directory':document['state_directory'],'package_cache':document['package_cache'],
            'implementation':document['implementation_sha256'],'rules':document['rule_sha256'],
            'actions':document['actions'],'interruption':document['interruption'],
            'status':document['status'],'blockers':document['blockers'],
            'static_inputs':document['static_inputs_sha256'],'runtime_ids':document['runtime_ids'],
            'configuration':[{**tree,'files':[{k:v for k,v in f.items() if k!='evidence_id'} for f in tree['files']]} for tree in document['configuration']],
            'definitions':[{**{k:d[k] for k in ('service','status','definition_sha256','archives','blockers','unit_source')},
                            'files':[{k:v for k,v in f.items() if k!='evidence_id'} for f in d['files']]} for d in document['definitions']]}


def verify_snapshot_views(report, snapshots, system):
    collector = Collector(system,evidence_prefix='v')
    blockers, views = [], []
    for tree in snapshots:
        runtimes = [r for r in report.inventory.runtimes if r.service==tree['service']]
        if not runtimes:
            blockers.append('SNAPSHOT_SERVICE_HAS_NO_RUNTIME:' + tree['service'])
        for runtime in runtimes:
            mountinfo, _ = collector.probe('read_text',f'/proc/{runtime.pid}/mountinfo')
            mounts = [line.split() for line in (mountinfo or '').splitlines()]
            exact = [m for m in mounts if len(m)>6 and m[4]==tree['root']]
            if len(exact)!=1 or 'ro' not in exact[0][5].split(',') or any(len(m)>6 and m[4].startswith(tree['root']+'/') for m in mounts):
                blockers.append('SNAPSHOT_READONLY_MOUNT_UNVERIFIED:' + str(runtime.pid))
            for file in tree['files']:
                actual, ident = collector.probe('fingerprint',f'/proc/{runtime.pid}/root'+file['path'])
                if actual is None or (actual['device'],actual['inode'],actual['sha256']) != (file['device'],file['inode'],file['sha256']):
                    blockers.append('SNAPSHOT_RUNTIME_FILE_VIEW_MISMATCH:' + str(runtime.pid)+':'+file['path'])
                views.append({'pid':runtime.pid,'path':file['path'],'evidence_id':ident})
    return {'status':'VERIFIED_READONLY_RUNTIME_VIEWS' if not blockers else 'BLOCKED','blockers':sorted(set(blockers)),
            'views':views,'evidence':[asdict(e) for e in collector.evidence]}


def execute_preparation(saved, *, confirmation_sha256, system, controller, probe, journal, clock=None, scanner=scan):
    clock = clock or (lambda:datetime.now(timezone.utc))
    changed, materialized, audit_failed = False, None, False
    def event(state, detail=None): journal.append({'kind':'preparation','hash':saved.get('preparation_sha256'),
                                                  'state':state,'at':clock().isoformat(),'details':detail or {}})
    @contextmanager
    def audited_lock():
        nonlocal audit_failed
        with controller.locked():
            try:
                yield
            except Exception as exc:
                try:
                    event('PREPARATION_PARTIAL' if changed else 'PREPARATION_ABORTED',{'exception_type':type(exc).__name__})
                except Exception:
                    audit_failed = True
                raise
    try:
        if (not isinstance(saved,dict) or type(saved.get('schema_version')) is not int or saved.get('schema_version')!=1 or saved.get('kind')!='controlled_service_preparation'
                or digest(dict(saved,preparation_sha256='')) != saved.get('preparation_sha256')
                or confirmation_sha256 != saved['preparation_sha256']):
            raise ValueError('PREPARATION_EXACT_CONFIRMATION_REQUIRED')
        if saved['status']!='READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION' or saved['blockers']:
            raise ValueError('PREPARATION_ADMISSION_BLOCKED')
        if not isinstance(saved.get('state_directory'),str) or not STATE_DIRECTORY.fullmatch(saved['state_directory']):
            raise ValueError('PREPARATION_STATE_DIRECTORY_INVALID')
        if datetime.fromisoformat(saved['expires_at']) > datetime.fromisoformat(saved['created_at'])+timedelta(minutes=30):
            raise ValueError('PREPARATION_VALIDITY_EXCEEDS_EVIDENCE')
        if not datetime.fromisoformat(saved['created_at']) <= clock() < datetime.fromisoformat(saved['expires_at']):
            raise ValueError('PREPARATION_EXPIRED_OR_CLOCK_REVERSED')
        if str(controller.state_dir) != saved['state_directory']:
            raise ValueError('PREPARATION_STATE_DIRECTORY_MISMATCH')
        with audited_lock():
            if any(e.get('hash')==saved['preparation_sha256'] for e in journal.events()):
                raise ValueError('PREPARATION_ALREADY_ATTEMPTED')
            current = scanner(system,now=clock(),package_cache=saved['package_cache'])
            fresh = preparation_plan(current,system=system,services=saved['services'],probes=saved['probes'],
                package_cache=saved['package_cache'],state_dir=saved['state_directory'],now=clock(),package_lock_owned=True)
            if set(saved)!=set(fresh) or fresh['status']=='BLOCKED' or preparation_semantics(fresh)!=preparation_semantics(saved):
                raise ValueError('PREPARATION_INPUT_DRIFT')
            if datetime.fromisoformat(saved['expires_at'])>datetime.fromisoformat(fresh['expires_at']):
                raise ValueError('PREPARATION_VALIDITY_EXCEEDS_EVIDENCE')
            event('PREPARATION_CONFIRMED')
            changed = True  # snapshots/drop-ins are explicitly approved mutations
            materialized = controller.materialize(fresh,system)
            event('CONFIGURATION_SNAPSHOTS_MATERIALIZED', {'roots':[s['root'] for s in materialized['snapshots']]})
            recovery = controller.store.seal({'kind':'owned_configuration_materialization','scope_sha256':saved['scope_sha256'],
                                             'preparation_sha256':saved['preparation_sha256'],'services':saved['services'],**materialized})
            controller.command('daemon-reload')
            controller.verify_loaded_definitions(materialized,system)
            for service in saved['services']:
                controller.command('restart',service)
                controller.wait_stable(service)
                event('SERVICE_RESTARTED',{'service':service})
            # Warm-up is explicit and is not accepted as runtime attribution.
            for target in saved['probes']:
                probe.collect(target['url'],target['script'],secrets.token_hex(32),saved['scope_sha256'])
            after = scanner(system,now=clock(),package_cache=saved['package_cache'])
            if after.inventory.environment.scope_sha256 != saved['scope_sha256'] or digest(static_inputs(after)) != saved['static_inputs_sha256']:
                raise ValueError('PREPARATION_UNEXPECTED_STATIC_INPUT_CHANGE')
            new_ids = {runtime_id(after.inventory,r) for r in after.inventory.runtimes if r.service in saved['services']}
            if not new_ids or new_ids & set(saved['runtime_ids']):
                raise ValueError('PREPARATION_OLD_PROCESS_STILL_PRESENT')
            views = verify_snapshot_views(after,materialized['snapshots'],system)
            if views['status']=='BLOCKED': raise ValueError('PREPARATION_SNAPSHOT_VIEW_FAILED')
            proofs = []
            for target in saved['probes']:
                result = collect_application_evidence(after,system=system,probe=probe,url=target['url'],script_path=target['script'],
                                                       service=target['service'],now=clock(),validity_seconds=1800)
                if result['status']!='VERIFIED_PROCESS_RESPONSE': raise ValueError('PREPARATION_APPLICATION_PROBE_FAILED')
                runtime = next(r for r in after.inventory.runtimes if r.pid==result['peer_pid'])
                if target['pool_listener'] is not None and target['pool_listener'] not in {e.path for e in runtime.endpoints}:
                    raise ValueError('PREPARATION_REQUEST_POOL_MISMATCH')
                proofs.append({**target,'runtime_id':result['runtime_id'],'receipt_sha256':result['receipt_sha256'],
                               'configuration':result['configuration'],'expires_at':result['expires_at']})
            expires = min([datetime.fromisoformat(saved['expires_at']),*[datetime.fromisoformat(p['expires_at']) for p in proofs]])
            if clock()>=expires: raise ValueError('PREPARATION_PROOF_EXPIRED')
            payload = {'kind':'controlled_startup','scope_sha256':saved['scope_sha256'],'prepared_at':clock().isoformat(),
                'expires_at':expires.isoformat(),'preparation_sha256':saved['preparation_sha256'],'services':saved['services'],
                'state_sha256':state_digest(after,stable_bindings(after)), 'static_inputs_sha256':digest(static_inputs(after)),
                'runtime_ids':sorted(new_ids),'probes':proofs,**materialized,'status':'VERIFIED_CONTROLLED_STARTUP',
                'claim':'Read-only snapshot input bytes and effective PHP views for declared probes after controlled restart; not global safety.'}
            document = controller.store.seal(payload)
            event('PREPARATION_VERIFIED',{'receipt_sha256':digest(document)})
            return {'status':'VERIFIED_CONTROLLED_STARTUP','changed':True,'receipt':document,'recovery_receipt':recovery,'executable':False}
    except (ValueError, KeyError, TypeError, OSError, ProbeError) as exc:
        reason = str(exc) if isinstance(exc,(ValueError,ProbeError)) and str(exc).startswith(('PREPARATION_','SERVICE_','SNAPSHOT_')) else 'PREPARATION_FAILED:'+type(exc).__name__
        return {'status':'PARTIAL' if changed else 'BLOCKED','changed':changed,'blockers':[reason],
                'owned_materialization':materialized,'recovery_receipt':locals().get('recovery'),
                'audit_write_failed':audit_failed,'executable':False}
