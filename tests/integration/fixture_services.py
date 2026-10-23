"""Deliberate single-SAPI matrix setup, never a product scope shortcut."""
import os
import re
import subprocess


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
