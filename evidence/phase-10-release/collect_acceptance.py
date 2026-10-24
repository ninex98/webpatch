"""Keep bounded acceptance evidence and all downloaded artifact hashes, never packages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

run_id, destination = sys.argv[1:]
output = Path(destination); output.mkdir(parents=True, exist_ok=True)
raw = subprocess.check_output(['gh', 'run', 'view', run_id, '-R', 'ninex98/webpatch', '--json', 'databaseId,headSha,status,conclusion,url,jobs'])
metadata = json.loads(raw)
(output / 'run.json').write_bytes(raw)
assert metadata['status'] == 'completed' and metadata['conclusion'] == 'success'
assert all(j['conclusion'] in {'success', 'skipped'} for j in metadata['jobs'])
root = Path('ci-evidence') / ('release-030-' + run_id)
subprocess.run(['gh', 'run', 'download', run_id, '-R', 'ninex98/webpatch', '-D', str(root)], check=True)
records, kept, junit = {}, {}, {}
selected = {'pytest.xml', 'pytest.log', 'native-result.json', 'native-zh.txt', 'result.json',
            'package-build.log', 'SHA256SUMS', 'execution-entry.json', 'wrong-confirmation.json',
            'repeated-confirmation.json', 'installed-docker-report.json', 'image.json', 'guest-image.json'}
for path in sorted(root.rglob('*')):
    if not path.is_file(): continue
    rel = str(path.relative_to(root))
    records[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.name == 'pytest.xml':
        suites = ET.parse(path).getroot()
        suite = suites if suites.tag == 'testsuite' else suites.find('testsuite')
        assert suite is not None
        assert all(suite.attrib.get(k, '0') == '0' for k in ('failures', 'errors', 'skipped'))
        junit[rel] = dict(suite.attrib)
    if path.name in selected and path.stat().st_size < 200000:
        target = output / 'artifacts' / rel.replace('ci-evidence/', 'results/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        kept[rel] = str(target.relative_to(output))
(output / 'validation.json').write_text(json.dumps({'status':'PASS','commit':metadata['headSha'],
    'jobs':len(metadata['jobs']),'junit':junit,'artifact_sha256':records,'retained':kept},indent=2)+'\n')
print(json.dumps({'status':'PASS','run':run_id,'jobs':len(metadata['jobs']),'junit':junit}))
