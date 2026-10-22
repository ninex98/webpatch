"""Real official-package upgrade and post-repair failure, disposable hosted VM only.

Old signed base packages create the fixture. No vulnerability exploit is used;
the fixture web listeners are loopback-only. Production entry points never use
the downgrade/reinstall commands in this test setup.
"""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from webpatch.application import LocalApplicationProbe
from webpatch.apt import LocalAptSimulator
from webpatch.package_control import LocalPackageControl
from webpatch.planning import digest
from webpatch.preparation import preparation_plan,execute_preparation
from webpatch.repair_execution import execute_repair_review
from webpatch.repair_policy import build_repair_review
from webpatch.service import scan
from webpatch.system import LocalSystem
from webpatch.transaction import AuditJournal

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
name,service,port,cache=sys.argv[1:]
reader=LocalSystem(); initial=scan(reader,package_cache=cache)
source='php8.1' if initial.inventory.environment.codename=='jammy' else 'php8.3'
packages=[p for p in initial.inventory.packages if p.source_name==source]
assert packages and initial.package_trust['status']=='VERIFIED_INDEX_CHAIN'
base_rows={p.id:[c for c in initial.package_trust['candidates'] if (c['name'],c['architecture'],c['source_name'],c['suite'])
              ==(p.name.split(':')[0],p.architecture,source,initial.inventory.environment.codename)] for p in packages}
common=set.intersection(*({c['version'] for c in rows} for rows in base_rows.values()))
assert len(common)==1,('exact shared official base version required',sorted(common))
base_version=next(iter(common))
old={p.id:next(c for c in base_rows[p.id] if c['version']==base_version) for p in packages}
specs=[p.id+'='+base_version for p in packages]
assert all(reader.run(('/usr/bin/dpkg','--compare-versions',base_version,'ge',p.version)).returncode==1 for p in packages)
subprocess.run(['/usr/bin/apt-get','download',*specs],cwd=cache,check=True)
for key,candidate in old.items():
    matches=[]
    for path in Path(cache).glob(candidate['name']+'_*.deb'):
        if reader.archive_fingerprint(str(path))['sha256']==candidate['sha256']: matches.append(path)
    assert len(matches)==1,key
    archive=reader.package_archive((str(matches[0]),candidate['sha256']))
    assert (archive['control']['Package'],archive['control']['Architecture'],archive['control']['Version'])==(candidate['name'],candidate['architecture'],base_version)
root=Path('ci-evidence/repair-lifecycle'); root.mkdir(exist_ok=True)
(root/'official-base-identities.json').write_text(json.dumps(old,indent=2)+'\n')
probes=[{'service':service,'url':f'http://127.0.0.1:{port}/webpatch-proof.php','script':'/var/www/html/webpatch-proof.php',
         'pool_listener':f'/run/php/{source}-fpm.sock' if service!='apache2.service' else None}]
if service!='apache2.service':
    probes.append({'service':service,'url':f'http://127.0.0.1:{port}/webpatch-extra.php',
                   'script':'/var/www/html/webpatch-extra.php','pool_listener':'/run/php/webpatch-ci-extra.sock'})


class FaultProbe(LocalApplicationProbe):
    failed=False
    def collect(self,url,*args):
        if self.failed:
            url='http://127.0.0.1:9/'+url.rsplit('/',1)[1]
        return super().collect(url,*args)


class FaultControl(LocalPackageControl):
    armed=False
    def command(self,action,service=None,**kwargs):
        result=super().command(action,service,**kwargs)
        if self.armed and action=='restart': capability.failed=True
        return result


for case in ('success','post-health-failure'):
    folder=root/case; folder.mkdir(exist_ok=True)
    # Isolated setup only: reset the fixture to authenticated old base archives.
    subprocess.run(['/usr/bin/apt-get','install','--allow-downgrades','-y',*specs],check=True,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C','DEBIAN_FRONTEND':'noninteractive'})
    controller=FaultControl('/var/lib/webpatch-repair-'+case); capability=FaultProbe()
    controller.command('restart',service); controller.wait_stable(service)
    before=scan(reader,package_cache=cache)
    assert any(a.version_status=='BELOW_VENDOR_FIX' for a in before.assessments)
    prep=preparation_plan(before,system=reader,services=[service],probes=probes,package_cache=cache,state_dir=str(controller.state_dir))
    (folder/'preparation-plan.json').write_text(json.dumps(prep,indent=2)+'\n')
    assert prep['status']=='READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION',prep['blockers']
    journal=AuditJournal(controller.state_dir/'operations.jsonl')
    prepared=execute_preparation(prep,confirmation_sha256=prep['preparation_sha256'],system=reader,
        controller=controller,probe=capability,journal=journal)
    (folder/'preparation-result.json').write_text(json.dumps(prepared,indent=2)+'\n')
    recovery=prepared.get('recovery_receipt')
    try:
        assert prepared['status']=='VERIFIED_CONTROLLED_STARTUP',prepared.get('blockers')
        current=scan(reader,package_cache=cache)
        review=build_repair_review(current,system=reader,simulator=LocalAptSimulator(),controller=controller,probe=capability,
            startup_receipt=prepared['receipt'],source_cohort=source,package_cache=cache,budget_seconds=600)
        document=review.document(); (folder/'repair-plan.json').write_text(json.dumps(document,indent=2)+'\n')
        assert review.proposal.admission_status=='READY_FOR_CONFIRMATION',review.proposal.blockers
        assert review.proposal.changes and all(c.old_version==base_version and c.new_version!=base_version for c in review.proposal.changes)
        denied=execute_repair_review(document,confirmation_sha256='f'*64,system=reader,simulator=LocalAptSimulator(),
            controller=controller,probe=capability,journal=journal)
        assert denied['status']=='BLOCKED' and not denied['changed']
        (folder/'wrong-confirmation.json').write_text(json.dumps(denied,indent=2)+'\n')
        controller.armed=case=='post-health-failure'
        result=execute_repair_review(document,confirmation_sha256=review.proposal.plan_sha256,system=reader,
            simulator=LocalAptSimulator(),controller=controller,probe=capability,journal=journal)
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if case=='success':
            assert result['status']=='VERIFIED_WITHIN_DECLARED_SCOPE',result.get('reasons')
        else:
            assert result['status']=='PARTIAL' and result['changed'],result.get('reasons')
            assert result['verification']['status']=='BLOCKED'
        assert not result['safe']
        after=scan(reader,package_cache=cache)
        assert all(next(p.version for p in after.inventory.packages if p.id==t.name+':'+t.architecture)==t.version for t in review.proposal.targets)
        repeated=execute_repair_review(document,confirmation_sha256=review.proposal.plan_sha256,system=reader,
            simulator=LocalAptSimulator(),controller=controller,probe=capability,journal=journal)
        assert repeated['status']=='BLOCKED'
    finally:
        controller.armed=False; capability.failed=False
        if recovery:
            with controller.locked():
                controller.retire_overrides(controller.store.verify(recovery))
                controller.command('restart',service)
        if journal.path.exists(): (folder/'audit.jsonl').write_bytes(journal.path.read_bytes())
print('PASS: official same-branch base-to-fixed upgrade and real post-restart HTTP failure; exact confirmation, audit and no-retry enforced. No exploit used.')
