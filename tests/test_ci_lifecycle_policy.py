"""The disposable fixture must never retry a changed or unrelated failure."""
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('fixture_services',Path(__file__).parent/'integration/fixture_services.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def observation_abort():
    return {'status':'BLOCKED','changed':False,'reasons':['LOCKED_REVALIDATION_FAILED'],
        'revalidation':{'blockers':['CONSUMER_PROCESS_UNSTABLE_OR_UNREADABLE:42']}}


def test_only_unmodified_observation_race_allows_a_new_fixture_review():
    assert module.retryable_observation_abort(observation_abort())


@pytest.mark.parametrize('mutation',['changed','partial','health','expired','source','no-blockers','dependency-only'])
def test_fixture_does_not_hide_changed_or_unrelated_failure(mutation):
    result=observation_abort()
    if mutation=='changed': result['changed']=True
    elif mutation=='partial': result['status']='PARTIAL'
    elif mutation=='health': result['reasons']=['REPAIR_POST_VERIFICATION_FAILED']
    elif mutation=='expired': result['revalidation']['blockers'].append('PREPARED_RECEIPT_EXPIRED')
    elif mutation=='source': result['revalidation']['blockers'].append('SOURCE_POLICY_UNKNOWN')
    elif mutation=='no-blockers': result['revalidation']['blockers']=[]
    elif mutation=='dependency-only': result['revalidation']['blockers']=['REPAIR_REQUIREMENT_NOT_MET:dependency_changes']
    assert not module.retryable_observation_abort(result)
