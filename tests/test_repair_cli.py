import json

import pytest

from conftest import NOW,FakeSystem
from test_repair_policy import fixture,build
from test_repair_execution import Controller
from test_preparation import Journal
from webpatch.cli import main
from webpatch.documents import load_document
from webpatch.repair_execution import ManagedRepairBackend
from webpatch.transaction import StepResult


def test_pending_certification_and_missing_confirmation_do_not_read_or_mutate(capsys,monkeypatch):
    monkeypatch.setattr('webpatch.release_gate.PUBLIC_REPAIR_ENABLED',False)
    fake=FakeSystem({})
    assert main(['apply','/not-read.json','--confirm-sha256','f'*64],system=fake,now=NOW)==4
    assert fake.calls==[] and 'BLOCKED' in capsys.readouterr().err
    monkeypatch.setattr('webpatch.release_gate.PUBLIC_REPAIR_ENABLED',True)
    assert main(['apply'],system=fake,now=NOW)==4 and fake.calls==[]


@pytest.mark.parametrize('raw',['{"x":1,"x":2}','{"nested":{"x":1,"x":2}}','{"x":NaN}','{"x":Infinity}'])
def test_ambiguous_review_documents_are_rejected(raw):
    with pytest.raises(ValueError): load_document(raw)


@pytest.mark.parametrize('directory',[None,[],12,{'path':'/var/lib/webpatch'}])
def test_invalid_state_directory_is_rejected_before_native_capability_construction(directory,monkeypatch,capsys):
    fake=FakeSystem({});fake.reads['/review.json']=json.dumps({'contract':{'state_directory':directory}})
    monkeypatch.setattr('webpatch.release_gate.PUBLIC_REPAIR_ENABLED',True)
    monkeypatch.setattr('webpatch.cli.LocalSystem',lambda:fake)
    def forbidden(*args): raise AssertionError('Native control constructed for malformed document')
    monkeypatch.setattr('webpatch.cli.LocalPackageControl',forbidden)
    assert main(['apply','/review.json','--confirm-sha256','f'*64])==3
    assert 'ValueError' in capsys.readouterr().err


def test_certified_entry_requires_explicit_injected_capabilities_and_exact_plan(monkeypatch,capsys):
    values=fixture(monkeypatch);fake=values[0];review=build(values);controller=Controller(fake)
    fake.reads['/review.json']=json.dumps(review.document())
    monkeypatch.setattr('webpatch.release_gate.PUBLIC_REPAIR_ENABLED',True)
    args=['apply','/review.json','--confirm-sha256',review.proposal.plan_sha256]
    assert main(args,system=fake,now=NOW)==3
    assert not controller.calls
    capsys.readouterr()
    monkeypatch.setattr(ManagedRepairBackend,'verify',lambda self,expected:StepResult(True,False,reason='INJECTED_VERIFIER'))
    result=main(args,system=fake,simulator=values[4],probe=object(),package_controller=controller,journal=Journal(),now=NOW)
    assert result==0
    output=json.loads(capsys.readouterr().out)
    assert output['status']=='VERIFIED_WITHIN_DECLARED_SCOPE' and not output['safe']
