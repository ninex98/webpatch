"""Authenticate the package-owned service definition and launcher prerequisites."""
from dataclasses import asdict
import re

from .models import Package
from .planning import digest
from .system import Collector, DPKG_QUERY, definition_command, environment_files_command
from .trust import source_identity


def service_packages(service):
    match = re.fullmatch(r'php([0-9]+\.[0-9]+)-fpm\.service', service)
    if match:
        return (service.removesuffix('.service'),'php-common'), '/usr/sbin/php-fpm' + match[1]
    if service == 'apache2.service':
        return ('apache2','apache2-bin'), '/usr/sbin/apache2'
    raise ValueError('PREPARATION_SERVICE_UNSUPPORTED')


def authenticate_service(report, *, system, service, package_cache, allowed_dropin=None):
    packages, executable = service_packages(service)
    runtimes = [r for r in report.inventory.runtimes if r.service == service]
    packages = tuple(sorted(set(packages) | {p.split(':')[0] for r in runtimes for p in r.package_ids}))
    collector = Collector(system, evidence_prefix='u')
    reasons, archives = [], []
    metadata, _ = collector.probe('run', DPKG_QUERY)
    rows = []
    if metadata and metadata.returncode == 0 and not metadata.stderr:
        rows = [r.split('\t') for r in metadata.stdout.splitlines()]
    names, _ = collector.probe('listdir', package_cache)
    for name in packages:
        installed = [r for r in rows if len(r)==6 and r[0].split(':')[0] == name and r[5] == 'install ok installed']
        if len(installed) != 1:
            reasons.append('SERVICE_PACKAGE_IDENTITY_UNKNOWN:' + name)
            continue
        row = installed[0]
        candidates = [c for c in (report.package_trust or {}).get('candidates', [])
                      if (c['name'],c['version'],c['architecture'],c['source_name'],c['source_version']) == (name,row[1],row[2],row[3],row[4])]
        hashes = {c['sha256'] for c in candidates}
        if len(hashes) != 1:
            reasons.append('SERVICE_ARCHIVE_ORIGIN_UNKNOWN:' + name)
            continue
        found = False
        for filename in [n for n in names or [] if n.startswith(name + '_') and n.endswith('.deb')][:32]:
            path = package_cache.rstrip('/') + '/' + filename
            before, _ = collector.probe('archive_fingerprint', path)
            if not before or before['sha256'] not in hashes or before['size'] not in {c['size'] for c in candidates}:
                continue
            archive, _ = collector.probe('package_archive', (path,before['sha256']))
            after, _ = collector.probe('archive_fingerprint', path)
            if archive is None or archive.get('archive_sha256') != before['sha256'] or before != after:
                continue
            try:
                control = archive['control']
                identity = (control['Package'],control['Version'],control['Architecture'],*source_identity(control))
                if identity != (name,row[1],row[2],row[3],row[4]) or not archive.get('control_metadata_complete'):
                    continue
                archives.append({'package_id':name+':'+row[2], 'archive_sha256':before['sha256'],
                                 'payload_files':archive['payload_files'], 'runtime_files':archive['files'], 'path':path})
                found = True
                break
            except (KeyError, ValueError):
                continue
        if not found:
            reasons.append('SERVICE_AUTHENTICATED_ARCHIVE_UNAVAILABLE:' + name)
    definition, _ = collector.probe('run', definition_command(service))
    props = dict(line.split('=',1) for line in definition.stdout.splitlines() if '=' in line) if definition and not definition.returncode and not definition.stderr else {}
    # systemctl's structured-array renderer emits no line for an empty
    # EnvironmentFiles even with --all. Query its typed D-Bus value explicitly.
    environment_files, _ = collector.probe('run', environment_files_command(service))
    if (environment_files is None or environment_files.returncode or environment_files.stderr
            or environment_files.stdout.strip() != 'a(sb) 0'):
        reasons.append('SERVICE_ENVIRONMENT_FILES_NOT_VERIFIED_EMPTY')
    required = {'Id','FragmentPath','DropInPaths','RootDirectory','RootImage','PassEnvironment'}
    if not required <= props.keys() or props.get('Id') != service:
        reasons.append('SERVICE_DEFINITION_UNREADABLE')
    if (props.get('DropInPaths') not in {'', allowed_dropin}
            or any(props.get(k) for k in ('EnvironmentFiles','RootDirectory','RootImage','PassEnvironment'))):
        reasons.append('CUSTOM_SERVICE_DEFINITION_UNSUPPORTED')
    fragment = props.get('FragmentPath','')
    if fragment not in {'/lib/systemd/system/'+service, '/usr/lib/systemd/system/'+service}:
        reasons.append('SERVICE_FRAGMENT_PATH_UNSUPPORTED')
    payload = {}
    for archive in archives:
        for path, value in archive['payload_files'].items():
            if path in payload and payload[path] != value:
                reasons.append('SERVICE_PAYLOAD_CONFLICT')
            payload[path] = value
    checks = []
    required_paths = {fragment, executable, *(['/etc/apache2/envvars'] if service == 'apache2.service' else [])}
    required_paths.update(f.path for r in runtimes for f in r.files)
    required_paths.update(path for archive in archives for path in archive['runtime_files'])
    for path in sorted(required_paths):
        if not path or not path.startswith('/'):
            continue
        expected = payload.get(path)
        if path.startswith('/lib/systemd/'):
            expected = expected or payload.get('/usr' + path)
        elif path.startswith('/usr/lib/systemd/'):
            expected = expected or payload.get(path[4:])
        actual, ident = collector.probe('fingerprint', path)
        verified = (expected is not None and actual is not None and actual['sha256'] == expected
                    and actual.get('uid') == 0 and not actual.get('mode',0) & 0o022)
        checks.append({'path':path,'expected_sha256':expected,'observed_sha256':actual.get('sha256') if actual else None,
                       'status':'VERIFIED_PACKAGE_FILE' if verified else 'UNKNOWN','evidence_id':ident})
        if not verified:
            reasons.append('SERVICE_FILE_IDENTITY_UNKNOWN:' + path)
    unit_source = None
    unit_check = next((f for f in checks if f['path']==fragment and f['status']=='VERIFIED_PACKAGE_FILE'),None)
    if unit_check:
        raw, _ = collector.probe('read_text',fragment)
        import hashlib
        if raw is not None and hashlib.sha256(raw.encode()).hexdigest()==unit_check['expected_sha256']:
            unit_source = {'path':fragment,'sha256':unit_check['expected_sha256'],'content':raw}
        else:
            reasons.append('SERVICE_DEFINITION_CHANGED_DURING_READ')
    result = {'service':service, 'status':'AUTHENTICATED_SERVICE_DEFINITION' if not reasons else 'BLOCKED',
              'blockers':sorted(set(reasons)), 'files':checks,
              'definition_sha256':digest(props), 'archives':[{k:v for k,v in a.items() if k not in {'payload_files','runtime_files'}} for a in archives],
              'unit_source':unit_source,
              'observed_property_names':sorted(props),
              'evidence':[asdict(e) for e in collector.evidence], 'proof_sha256':''}
    result['proof_sha256'] = digest(result)
    return result
