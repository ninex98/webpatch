"""2D observations/negative cases, exclusively on a disposable hosted VM.

The mmap helper is benign data, not PHP code or a vulnerability exploit.
Configuration mutations are restored; no WebPatch repair is performed.
"""
import ctypes
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from webpatch.service import scan
from webpatch.system import LocalSystem

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
package, sapi, pid, cache = sys.argv[1:]
pid = int(pid)
record = json.loads(Path('ci-evidence/vm-root-scan.json').read_text())
runtime = next(r for r in record['inventory']['runtimes'] if r['pid'] == pid)
checks = record['inventory']['coverage']
assert any(c['requirement'] == 'runtime_file_identity' and c['status'] == 'VERIFIED'
           and any(s['kind'] == 'package' and s['id'].split(':')[0] == package for s in c['subjects']) for c in checks)
assert runtime['mapping_status'] == 'OBSERVED', runtime
assert any(c['requirement'] == 'configured_runtime_link' and any(s['kind'] == 'runtime' for s in c['subjects']) for c in checks)
assert all(c['status'] == 'UNKNOWN' for c in checks if c['requirement'] == 'loaded_configuration')
assert all(c['status'] == 'NOT_CHECKED' for c in checks if c['requirement'] == 'request_attribution')
if sapi == 'fpm':
    assert runtime['endpoints'], runtime
    assert any(c['requirement'] == 'process_unix_listener' and c['status'] == 'VERIFIED' for c in checks)
else:
    assert any(f['role'] == 'php_module' and '/libphp' in f['path'] for f in runtime['files'])

# Real unprivileged reads are allowed to be incomplete, never promoted to safety.
unprivileged = json.loads(Path('ci-evidence/vm-scan.json').read_text())
assert not unprivileged['safe']
negative = {'unprivileged_safe': unprivileged['safe'], 'cases': []}
branch = '8.1' if record['inventory']['environment']['codename'] == 'jammy' else '8.3'
config = Path(f'/etc/php/{branch}/{"fpm" if sapi == "fpm" else "apache2"}/php.ini')
original = config.read_bytes()
try:
    config.write_bytes(original + b'\n; webpatch disposable VM drift fixture\n')
    changed = scan(LocalSystem(), package_cache=cache)
    before = next(e for e in record['evidence'] if e['target'] == str(config) and e['operation'] == 'read_text')
    after = next(e for e in changed.evidence if e.target == str(config) and e.operation == 'read_text')
    assert before['sha256'] != after.sha256
    assert config.read_bytes() == original + b'\n; webpatch disposable VM drift fixture\n'
    assert all(c.status == 'UNKNOWN' for c in changed.inventory.coverage if c.requirement == 'loaded_configuration')
    negative['cases'].append({'case': 'configuration_changed_without_restart', 'result': 'PASS',
                              'before_sha256': before['sha256'], 'after_sha256': after.sha256,
                              'loaded_configuration': 'UNKNOWN'})
finally:
    config.write_bytes(original)

# A real process holds a mapped regular file; deleting/replacing the path must
# never turn its disk metadata into a verified loaded module identity.
helper = '''import ctypes,mmap,sys,time
ctypes.CDLL(None).prctl(15, b"php-fixture", 0, 0, 0)
f=open(sys.argv[1],"rb")
m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
print("ready",flush=True)
time.sleep(90)
'''
with tempfile.TemporaryDirectory(prefix='webpatch-runtime-negative-') as directory:
    for fault in ('deleted', 'replaced'):
        path = Path(directory) / 'libphp-fixture.so'
        path.write_bytes(b'benign-map-data\n' * 256)
        child = subprocess.Popen([sys.executable, '-c', helper, str(path)], stdout=subprocess.PIPE, text=True)
        try:
            assert child.stdout.readline().strip() == 'ready'
            path.unlink()
            if fault == 'replaced': path.write_bytes(b'new-benign-data\n' * 256)
            result = scan(LocalSystem(), package_cache=cache)
            instance = next(r for r in result.inventory.runtimes if r.pid == child.pid)
            assert instance.association == 'UNKNOWN'
            # Linux appends (deleted) to both cases while the old inode is mapped.
            assert 'DELETED_PHP_MAPPING' in instance.blockers, instance
            assert not result.safe
            negative['cases'].append({'case': fault + '_mapped_file', 'result': 'PASS', 'runtime': asdict(instance)})
        finally:
            child.terminate()
            child.wait(timeout=10)
assert config.read_bytes() == original
negative.update(result='PASS', observed_at=datetime.now(timezone.utc).isoformat(),
                config_restored_sha256=hashlib.sha256(original).hexdigest(),
                boundaries=['No request attribution', 'No loaded configuration proof', 'No repair'])
Path('ci-evidence/runtime-negative.json').write_text(json.dumps(negative, indent=2) + '\n')
print('PASS: real mapping faults and static configuration drift remain UNKNOWN; no repair.')
