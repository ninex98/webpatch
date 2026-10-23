"""Real controlled startup, only after read-only invariants on a disposable VM."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile

from webpatch.application import LocalApplicationProbe
from webpatch.planning import digest
from webpatch.platform_proof import service_packages
from webpatch.preparation import preparation_plan, execute_preparation, verify_snapshot_views
from webpatch.prepared_verification import verify_prepared_scope
from webpatch.service import scan
from webpatch.service_control import LocalServiceControl
from webpatch.system import LocalSystem,DPKG_QUERY
from webpatch.transaction import AuditJournal
from webpatch.apt import LocalAptSimulator
from webpatch.repair_policy import build_repair_review
from fixture_services import isolate_service

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
package_name, service, port, cache = sys.argv[1:]
# This is a separate, explicit maintenance fixture AFTER all readonly invariants
# in ci_vm_smoke.sh. The product never performs this configuration cleanup.
backup=Path(tempfile.mkdtemp(prefix='webpatch-managed-apt-fixture-'))
custom_tool=Path('/usr/local/bin/phpunit')
if custom_tool.exists():
    Path('ci-evidence/managed-custom-tool.json').write_text(json.dumps({'path':str(custom_tool),
        'sha256':hashlib.sha256(custom_tool.read_bytes()).hexdigest(),
        'action':'Relocated unverified custom tool before the plain official-package fixture'},indent=2)+'\n')
    shutil.move(custom_tool,backup/'custom-phpunit')
paths=[Path('/etc/apt/preferences'),Path('/etc/apt/apt.conf')]
for directory in ('/etc/apt/preferences.d','/etc/apt/apt.conf.d'):
    paths += [p for p in Path(directory).iterdir() if re.fullmatch(r'[A-Za-z0-9_-]+(?:\.conf)?',p.name)]
relocated=[]
for index,path in enumerate(paths):
    if not path.exists(): continue
    relocated.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    shutil.move(path,backup/(str(index)+'-'+path.name))
Path('ci-evidence/managed-apt-fixture.json').write_text(json.dumps(relocated,indent=2)+'\n')
source_cohort=re.search(r'php[0-9]+\.[0-9]+',package_name)[0]
before_rows=[line.split('\t') for line in subprocess.check_output(DPKG_QUERY,text=True).splitlines()]
cohort=[r[0] for r in before_rows if len(r)==6 and r[3]==source_cohort and r[5]=='install ok installed']
assert cohort and all(re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?',n) for n in cohort)
Path('ci-evidence/managed-package-baseline.json').write_text(json.dumps({
    'source_cohort':source_cohort,'before':[r for r in before_rows if r[0] in cohort or r[0] in {'libc-bin','man-db'}],
    'fixture_action':'Install current official cohort and reinstall its payloads plus libc-bin/man-db before evidence collection'},indent=2)+'\n')
subprocess.run(['/usr/bin/apt-get','install','--reinstall','-y','libc-bin','man-db',*cohort],check=True,
               env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C','DEBIAN_FRONTEND':'noninteractive'})
Path('ci-evidence/managed-service-baseline.json').write_text(json.dumps(isolate_service(service,source_cohort),indent=2)+'\n')
reader=LocalSystem()
initial=scan(reader,package_cache=cache)
required={p.split(':')[0] for r in initial.inventory.runtimes if r.service==service for p in r.package_ids}
required.update(service_packages(service)[0])
required.update(p.name.split(':')[0] for p in initial.inventory.packages if p.source_name==source_cohort)
required.update({'libc-bin','man-db'})
metadata=subprocess.check_output(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Version}\n'],text=True)
packages={line.split('\t')[0].split(':')[0]:line.split('\t') for line in metadata.splitlines()}
for name in sorted(required):
    installed,version=packages[name]
    subprocess.run(['/usr/bin/apt-get','download',installed+'='+version],cwd=cache,check=True,
                   env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C'})
report=scan(reader,package_cache=cache)
branch=source_cohort[3:]
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
    reviews=[]
    for attempt in range(3):
        current=scan(reader,package_cache=cache)
        review=build_repair_review(current,system=reader,simulator=LocalAptSimulator(),controller=controller,
            probe=LocalApplicationProbe(),startup_receipt=result['receipt'],source_cohort=source_cohort,
            package_cache=cache,budget_seconds=600)
        document=review.document(); reviews.append({'attempt':attempt+1,'status':review.proposal.status,'blockers':review.proposal.blockers})
        Path(f'ci-evidence/repair-review-{attempt+1}.json').write_text(json.dumps(document,indent=2)+'\n')
        if review.proposal.status=='NO_PACKAGE_CHANGES': break
        # Every attempt is retained; only transient observation drift is retried.
        retry_prefixes=('CONSUMER_PROCESS_','PREPARED_FRESH_REQUEST_FAILED','REPAIR_REQUIREMENT_NOT_MET:input_stability',
                        'REPAIR_REQUIREMENT_NOT_MET:diagnostic_simulation','MAINTENANCE_INPUT_STATE_DRIFT',
                        'AUTHENTICATED_MAINTENANCE_REVIEW_REQUIRED')
        if any(not b.startswith(retry_prefixes) for b in review.proposal.blockers): break
    Path('ci-evidence/repair-review-attempts.json').write_text(json.dumps(reviews,indent=2)+'\n')
    assert review.proposal.status=='NO_PACKAGE_CHANGES',review.proposal.blockers
    assert review.proposal.admission_status=='BLOCKED' and not review.proposal.executable
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
