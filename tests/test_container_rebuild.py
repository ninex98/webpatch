from dataclasses import replace
from datetime import timedelta
import json

import pytest

from conftest import NOW, FakeSystem
from webpatch.cli import main
from webpatch.container_rebuild import rebuild_advice
from webpatch.models import RuntimeHint
from webpatch.planning import digest
from webpatch.service import scan

IMAGE='registry.example.invalid/team/php@sha256:'+'a'*64


def report():
    fake=FakeSystem({'docker':True,'packages':[['php8.1-fpm','8.1.2-1ubuntu2.28','amd64','php8.1','8.1.2-1ubuntu2.28','install ok installed']]})
    value=scan(fake,now=NOW)
    value.inventory.environment=replace(value.inventory.environment,scope='container')
    return fake,value


def test_rebuild_advice_keeps_per_cve_constraints_and_deployment_unknown():
    _,value=report()
    result=rebuild_advice(value,image_reference=IMAGE,now=NOW)
    assert result['status']=='ADVISORY_READY',result['blockers']
    assert len(result['vendor_constraints'][0]['requirements'])==2
    assert result['image_identity']=='DECLARED_NOT_AUTHENTICATED_BY_LOCAL_SCAN'
    assert result['build_execution']==result['rollout_execution']=='NOT_RUN'
    assert not result['safe'] and not result['executable'] and not result['automatic_in_place_repair']
    assert digest(dict(result,advice_sha256=''))==result['advice_sha256']


@pytest.mark.parametrize('image',['php:latest','php@sha256:bad','$(touch /tmp/x)@sha256:'+'a'*64,'https://host/php@sha256:'+'a'*64])
def test_mutable_or_command_shaped_image_identifiers_are_rejected(image):
    with pytest.raises(ValueError): rebuild_advice(report()[1],image_reference=image,now=NOW)


@pytest.mark.parametrize('case',['host','empty','custom','expired','unknown-rule'])
def test_unknowns_are_actionable_and_never_turn_into_rebuild_success(case):
    _,value=report(); now=NOW
    if case=='host': value.inventory.environment=replace(value.inventory.environment,scope='host')
    elif case=='empty': value.inventory.packages=[]
    elif case=='custom': value.inventory.runtime_hints.append(RuntimeHint('custom','/opt/php',None,'container',()))
    elif case=='expired': now=NOW+timedelta(days=8)
    elif case=='unknown-rule': value=replace(value,assessments=[replace(a,version_status='UNKNOWN') for a in value.assessments])
    result=rebuild_advice(value,image_reference=IMAGE,now=now)
    assert result['status']=='BLOCKED_ADVICE' and result['blockers'] and not result['safe']


def test_cli_outputs_advice_with_no_build_or_rollout_capability(capsys):
    fake,_=report()
    assert main(['rebuild-plan','--image',IMAGE],system=fake,now=NOW)==4
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='ADVISORY_READY' and result['rollout_execution']=='NOT_RUN'
