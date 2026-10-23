import io
import json
import os
from pathlib import Path

import pytest

from conftest import FakeSystem, NOW
from test_repair_policy import fixture, build
from test_repair_execution import Controller
from test_preparation import Journal
from webpatch.cli import main
from webpatch.guided import run_guided
from webpatch.repair_execution import ManagedRepairBackend
from webpatch.sessions import SessionStore
from webpatch.terminal import Terminal
from webpatch.transaction import StepResult


class Input(io.StringIO):
    def isatty(self): return True


class MemorySession:
    def __init__(self): self.path = Path('/fixture/session'); self.documents = {}; self.created = False
    def create(self): self.created = True; return self
    def write(self, name, document):
        assert name not in self.documents
        self.documents[name] = json.loads(json.dumps(document))
        return str(self.path/name)


def invoke(monkeypatch, answer, *, terminal=True, mutate=None):
    values = fixture(monkeypatch)
    review = build(values)
    document = review.document()
    if mutate: mutate(document)
    values[0].reads['/review.json'] = json.dumps(document)
    session = MemorySession(); controller = Controller(values[0]); stream = io.StringIO()
    result = run_guided(system=values[0], simulator=values[4], controller=controller,
        probe=object(), journal=Journal(), session_factory=lambda: session, ui=Terminal(stream=stream, lang='en'),
        input_stream=(Input if terminal else io.StringIO)(answer(review)),
        package_cache='/var/cache/apt/archives', state_directory='/var/lib/webpatch', review_path='/review.json', now=NOW)
    return result, session, controller, stream.getvalue()


@pytest.mark.parametrize('response', ['y\n', 'yes\n', 'f'*64+'\n', 'abc\n'])
def test_short_generic_or_wrong_confirmation_never_creates_session_or_executes(monkeypatch, response):
    result, session, control, text = invoke(monkeypatch, lambda r: response)
    assert result['status'] == 'BLOCKED' and result['changed'] is False
    assert not control.calls and not session.created
    assert 'Plan SHA256:' in text and 'Budget (seconds):' in text


@pytest.mark.parametrize('response', ['', '\n', 'q\n'])
def test_cancel_or_eof_never_creates_session_or_executes(monkeypatch, response):
    result, session, control, _ = invoke(monkeypatch, lambda r: response)
    assert result['status'] == 'CANCELLED' and not result['changed']
    assert not control.calls and not session.created


def test_noninteractive_input_cannot_confirm_even_with_correct_hash(monkeypatch):
    result, session, control, _ = invoke(monkeypatch, lambda r: r.proposal.plan_sha256+'\n', terminal=False)
    assert result['reasons'] == ['INTERACTIVE_TERMINAL_REQUIRED']
    assert not control.calls and not session.created


def test_exact_confirmed_review_uses_existing_locked_executor_and_retains_results(monkeypatch):
    monkeypatch.setattr(ManagedRepairBackend, 'verify', lambda self, expected: StepResult(True, False, reason='EXPLICIT_TEST_VERIFIER'))
    result, session, control, _ = invoke(monkeypatch, lambda r: r.proposal.plan_sha256+'\n')
    assert result['status'] == 'VERIFIED_WITHIN_DECLARED_SCOPE' and not result['safe']
    assert control.calls[0] == 'lock' and control.calls[-1] == 'unlock'
    assert any(isinstance(c, tuple) and c[0] == 'install' for c in control.calls)
    assert session.documents['review.json']['plan']['plan_sha256'] == result['plan_sha256']
    assert session.documents['result.json']['status'] == result['status']


def test_changed_contract_is_rejected_by_original_executor(monkeypatch):
    result, session, control, _ = invoke(monkeypatch, lambda r: r.proposal.plan_sha256+'\n',
        mutate=lambda d: d['contract'].update(maintenance_budget_seconds=1800))
    assert result['status'] == 'BLOCKED' and not result['changed']
    assert not control.calls


