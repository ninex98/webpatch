"""Real Debian archive keys/indexes/bytes and tampered-signature rejection."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

assert Path('/.dockerenv').is_file() and Path.cwd()==Path('/work')
sys.path.insert(0,'src')
from webpatch.archive_policy import DEBIAN_KEYS,DEBIAN_KEYRING
from webpatch.service import scan
from webpatch.system import LocalSystem

before=hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
report=scan(LocalSystem(),package_cache='/cache')
assert report.package_trust['status']=='VERIFIED_INDEX_CHAIN',report.package_trust['blockers']
package=next(p for p in report.inventory.packages if p.sapi=='fpm')
identity=next(p for p in report.package_trust['installed'] if p['package_id']==package.id)
assert identity['status']=='AUTHENTICATED_RUNTIME_FILES',identity['blockers']
assert not report.safe
commands=[json.loads(e.target) for e in report.evidence if e.operation=='run' and 'gpgv' in e.target and e.outcome=='EXIT_0']
assert commands and all(c[3]==DEBIAN_KEYRING for c in commands)
raw=Path(commands[0][-1]).read_bytes(); tampered=raw.replace(b'Origin: Debian',b'Origin: Forged',1)
assert tampered!=raw
with tempfile.TemporaryDirectory(prefix='webpatch-debian-negative-') as folder:
    path=Path(folder)/'InRelease';path.write_bytes(tampered)
    negative=subprocess.run([*commands[0][:-1],str(path)],capture_output=True,text=True,timeout=10)
    assert negative.returncode and 'BADSIG' in negative.stdout
assert before==hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
keyring_version=subprocess.check_output(['/usr/bin/dpkg-query','-W','-f=${Version}','debian-archive-keyring'],text=True)
print(json.dumps({'result':'PASS','scope':'Debian read-only archive authentication, not repair certification',
    'environment':asdict(report.inventory.environment),'package':asdict(package),'identity':identity,
    'observed_pinned_signers':sorted({c['signer'] for c in report.package_trust['candidates']}),
    'reviewed_pins':DEBIAN_KEYS[report.inventory.environment.codename],
    'keyring_package_version':keyring_version,'keyring_sha256':hashlib.sha256(Path(DEBIAN_KEYRING).read_bytes()).hexdigest(),
    'tampered_signature':'REJECTED','state_sha256':before,'evidence':[asdict(e) for e in report.evidence]},indent=2))
