"""Validate downloaded current-source acceptance, without invoking target systems."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).parent
accepted = root / 'accepted-ci'
metadata = json.loads((accepted / 'run.json').read_text())
manifest = json.loads((accepted / 'ci-manifest.json').read_text())
assert metadata['status'] == 'completed' and metadata['conclusion'] == 'success'
assert len(metadata['jobs']) == 9 and all(j['conclusion'] == 'success' for j in metadata['jobs'])
assert metadata['headSha'] == manifest['commit']
for name, expected in manifest['source_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
checked_artifacts = 0
for name, expected in manifest['artifact_sha256'].items():
    if name.endswith('.deb'):
        continue  # binary artifact digest retained; binaries are not committed
    path = accepted / 'artifacts' / name.replace('ci-evidence/', 'results/')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    checked_artifacts += 1
fixtures = {}
for version in ('3.10', '3.12'):
    path = accepted / 'artifacts' / ('fixtures-' + version) / 'pytest.xml'
    suite = ET.parse(path).getroot().find('testsuite')
    assert suite is not None and all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped'))
    fixtures[version] = int(suite.attrib['tests'])
containers = {}
for cell in ('jammy', 'noble', 'bookworm'):
    base = accepted / 'artifacts' / ('container-' + cell)
    result = json.loads((base / 'docker-result.json').read_text())
    assert result['result'] == 'PASS'
    for name, expected in result['source_sha256'].items():
        assert hashlib.sha256((Path('src') / name).read_bytes()).hexdigest() == expected
    containers[cell] = {'status': 'PASS', 'environment': result['environment'],
                        'image_id': json.loads((base / 'docker-image.json').read_text())[0]['Id']}
vm = {}
for release in ('22.04', '24.04'):
    for sapi in ('fpm', 'apache'):
        cell = 'vm-ubuntu-' + release + '-' + sapi
        base = accepted / 'artifacts' / cell / 'results'
        scan = json.loads((base / 'vm-root-scan.json').read_text())
        plan = json.loads((base / 'vm-root-plan.json').read_text())
        verification = json.loads((base / 'vm-plan-verification.json').read_text())
        negative = json.loads((base / 'runtime-negative.json').read_text())
        before = json.loads((base / 'runtime-processes-before.json').read_text())
        after = json.loads((base / 'runtime-processes-after.json').read_text())
        assert before == after and before
        assert scan['safe'] is False and plan['executable'] is False and plan['admission_status'] == 'BLOCKED'
        assert plan['schema_version'] == 4 and plan['apt_simulation'] == 'PASS' and verification['drift'] == []
        assert negative['result'] == 'PASS' and len(negative['cases']) == 3
        assert all(case['result'] == 'PASS' for case in negative['cases'])
        assert all('GATE:' + g['id'] in plan['blockers'] for g in plan['gates'] if g['status'] != 'PASS')
        deadlines = [datetime.fromisoformat(plan['created_at']) + timedelta(minutes=30),
                     datetime.fromisoformat(scan['rule_valid_until'])]
        deadlines += [datetime.fromisoformat(c['valid_until']) for c in scan['package_trust']['candidates'] if c['valid_until']]
        assert datetime.fromisoformat(plan['expires_at']) <= min(deadlines)
        vm[cell] = {'status': 'PASS', 'apt_simulation': 'PASS', 'verification_drift': [],
                    'stable_process_count': len(before), 'negative_cases': [c['case'] for c in negative['cases']],
                    'plan_sha256': plan['plan_sha256'], 'expires_at': plan['expires_at']}
result = {'result': 'PASS', 'source_commit': metadata['headSha'], 'run': metadata['url'],
          'source_files_matched': len(manifest['source_sha256']), 'artifact_hashes_matched': checked_artifacts,
          'python_tests': fixtures, 'containers': containers, 'vm_cells': vm,
          'runtime_safety': 'UNKNOWN', 'repair_execution': 'NOT_RUN_DISABLED',
          'remaining_admission': ['Complete consumer inventory', 'Loaded configuration', 'Request attribution',
              'Installation equivalence', 'Maintainer scripts/triggers/conffile policy', 'Downtime approval',
              'Plan-hash authorization', 'Locked transaction and post-repair health/failure verification']}
(root / 'current-source-validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