def test_details_are_opt_in_and_do_not_grant_confirmation(monkeypatch):
    result, session, control, text = invoke(monkeypatch, lambda r: 'd\n\n')
    assert 'execution_contract_sha256' in text and 'maintenance_archives' in text
    assert result['status'] == 'CANCELLED' and not control.calls and not session.created


def test_plain_fix_on_empty_inventory_explains_without_writes(capsys):
    assert main(['fix', '--lang', 'zh'], system=FakeSystem({}), now=NOW) == 4
    text = capsys.readouterr().out
    assert '未发现 PHP' in text and '当前清单没有可供修复' in text


def test_fix_dry_run_does_not_construct_session_or_collect_probe(monkeypatch):
    values = fixture(monkeypatch)
    class Forbidden:
        def __getattr__(self, name): raise AssertionError(name)
    result = run_guided(system=values[0], simulator=values[4], controller=Forbidden(), probe=Forbidden(),
        journal=Forbidden(), session_factory=lambda: pytest.fail('write capability used'),
        ui=Terminal(stream=io.StringIO()), input_stream=Forbidden(), package_cache='/var/cache/apt/archives',
        state_directory='/var/lib/webpatch', dry_run=True, now=NOW)
    assert result['status'] == 'BLOCKED' and not result['changed']
    assert result['reasons'] == ['REVIEW_ONLY_NO_CHANGES']


def test_cancellation_after_preparation_retains_receipt_and_reports_changed(monkeypatch):
    values = fixture(monkeypatch); report = values[1]; session = MemorySession(); control = Controller(values[0])
    prep = {'status':'READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION', 'preparation_sha256':'a'*64,
            'actions':['restart declared service'], 'interruption':'Requests will be interrupted.'}
    monkeypatch.setattr('webpatch.guided.preparation_plan', lambda *a, **kw: prep)
    def prepare(*a, **kw):
        assert kw['confirmation_sha256']=='a'*64
        return {'status':'VERIFIED_CONTROLLED_STARTUP','changed':True,'receipt':values[2]}
    monkeypatch.setattr('webpatch.guided.execute_preparation', prepare)
    pools={r.target for r in report.inventory.config_relations if r.kind=='fpm_pool' and r.path.startswith('/etc/php/8.1/fpm/')}
    answers=('http://127.0.0.1:18080/proof.php\n/var/www/proof.php\n'*len(pools))+'a'*64+'\n\n'
    result=run_guided(system=values[0],simulator=values[4],controller=control,probe=object(),journal=Journal(),
        session_factory=lambda:session,ui=Terminal(stream=io.StringIO()),input_stream=Input(answers),
        package_cache='/var/cache/apt/archives',state_directory='/var/lib/webpatch',now=NOW)
    assert result['status']=='CANCELLED' and result['changed'] and result['preparation_changed']
    assert 'startup.json' in session.documents and 'preparation-result.json' in session.documents
    assert not control.calls


def test_private_session_outputs_reject_symlinks_overwrite_and_open_permissions(tmp_path):
    store=SessionStore('/var/lib/webpatch');store.path=tmp_path
    tmp_path.chmod(0o700)
    path=Path(store.write('review.json',{'review':True}))
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError): store.write('review.json',{})
    (tmp_path/'result.json').symlink_to(tmp_path/'outside')
    with pytest.raises(FileExistsError): store.write('result.json',{})
    assert not (tmp_path/'outside').exists()
    with pytest.raises(ValueError): store.write('../escape.json',{})
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError,match='UNTRUSTED'): store.write('startup.json',{})


def test_fix_has_no_yes_bypass_and_rejects_budget_before_reading(capsys):
    fake=FakeSystem({})
    for args in [['fix','--yes'],['fix','--budget-seconds','0']]:
        with pytest.raises(SystemExit): main(args,system=fake,now=NOW)
    assert not fake.calls
