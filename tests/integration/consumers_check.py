"""Native file consumers in a hosted VM; helper only maps benign existing bytes."""
import json
import os
from pathlib import Path
import subprocess
import sys

from webpatch.consumers import census
from webpatch.service import scan
from webpatch.system import LocalSystem

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
name, cache = sys.argv[1:]
reader = LocalSystem()
report = scan(reader, package_cache=cache)
package = next(p for p in report.inventory.packages if p.name.split(':')[0] == name)
# A short census may observe unrelated PID churn. Keep every failed attempt;
# retry only the observation, never suppress the unknown reason.
attempts = []
for _ in range(3):
    result = census(report, system=reader, package_ids=[package.id])
    attempts.append(result)
    if result['status'] == 'VERIFIED_ACTIVE_MAPPING_CENSUS': break
Path('ci-evidence/consumer-census.json').write_text(json.dumps({'attempts':attempts},indent=2)+'\n')
assert result['status'] == 'VERIFIED_ACTIVE_MAPPING_CENSUS', result['blockers']
identity = next(i for i in report.package_trust['installed'] if i['package_id'] == package.id)
path = next(p for p in identity['files'] if p.endswith('.so') or p.startswith('/usr/sbin/php-fpm'))
helper = '''import ctypes,mmap,sys
ctypes.CDLL(None).prctl(15,b"mapped-reader",0,0,0)
f=open(sys.argv[1],"rb")
m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
print("ready",flush=True)
sys.stdin.buffer.read(1)
'''
child = subprocess.Popen([sys.executable,'-c',helper,path], stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
try:
    assert child.stdout.readline().strip() == 'ready'
    negative = census(report, system=reader, package_ids=[package.id])
    assert negative['status'] == 'BLOCKED'
    assert 'CONSUMER_NOT_ACCOUNTED:' + str(child.pid) in negative['blockers']
    assert any(c['pid'] == child.pid for c in negative['consumers'])
    Path('ci-evidence/consumer-negative.json').write_text(json.dumps(negative,indent=2)+'\n')
finally:
    child.terminate()
    child.wait(timeout=10)
    child.stdin.close()
    child.stdout.close()
print('PASS: root process census covers active package mappings; renamed extra mapped-file holder blocks coverage.')
