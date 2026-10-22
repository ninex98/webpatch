"""Real Node metadata/process evidence without a vulnerability exploit."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

assert Path('/.dockerenv').is_file() and Path.cwd()==Path('/work')
sys.path.insert(0,'/usr/lib/webpatch')
from webpatch.node_adapter import scan_node
from webpatch.node_rules import NodeRuleProvider
from webpatch.system import LocalSystem

hashes={}
for path in sorted(Path('src/webpatch').rglob('*')):
    if path.suffix in {'.py','.php','.json'}:
        relative=path.relative_to('src')
        assert path.read_bytes()==(Path('/usr/lib/webpatch')/relative).read_bytes()
        hashes[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
for installed,fixed,expected in json.loads(Path('tests/fixtures/node-comparisons.json').read_text()):
    result=subprocess.run(['/usr/bin/dpkg','--compare-versions',installed,'ge',fixed],capture_output=True)
    assert result.returncode in (0,1) and (result.returncode==0)==expected
before=hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
# Deliberately renamed process, no server, no requests, no filesystem writes.
with subprocess.Popen(['/usr/bin/node','-e',"process.title='renamed-worker'; console.log('ready'); setInterval(()=>{},1000)"],
                      stdout=subprocess.PIPE,text=True) as child:
    try:
        assert child.stdout.readline().strip()=='ready'
        result=scan_node(LocalSystem())
        runtime=next(r for r in result.inventory.runtimes if r.pid==child.pid)
        assert runtime.path=='/usr/bin/node' and runtime.start_ticks
        assert runtime.association=='VERIFIED_LOCAL_FILE_ASSOCIATION',runtime.blockers
        assert result.assessments and all(a.version_status!='UNKNOWN' for a in result.assessments)
        assert not result.safe and all(a.runtime_status=='UNKNOWN' for a in result.assessments)
        cli=subprocess.run(['/usr/bin/webpatch','scan-node','--format','json'],capture_output=True,text=True)
        assert cli.returncode in (1,2) and not json.loads(cli.stdout)['safe']
    finally:
        child.terminate(); child.wait(timeout=10)
assert before==hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
print(json.dumps({'result':'PASS','scope':'Node package comparisons and local process evidence only',
    'environment':asdict(result.inventory.environment),'runtime':asdict(runtime),
    'assessments':[asdict(a) for a in result.assessments],'source_sha256':hashes,
    'rule_sha256':NodeRuleProvider().sha256,'state_sha256':before},indent=2))
