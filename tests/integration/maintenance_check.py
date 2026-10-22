"""Inspect authenticated control archives in a disposable hosted VM."""
import json
import os
from pathlib import Path
import sys
import tempfile

from webpatch.maintenance import inspect_maintenance
from webpatch.planning import plan
from webpatch.service import scan
from webpatch.system import LocalSystem
from webpatch.apt import LocalAptSimulator

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
name, cache = sys.argv[1:]
reader = LocalSystem()
report = scan(reader, package_cache=cache)
package = next(p for p in report.inventory.packages if p.name.split(':')[0] == name)
proposal = plan(report, system=reader, simulator=LocalAptSimulator(), target_package_ids=[package.id])
result = inspect_maintenance(report, proposal, system=reader, package_cache=cache)
Path('ci-evidence/maintenance-review.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['status'] == 'READY_FOR_MAINTENANCE_REVIEW', result['blockers']
assert all(r['status'] == 'INSPECTED_AUTHENTICATED_ARCHIVE' for r in result['archives'])
assert any('postinst' in r['control_files'] for r in result['archives'])
assert not result['executable'] and result['trigger_cascade'] == 'NOT_PROVEN'
with tempfile.TemporaryDirectory(prefix='webpatch-control-negative-') as directory:
    for source in Path(cache).glob(name + '_*.deb'):
        raw = bytearray(source.read_bytes())
        raw[-1] ^= 1
        (Path(directory) / source.name).write_bytes(raw)
    negative = inspect_maintenance(report, proposal, system=reader, package_cache=directory)
    assert negative['status'] == 'BLOCKED'
    assert any('AUTHENTICATED_CONTROL_ARCHIVE_UNAVAILABLE' in b for b in negative['blockers'])
Path('ci-evidence/maintenance-negative.json').write_text(json.dumps({
    'result':'PASS','test':'modified cached control archive rejected before parsing/execution',
    'blockers':negative['blockers']}, indent=2)+'\n')
print('PASS: exact authenticated maintainer/conffile inventory and modified-archive negative; no scripts executed.')
