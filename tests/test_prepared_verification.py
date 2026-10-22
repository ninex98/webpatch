from copy import deepcopy
from datetime import timedelta
import json

import pytest

from conftest import NOW
from test_preparation import fixture, make_plan, Controller, Probe, Journal
from webpatch.preparation import execute_preparation
from webpatch.prepared_verification import verify_prepared_scope
from webpatch.service import scan
from webpatch.cli import main
from webpatch.planning import digest


def prepared(monkeypatch,tmp_path):
    fake,report,probes=fixture(monkeypatch)
    proposal=make_plan(fake,report,probes)
    controller=Controller(fake,tmp_path)
    result=execute_preparation(proposal,confirmation_sha256=proposal['preparation_sha256'],system=fake,
        controller=controller,probe=Probe(),journal=Journal(),clock=lambda:NOW)
    assert result['status']=='VERIFIED_CONTROLLED_STARTUP',result
    return fake,controller,result['receipt']


def test_signed_startup_requires_current_views_and_new_kernel_requests(monkeypatch,tmp_path):
    fake,controller,receipt=prepared(monkeypatch,tmp_path)
    result=verify_prepared_scope(receipt,scan(fake,now=NOW),system=fake,controller=controller,probe=Probe(),now=NOW)
    assert result['status']=='VERIFIED_CURRENT_PREPARED_SCOPE',result['blockers']
    assert len(result['requests'])==2 and not result['executable']


@pytest.mark.parametrize('mutation',['signature','expired','implementation','scope','static-input','process','mount','effective-settings','ownership-receipt'])
def test_no_saved_receipt_can_override_current_unknowns(mutation,monkeypatch,tmp_path):
    fake,controller,receipt=prepared(monkeypatch,tmp_path)
    body=deepcopy(receipt['payload'])
    if mutation=='signature': receipt['payload']['services']=[]
    elif mutation=='expired': body['expires_at']=(NOW-timedelta(seconds=1)).isoformat()
    elif mutation=='implementation': body['implementation_sha256']='f'*64
    elif mutation=='scope': body['scope_sha256']='f'*64
    elif mutation=='static-input': body['static_inputs_sha256']='f'*64
    elif mutation=='process': fake.reads['/proc/43/stat']=fake.reads['/proc/43/stat'].replace('456','789')
    elif mutation=='mount': fake.reads['/proc/43/mountinfo']=fake.reads['/proc/43/mountinfo'].replace(' ro ',' rw ')
    elif mutation=='effective-settings': body['probes'][0]['configuration']['effective_ini_sha256']='f'*64
    elif mutation=='ownership-receipt': body['kind']='owned_configuration_materialization'
    if mutation!='signature': receipt=controller.store.seal(body)
    result=verify_prepared_scope(receipt,scan(fake,now=NOW),system=fake,controller=controller,probe=Probe(),now=NOW)
    assert result['status']=='BLOCKED' and result['blockers']


def test_cli_verifies_exact_receipt_without_host_capability_fallback(monkeypatch,tmp_path,capsys):
    fake,controller,receipt=prepared(monkeypatch,tmp_path)
    fake.reads['/tmp/startup.json']=json.dumps(receipt)
    argv=['verify-preparation','/tmp/startup.json','--expect-sha256',digest(receipt)]
    assert main(argv,system=fake,service_controller=controller,probe=Probe(),now=NOW)==0
    assert json.loads(capsys.readouterr().out)['status']=='VERIFIED_CURRENT_PREPARED_SCOPE'
    assert main(argv,system=fake,now=NOW)==3
    assert 'ERROR' in capsys.readouterr().err
