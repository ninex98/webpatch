from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path

import pytest

from conftest import NOW
from test_repair_policy import fixture,build
from test_preparation import Journal
from webpatch.planning import digest,lock_blockers
from webpatch.repair_execution import decode_plan,execute_repair_review,ManagedRepairBackend
from webpatch.system import Collector
from webpatch.transaction import StepResult


class Controller:
    state_dir=Path('/var/lib/webpatch')
    def __init__(self,fake): self.fake=fake; self.owns_package_lock=False; self.calls=[]
    def frontend_lock_identity(self):
        return {'path':'/var/lib/dpkg/lock-frontend','device':1,'inode':77,'pid':os.getpid()}
    @contextmanager
    def locked(self):
        self.calls.append('lock'); self.owns_package_lock=True
        self.fake.identities['/var/lib/dpkg/lock-frontend']={'device':1,'inode':77}
        self.fake.reads['/proc/locks']=f'1: POSIX ADVISORY WRITE {os.getpid()} 00:01:77 0 EOF\n'
        try: yield
        finally:
            self.owns_package_lock=False; self.fake.reads['/proc/locks']=''; self.calls.append('unlock')
    def install_operation(self,operation,system):
        self.calls.append(('install',operation))
        return StepResult(True,True,reason='INJECTED_PACKAGE_SUCCESS')
    def command(self,action,service,**kwargs): self.calls.append((action,service))
    def wait_stable(self,service,**kwargs): pass
    def verify_loaded_definitions(self,body,system): self.calls.append('definitions')


def test_saved_schema_is_typed_and_unknown_fields_are_rejected(monkeypatch):
    review=build(fixture(monkeypatch)); raw=review.document()['plan']
    assert asdict(decode_plan(raw))==asdict(review.proposal)
    raw['execute_shell']='untrusted'
    with pytest.raises(ValueError,match='SCHEMA'): decode_plan(raw)


def test_only_our_observed_posix_frontend_lock_can_be_excluded(monkeypatch):
    fake=fixture(monkeypatch)[0]; controller=Controller(fake)
    with controller.locked():
        assert lock_blockers(Collector(fake))==['PACKAGE_MANAGER_LOCK_HELD']
        assert lock_blockers(Collector(fake),controller.frontend_lock_identity())==[]
        assert lock_blockers(Collector(fake),{**controller.frontend_lock_identity(),'pid':os.getpid()+1})
        fake.reads['/proc/locks']=''
        assert 'OWNED_PACKAGE_LOCK_NOT_OBSERVED' in lock_blockers(Collector(fake),controller.frontend_lock_identity())


@pytest.mark.parametrize('mutation',['confirmation','contract','evidence','extra-field','source-changed'])
def test_unconfirmed_forged_or_stale_saved_review_never_installs(mutation,monkeypatch):
    values=fixture(monkeypatch); fake=values[0]; review=build(values); saved=review.document()
    controller=Controller(fake); confirmation=review.proposal.plan_sha256
    if mutation=='confirmation': confirmation='f'*64
    if mutation=='contract': saved['contract']['maintenance_budget_seconds']=1800
    if mutation=='evidence': saved['evidence']['global_scan_coverage_gaps']=[]
    if mutation=='extra-field': saved['plan']['unreviewed_action']='anything'
    if mutation=='source-changed': fake.reads['/etc/apt/sources.list']+='\n# changed\n'
    result=execute_repair_review(saved,confirmation_sha256=confirmation,system=fake,simulator=values[4],
        controller=controller,probe=object(),journal=Journal(),clock=lambda:NOW)
    assert result['status'] in {'BLOCKED','FAILED'}
    assert not any(isinstance(c,tuple) and c[0]=='install' for c in controller.calls)


def test_exact_review_is_recomputed_under_lock_and_only_typed_archives_are_dispatched(monkeypatch):
    values=fixture(monkeypatch); fake=values[0]; review=build(values); controller=Controller(fake); journal=Journal()
    # This isolates the bridge; actual post-repair runtime verification is not
    # claimed by this injected success result and must pass the native matrix.
    monkeypatch.setattr(ManagedRepairBackend,'verify',lambda self,expected:StepResult(True,False,reason='INJECTED_VERIFIER'))
    result=execute_repair_review(review.document(),confirmation_sha256=review.proposal.plan_sha256,system=fake,
        simulator=values[4],controller=controller,probe=object(),journal=journal,clock=lambda:NOW)
    assert result['status']=='VERIFIED_WITHIN_DECLARED_SCOPE',result
    operation=next(c[1] for c in controller.calls if isinstance(c,tuple) and c[0]=='install')
    assert len(operation.archives)==1 and operation.archives[0].version=='8.1.2-1ubuntu2.28'
    assert operation.transaction_sha256==review.proposal.plan_sha256 and not result['safe']
    repeated=execute_repair_review(review.document(),confirmation_sha256=review.proposal.plan_sha256,system=fake,
        simulator=values[4],controller=controller,probe=object(),journal=journal,clock=lambda:NOW)
    assert repeated['status']=='BLOCKED'


def test_post_verifier_rejects_old_packages_old_processes_and_missing_configuration_proof(monkeypatch):
    values=fixture(monkeypatch); review=build(values); contract=review.document()['contract']
    contract['startup_receipt']['payload'].update(snapshots=[],probes=[])
    backend=ManagedRepairBackend(review.proposal,contract,system=values[0],simulator=values[4],
        controller=Controller(values[0]),probe=object(),clock=lambda:NOW)
    backend.current=review
    result=backend.verify(review.proposal)
    assert not result.success
    reasons=backend.verification['blockers']
    assert 'REPAIR_POST_VENDOR_BOUNDARY_NOT_MET' in reasons
    assert 'REPAIR_POST_RUNTIME_REPLACEMENT_UNVERIFIED' in reasons
    assert 'REPAIR_POST_CONFIGURATION_OR_PROBES_MISSING' in reasons
