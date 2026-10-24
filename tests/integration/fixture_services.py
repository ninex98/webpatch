"""Deliberate single-SAPI matrix setup, never a product scope shortcut."""
import os
import re
import subprocess


def retryable_review_blockers(blockers):
    """CI only: retry a fresh pre-execution review on narrow process races."""
    prefixes = ('CONSUMER_PROCESS_DESCRIPTORS_UNREADABLE:',
                'CONSUMER_PROCESS_UNSTABLE_OR_UNREADABLE:',
                'CONSUMER_PROCESS_DESCRIPTORS_CHANGED:')
    return bool(blockers) and all(
        b == 'CONSUMER_PROCESS_SET_CHANGED' or b.startswith(prefixes) for b in blockers)


def retryable_observation_abort(result):
    """CI only: a fresh review may follow an unchanged observation-race abort."""
    if (result.get('status')!='BLOCKED' or result.get('changed') is not False
            or list(result.get('reasons',[]))!=['LOCKED_REVALIDATION_FAILED']):
        return False
    blockers=(result.get('revalidation') or {}).get('blockers',[])
    primary=('CONSUMER_PROCESS_DESCRIPTORS_UNREADABLE:','CONSUMER_PROCESS_UNSTABLE_OR_UNREADABLE:',
             'REPAIR_REQUIREMENT_NOT_MET:input_stability')
    secondary=('REPAIR_REQUIREMENT_NOT_MET:dependency_changes','REPAIR_REQUIREMENT_NOT_MET:diagnostic_simulation',
               'REPAIR_REQUIREMENT_NOT_MET:installation_equivalence')
    return bool(blockers) and any(b.startswith(primary) for b in blockers) and all(b.startswith(primary+secondary) for b in blockers)


def isolate_service(service,source):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    assert re.fullmatch(r'php[0-9]+\.[0-9]+',source)
    assert service in {source+'-fpm.service','apache2.service'}
    records=[]
    for unit in (source+'-fpm.service','apache2.service'):
        if unit==service: continue
        state=subprocess.run(['/usr/bin/systemctl','show','--property=LoadState','--value',unit],capture_output=True,text=True,check=True)
        if state.stdout.strip()=='loaded':
            before=subprocess.run(['/usr/bin/systemctl','is-active',unit],capture_output=True,text=True)
            subprocess.run(['/usr/bin/systemctl','stop',unit],check=True)
            records.append({'service':unit,'previous_state':before.stdout.strip(),'fixture_action':'STOP_UNSELECTED_SAPI_BEFORE_EVIDENCE'})
    return records
