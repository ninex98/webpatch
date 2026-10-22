"""Real solver against an isolated, explicitly synthetic older status snapshot.

No old PHP binary is installed and the host dpkg database is never changed.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from webpatch.apt import LocalAptSimulator
from webpatch.planning import parse_simulation
from webpatch.sources import paragraphs

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
status = Path('/var/lib/dpkg/status').read_text()
records = paragraphs(status)
package = next(r for r in records if r['Package'] == sys.argv[1])
branch = re.search(r'php[0-9]+\.[0-9]+', package['Package'])[0]
changed = {package['Package'], branch + '-common'}
old = package['Version'].rsplit('.', 1)
assert old[-1].isdigit() and int(old[-1]) > 0
older_version = old[0] + '.' + str(int(old[-1]) - 1)
stanzas = []
for stanza in status.split('\n\n'):
    if any(stanza.startswith('Package: ' + name + '\n') for name in changed):
        stanza = re.sub(r'^Version: .+$', 'Version: ' + older_version, stanza, flags=re.M)
    stanzas.append(stanza)
with tempfile.TemporaryDirectory(prefix='webpatch-synthetic-apt-state-') as directory:
    snapshot = Path(directory) / 'status'
    snapshot.write_text('\n\n'.join(stanzas))
    class SnapshotSimulator(LocalAptSimulator):
        def _configuration(self, root):
            return super()._configuration(root).replace('"/var/lib/dpkg/status"', '"' + str(snapshot) + '"')
    result = SnapshotSimulator().simulate((f"{package['Package']}:{package['Architecture']}={package['Version']}",))
    assert result.result.returncode == 0, result.result.stderr
    changes = parse_simulation(result.result.stdout)
    assert changed <= {c.name for c in changes}, (changed, changes, result.result.stdout)
    assert all(c.operation == 'UPGRADE' for c in changes)
    record = {'result': 'PASS', 'scope': 'REAL_APT_SYNTHETIC_STATUS_ONLY_NO_BINARY_DOWNGRADE',
              'status_sha256': hashlib.sha256(status.encode()).hexdigest(),
              'synthetic_status_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
              'simulation': asdict(result), 'changes': [asdict(c) for c in changes]}
assert Path('/var/lib/dpkg/status').read_text() == status
Path('ci-evidence/apt-synthetic-upgrade.json').write_text(json.dumps(record, indent=2) + '\n')
