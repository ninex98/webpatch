"""State-machine fixtures; these do not establish real execution admission."""
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import timedelta
import json

import pytest

from conftest import NOW
from test_planning import setup_plan
from webpatch.models import ReviewGate
from webpatch.planning import plan, digest
from webpatch.transaction import REQUIRED_GATES, StepResult, AuditJournal, execute


def ready_fixture():
    fake, report, simulator = setup_plan()
    original = plan(report, system=fake, simulator=simulator, now=NOW)
    gates = tuple(ReviewGate(name, name, 'PASS', (), (), 'Fixture-provided prerequisite', 'Already satisfied in this injected state-machine fixture') for name in sorted(REQUIRED_GATES))
    impacts = tuple(replace(i, completeness='VERIFIED_WITHIN_DECLARED_SCOPE') for i in original.scope.impacts)
    value = replace(original, gates=gates, coverage=(), blockers=(), admission_status='READY_FOR_CONFIRMATION',
                    scope=replace(original.scope, impacts=impacts), services=('php8.1-fpm.service',), plan_sha256='')
    return replace(value, plan_sha256=digest(asdict(value)))


def seal(proposal):
    return replace(proposal, plan_sha256=digest(asdict(replace(proposal, plan_sha256=''))))


class Backend:
    def __init__(self, failure=None):
        self.calls, self.failure, self.owns_lock = [], failure, False

    @contextmanager
    def locked(self):
        self.calls.append('lock')
        if self.failure == 'lock': raise OSError('private secret that must not appear')
        self.owns_lock = True
        try: yield
        finally:
            self.owns_lock = False
            self.calls.append('unlock')

    def revalidate(self, proposal):
        assert self.owns_lock
        self.calls.append('revalidate')
        return self.failure != 'drift'

    def install(self, targets):
        assert self.owns_lock
        self.calls.append('install')
        if self.failure == 'install-exception': raise RuntimeError('sensitive hook stdout')
        return StepResult(self.failure not in {'install-clean','install-partial'}, self.failure != 'install-clean', 'a'*64)

    def restart(self, service):
        assert self.owns_lock
        self.calls.append('restart:' + service)
        if self.failure == 'restart-exception': raise RuntimeError('sensitive restart output')
        return StepResult(self.failure != 'restart', True, 'b'*64)

    def verify(self, proposal):
        assert self.owns_lock
        self.calls.append('verify')
        return StepResult(self.failure != 'health', False, 'c'*64)


def test_typed_success_is_confirmed_revalidated_and_audited_under_lock(tmp_path):
    proposal = ready_fixture()
    backend, journal = Backend(), AuditJournal(tmp_path/'audit.jsonl')
    result = execute(proposal, confirmation_sha256=proposal.plan_sha256, backend=backend, journal=journal, clock=lambda:NOW)
    assert result['status'] == 'VERIFIED_WITHIN_DECLARED_SCOPE'
    assert backend.calls == ['lock','revalidate','install','restart:php8.1-fpm.service','verify','unlock']
    assert journal.events()[-1]['state'] == 'VERIFIED_WITHIN_DECLARED_SCOPE'
    backend.calls.clear()
    repeated = execute(proposal, confirmation_sha256=proposal.plan_sha256, backend=backend, journal=journal, clock=lambda:NOW)
    assert repeated['status'] == 'BLOCKED' and 'install' not in backend.calls


@pytest.mark.parametrize('mutation', ['hash','confirmation','expired','missing-gate','unknown-gate','unknown-impact','blocked-plan','saved-actions'])
def test_missing_proof_or_exact_confirmation_never_reaches_backend(mutation, tmp_path):
    proposal = ready_fixture()
    confirmation, now = proposal.plan_sha256, NOW
    if mutation == 'hash': proposal = replace(proposal, services=('apache2.service',))
    if mutation == 'confirmation': confirmation = 'f'*64
    if mutation == 'expired': now += timedelta(minutes=31)
    if mutation == 'missing-gate': proposal = seal(replace(proposal, gates=proposal.gates[1:]))
    if mutation == 'unknown-gate': proposal = seal(replace(proposal, gates=(replace(proposal.gates[0], status='UNKNOWN'),*proposal.gates[1:])))
    if mutation == 'unknown-impact': proposal = seal(replace(proposal, scope=replace(proposal.scope, impacts=(replace(proposal.scope.impacts[0],completeness='UNKNOWN'),))))
    if mutation == 'blocked-plan': proposal = seal(replace(proposal, admission_status='BLOCKED'))
    if mutation == 'saved-actions': proposal = seal(replace(proposal, actions=('/bin/sh malicious',)))
    if mutation not in {'confirmation','hash'}: confirmation = proposal.plan_sha256
    backend, journal = Backend(), AuditJournal(tmp_path/'audit.jsonl')
    result = execute(proposal, confirmation_sha256=confirmation, backend=backend, journal=journal, clock=lambda:now)
    assert result['status'] == 'BLOCKED' and not backend.calls and not journal.path.exists()


@pytest.mark.parametrize('failure,status', [('lock','FAILED'),('drift','BLOCKED'),('install-clean','FAILED'),
    ('install-partial','PARTIAL'),('install-exception','PARTIAL'),('restart','RESTART_REQUIRED'),
    ('restart-exception','PARTIAL'),('health','PARTIAL')])
def test_failures_stop_transaction_and_never_claim_rollback_or_health(failure, status, tmp_path):
    proposal = ready_fixture()
    backend, journal = Backend(failure), AuditJournal(tmp_path/'audit.jsonl')
    result = execute(proposal, confirmation_sha256=proposal.plan_sha256, backend=backend, journal=journal, clock=lambda:NOW)
    assert result['status'] == status
    if failure != 'health': assert 'verify' not in backend.calls
    if failure in {'lock','drift'}: assert 'install' not in backend.calls
    text = json.dumps(result) + (journal.path.read_text() if journal.path.exists() else '')
    assert 'sensitive' not in text and 'private secret' not in text
    assert all('rollback' not in call for call in backend.calls)
    if failure == 'lock': assert not journal.path.exists()


def test_audit_failure_before_mutation_prevents_install(tmp_path):
    proposal, backend = ready_fixture(), Backend()
    class BrokenJournal:
        def events(self): return []
        def append(self,event): raise OSError('disk full')
    result = execute(proposal, confirmation_sha256=proposal.plan_sha256, backend=backend, journal=BrokenJournal(), clock=lambda:NOW)
    assert result['status'] == 'FAILED' and 'install' not in backend.calls


def test_current_real_planner_output_remains_non_executable(tmp_path):
    fake, report, simulator = setup_plan()
    proposal = plan(report, system=fake, simulator=simulator, now=NOW)
    backend = Backend()
    result = execute(proposal, confirmation_sha256=proposal.plan_sha256, backend=backend,
                     journal=AuditJournal(tmp_path/'audit.jsonl'), clock=lambda:NOW)
    assert result['status'] == 'BLOCKED' and not backend.calls


def test_audit_hash_chain_rejects_tampering_and_permissive_files(tmp_path):
    journal = AuditJournal(tmp_path/'audit.jsonl')
    journal.append({'state':'PRECHECK'})
    journal.append({'state':'ABORTED'})
    assert len(journal.events()) == 2
    content = journal.path.read_text().replace('ABORTED','SUCCESS')
    journal.path.write_text(content)
    with pytest.raises(ValueError, match='JOURNAL_DIGEST'): journal.events()
    journal.path.chmod(0o644)
    with pytest.raises(ValueError, match='JOURNAL_PATH_SIZE_OR_OWNER'): journal.events()
