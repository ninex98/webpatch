"""Real controlled startup, only after read-only invariants on a disposable VM."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from webpatch.application import LocalApplicationProbe
from webpatch.planning import digest
from webpatch.platform_proof import service_packages
from webpatch.preparation import preparation_plan, execute_preparation, verify_snapshot_views
from webpatch.prepared_verification import verify_prepared_scope
from webpatch.service import scan
from webpatch.service_control import LocalServiceControl
from webpatch.system import LocalSystem
from webpatch.transaction import AuditJournal

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
package_name, service, port, cache = sys.argv[1:]
reader=LocalSystem()
initial=scan(reader,package_cache=cache)
required={p.split(':')[0] for r in initial.inventory.runtimes if r.service==service for p in r.package_ids}
required.update(service_packages(service)[0])
metadata=subprocess.check_output(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Version}\n'],text=True)
packages={line.split('\t')[0].split(':')[0]:line.split('\t') for line in metadata.splitlines()}
for name in sorted(required):
    installed,version=packages[name]
    subprocess.run(['/usr/bin/apt-get','download',installed+'='+version],cwd=cache,check=True,
                   env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C'})
report=scan(reader,package_cache=cache)
branch='8.1' if report.inventory.environment.codename=='jammy' else '8.3'
probes=[{'service':service,'url':f'http://127.0.0.1:{port}/webpatch-proof.php',
         'script':'/var/www/html/webpatch-proof.php','pool_listener':f'/run/php/php{branch}-fpm.sock' if service!='apache2.service' else None}]
if service!='apache2.service':
    probes.append({'service':service,'url':f'http://127.0.0.1:{port}/webpatch-extra.php',
                   'script':'/var/www/html/webpatch-extra.php','pool_listener':'/run/php/webpatch-ci-extra.sock'})
proposal=preparation_plan(report,system=reader,services=[service],probes=probes,package_cache=cache,state_dir='/var/lib/webpatch-ci')
Path('ci-evidence/preparation-plan.json').write_text(json.dumps(proposal,indent=2)+'\n')
assert proposal['status']=='READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION',proposal['blockers']
controller=LocalServiceControl('/var/lib/webpatch-ci')
journal=AuditJournal(controller.state_dir/'operations.jsonl')
result=execute_preparation(proposal,confirmation_sha256=proposal['preparation_sha256'],system=reader,
                            controller=controller,probe=LocalApplicationProbe(),journal=journal)
Path('ci-evidence/preparation-result.json').write_text(json.dumps(result,indent=2)+'\n')
recovery=result.get('recovery_receipt')
try:
    if result['status']!='VERIFIED_CONTROLLED_STARTUP':
        diagnostics=subprocess.run(['/usr/bin/journalctl','--no-pager','-u',service,'-n','60'],capture_output=True,text=True)
        Path('ci-evidence/preparation-service.log').write_text(diagnostics.stdout+diagnostics.stderr)
    assert result['status']=='VERIFIED_CONTROLLED_STARTUP',result.get('blockers')
    body=controller.store.verify(result['receipt'])
    assert body['runtime_ids'] and not set(body['runtime_ids'])&set(proposal['runtime_ids'])
    assert len(body['probes'])==len(probes)
    current=scan(reader,package_cache=cache)
    views=verify_snapshot_views(current,body['snapshots'],reader)
    assert views['status']=='VERIFIED_READONLY_RUNTIME_VIEWS',views['blockers']
    Path('ci-evidence/preparation-views.json').write_text(json.dumps(views,indent=2)+'\n')
    fresh=verify_prepared_scope(result['receipt'],current,system=reader,controller=controller,probe=LocalApplicationProbe())
    Path('ci-evidence/preparation-fresh-verification.json').write_text(json.dumps(fresh,indent=2)+'\n')
    assert fresh['status']=='VERIFIED_CURRENT_PREPARED_SCOPE',fresh['blockers']
    forged=json.loads(json.dumps(result['receipt']))
    forged['payload']['scope_sha256']='f'*64
    try:
        controller.store.verify(forged)
        raise AssertionError('forged preparation accepted')
    except ValueError:
        pass
finally:
    if recovery:
        with controller.locked():
            owned=controller.store.verify(recovery)
            controller.retire_overrides(owned)
            controller.command('restart',service)
    if journal.path.exists():
        # Event log contains hashes and states, never the local signing key.
        Path('ci-evidence/preparation-audit.jsonl').write_bytes(journal.path.read_bytes())
print('PASS: authenticated controlled restart, immutable runtime configuration views, pool attribution and receipt tampering rejection; canonical unit restored.')
