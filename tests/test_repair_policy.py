"""Policy conjunction tests; startup attestation is an explicit injected fact.

Real signatures, mounts, processes and kernel probes have their own native gates.
No fixture claim below is accepted by the public production verifier.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import NOW
from test_execution_inputs import execution_fixture
from test_runtime_evidence import connected_fixture
from test_planning import FakeSimulator,UPGRADE
from test_trust import DEB,INDEX,EXECUTABLE
from webpatch.coverage import runtime_id
from webpatch.planning import digest
from webpatch.repair_policy import build_repair_review,path_overrides,predependency_state
from webpatch.service import scan
from webpatch.system import DPKG_QUERY,CommandResult
from webpatch.transaction import admission_reasons
from webpatch.models import PackageChange,RuntimeHint
from webpatch.cli import main


def fixture(monkeypatch,upgrade=True):
    fake,_=execution_fixture(); runtime=connected_fixture()
    fake.fd_tables=deepcopy(runtime.fd_tables)
    for attr in ('reads','links','identities','fingerprints','commands','dirs'):
        target=getattr(fake,attr)
        for key,value in getattr(runtime,attr).items():
            if (isinstance(key,str) and key.startswith(('/proc','/etc/php','/etc/nginx'))) or (isinstance(key,tuple) and key!=DPKG_QUERY):
                target[key]=deepcopy(value)
    fake.reads['/proc/locks']=''
    fake.fingerprints[EXECUTABLE].update(sha256='c'*64,inode=4,uid=0,mode=0o100755)
    fake.fingerprints['/proc/42/exe']=fake.fingerprints[EXECUTABLE].copy()
    fake.identities['/proc/42/exe']={'device':1,'inode':4}
    fake.reads['/proc/42/maps']=fake.reads['/proc/42/maps'].replace('00:01 5','00:01 4')
    fake.fingerprints['/etc/php/8.1/fpm/php-fpm.conf']={'device':1,'inode':500,'sha256':'a'*64,'size':100}
    fake.reads['/var/lib/dpkg/triggers/File']='/etc/php php8.1-fpm/noawait\n'
    if upgrade:
        old=DEB.replace('.28_','.27_')
        fake.dirs['/var/cache/apt/archives'].append(old.rsplit('/',1)[1])
        fake.archives[old]=deepcopy(fake.archives[DEB])
        fake.archives[old]['control']['Version']='8.1.2-1ubuntu2.27'
        fake.archives[old]['archive_sha256']='d'*64
        fake.fingerprints[old]={**fake.fingerprints[DEB],'sha256':'d'*64,'inode':9}
        row=deepcopy(fake.indexes[INDEX]['packages'][0]); row.update(Version='8.1.2-1ubuntu2.27',SHA256='d'*64,Filename=row['Filename'].replace('.28_','.27_'))
        fake.indexes[INDEX]['packages'].append(row)
        fake.commands[DPKG_QUERY]=replace(fake.commands[DPKG_QUERY],stdout=fake.commands[DPKG_QUERY].stdout.replace('.28','.27'))
        fake.commands[('/usr/bin/dpkg','--compare-versions','8.1.2-1ubuntu2.28','ge','8.1.2-1ubuntu2.27')]=CommandResult(0)
        fake.commands[('/usr/bin/dpkg','--compare-versions','8.1.2-1ubuntu2.27','ge','8.1.2-1ubuntu2.27')]=CommandResult(0)
    report=scan(fake,now=NOW)
    ident=runtime_id(report.inventory,report.inventory.runtimes[0])
    receipt={'payload':{'services':['php8.1-fpm.service'],'runtime_ids':[ident]},'fixture_only':True}
    startup={'status':'VERIFIED_CURRENT_PREPARED_SCOPE','expires_at':(NOW+timedelta(minutes=5)).isoformat(),'blockers':[]}
    monkeypatch.setattr('webpatch.repair_policy.verify_prepared_scope',lambda *args,**kwargs:startup)
    return fake,report,receipt,startup,FakeSimulator(UPGRADE) if upgrade else FakeSimulator()


def build(values,clock=None):
    fake,report,receipt,_,simulator=values
    return build_repair_review(report,system=fake,simulator=simulator,controller=SimpleNamespace(state_dir=Path('/var/lib/webpatch')),
        probe=object(),startup_receipt=receipt,source_cohort='php8.1',package_cache='/var/cache/apt/archives',budget_seconds=300,now=NOW,clock=clock)


def test_ready_review_binds_maintenance_contract_but_keeps_global_unknowns(monkeypatch):
    review=build(fixture(monkeypatch)); document=review.document(); proposal=review.proposal
    assert proposal.admission_status=='READY_FOR_CONFIRMATION',proposal.blockers
    assert not proposal.executable and proposal.schema_version==5
    assert digest(document['contract'])==proposal.execution_contract_sha256
    assert document['evidence']['global_scan_coverage_gaps']
    assert proposal.scope.impacts[0].completeness=='VERIFIED_WITHIN_DECLARED_SCOPE'
    assert admission_reasons(proposal,proposal.plan_sha256,NOW)==()
    assert admission_reasons(proposal,'f'*64,NOW)==('EXACT_PLAN_HASH_CONFIRMATION_REQUIRED',)


def test_no_change_is_not_a_repair_transaction_or_runtime_safe_claim(monkeypatch):
    review=build(fixture(monkeypatch,upgrade=False))
    assert review.proposal.status=='NO_PACKAGE_CHANGES',review.proposal.blockers
    assert review.proposal.admission_status=='BLOCKED' and not review.proposal.executable


def test_unverified_custom_tool_is_named_and_not_assumed_to_be_a_safe_wrapper(monkeypatch):
    values=fixture(monkeypatch)
    values[1].inventory.runtime_hints.append(RuntimeHint('custom','/usr/local/bin/phpunit',None,'host',()))
    review=build(values)
    assert 'REPAIR_CUSTOM_INSTALLATION_UNRESOLVED:/usr/local/bin/phpunit' in review.proposal.blockers


@pytest.mark.parametrize('mutation',['startup','extra-consumer','archive','script','hook','target-diversion','predepends'])
def test_one_unresolved_requirement_prevents_admission(mutation,monkeypatch):
    values=fixture(monkeypatch); fake,report,receipt,startup,_=values
    if mutation=='startup': startup.update(status='BLOCKED',blockers=['PREPARED_RUNTIME_SET_DRIFT'])
    elif mutation=='extra-consumer':
        fake.dirs['/proc'].append('43')
        fake.fd_tables['43']=deepcopy(fake.fd_tables['42'])
        for attr in ('reads','links','identities'):
            target=getattr(fake,attr)
            for path,value in list(target.items()):
                if isinstance(path,str) and path.startswith('/proc/42/'):
                    target[path.replace('/42/','/43/')]=deepcopy(value)
        fake.reads['/proc/43/comm']='hidden-holder'
    elif mutation=='archive': report.package_trust['installed'][0]['status']='UNKNOWN'
    elif mutation=='script': fake.fingerprints['/var/lib/dpkg/info/php8.1-fpm.postinst']['sha256']='f'*64
    elif mutation=='hook': fake.reads['/etc/dpkg/dpkg.cfg']='post-invoke=unknown-program\n'
    elif mutation=='target-diversion': fake.reads['/var/lib/dpkg/diversions']=EXECUTABLE+'\n'+EXECUTABLE+'.old\nlocal\n'
    elif mutation=='predepends': fake.archives[DEB]['control']['Pre-Depends']='unknown-package'
    review=build(values)
    assert review.proposal.status=='BLOCKED' and review.proposal.admission_status=='BLOCKED' and review.proposal.blockers


def test_unrelated_diversion_is_measured_and_target_parent_override_blocks(monkeypatch):
    values=fixture(monkeypatch); fake=values[0]
    fake.reads['/var/lib/dpkg/diversions']='/usr/bin/unrelated\n/usr/bin/unrelated.real\nlocal\n'
    inspection={'archives':[{'roles':['candidate'],'payload_paths':[EXECUTABLE]}]}
    result=path_overrides(inspection,fake)
    assert result['status']=='PASS' and result['unrelated'][0]['disposition']=='OUTSIDE_CHANGED_PACKAGE_PAYLOAD'
    fake.reads['/var/lib/dpkg/diversions']='/usr/sbin\n/opt/sbin\nlocal\n'
    assert path_overrides(inspection,fake)['status']=='BLOCKED'


def test_predependencies_must_already_be_configured_outside_the_change_set(monkeypatch):
    fake=fixture(monkeypatch)[0]
    inspection={'archives':[{'roles':['candidate'],'pre_depends':'php8.1-fpm (>= 8.1.2-1ubuntu2.27)','package_id':'fixture:all'}]}
    proposal=SimpleNamespace(changes=())
    assert predependency_state(inspection,proposal,fake)['status']=='PASS'
    proposal.changes=(PackageChange('UPGRADE','php8.1-fpm','amd64','8.1.2-1ubuntu2.27','8.1.2-1ubuntu2.28'),)
    assert predependency_state(inspection,proposal,fake)['status']=='BLOCKED'
    inspection['archives'][0]['pre_depends']='php8.1-fpm | arbitrary-alternative'
    assert predependency_state(inspection,proposal,fake)['status']=='BLOCKED'


def test_review_cli_requires_explicit_capabilities_for_an_injected_reader(monkeypatch,capsys):
    fake=fixture(monkeypatch)[0]
    result=main(['repair-plan','--prepared-receipt','/tmp/unread.json','--source-cohort','php8.1',
                 '--budget-seconds','300','--refresh-probes'],system=fake,now=NOW)
    assert result==3 and 'ERROR' in capsys.readouterr().err
    assert not any(op=='read_plan_document' for op,_ in fake.calls)


def test_slow_review_must_not_emit_executable_admission_after_expiry(monkeypatch):
    count=0
    def clock():
        nonlocal count
        count+=1
        return NOW if count<4 else NOW+timedelta(minutes=6)
    review=build(fixture(monkeypatch),clock=clock)
    assert review.proposal.admission_status=='BLOCKED'
    assert any(g.category=='collection_freshness' and g.status=='BLOCKED' for g in review.proposal.gates)
