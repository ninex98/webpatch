"""Real execution-input audit; negative bytes live only in a private copy."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from webpatch.apt import LocalAptSimulator
from webpatch.execution_inputs import audit_execution_inputs
from webpatch.maintenance import inspect_maintenance
from webpatch.planning import plan
from webpatch.service import scan
from webpatch.system import LocalSystem

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
name,cache=sys.argv[1:]
reader=LocalSystem()
report=scan(reader,package_cache=cache)
package=next(p for p in report.inventory.packages if p.name.split(':')[0]==name)
proposal=plan(report,system=reader,simulator=LocalAptSimulator(),target_package_ids=[package.id])
inspection=inspect_maintenance(report,proposal,system=reader,package_cache=cache)
result=audit_execution_inputs(inspection,system=reader)
Path('ci-evidence/execution-inputs.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['status']=='READY_FOR_EXECUTION_POLICY_REVIEW',result['blockers']
assert all(c['status']=='MATCHES_AUTHENTICATED_CONTROL' for c in result['installed_controls'])
assert not result['executable']
script=next(c['path'] for c in result['installed_controls'] if c['path'].endswith('.postinst') and c['expected_sha256'])
with tempfile.TemporaryDirectory(prefix='webpatch-control-script-negative-') as directory:
    copy=Path(directory)/'postinst'
    shutil.copy2(script,copy)
    with copy.open('ab') as stream: stream.write(b'\n# isolated negative fixture\n')
    class RedirectedControlReader(LocalSystem):
        def archive_fingerprint(self,path):
            return super().archive_fingerprint(str(copy) if path==script else path)
    negative=audit_execution_inputs(inspection,system=RedirectedControlReader())
    assert negative['status']=='BLOCKED'
    assert 'INSTALLED_CONTROL_CHANGED_OR_UNREADABLE:'+script in negative['blockers']
Path('ci-evidence/execution-inputs-negative.json').write_text(json.dumps({
    'result':'PASS','case':'changed isolated copy of real installed script rejected',
    'blockers':negative['blockers']},indent=2)+'\n')
print('PASS: real installed control bytes, dpkg policy and file-trigger candidates audited; isolated changed-script copy rejected.')
