"""Validate the draft and its downloads against the accepted distribution artifact."""
import hashlib
import json
from pathlib import Path
import sys

metadata_path, draft_dir, distribution_dir, expected_sha, output_path = sys.argv[1:]
metadata = json.loads(Path(metadata_path).read_text())
assert metadata['tag_name'] == 'v0.3.0'
assert metadata['target_commitish'] == expected_sha
assert metadata['draft'] is True and metadata['prerelease'] is False
expected_names = {'webpatch_0.3.0_all.deb', 'install.sh', 'LICENSE', 'SHA256SUMS'}
assert {asset['name'] for asset in metadata['assets']} == expected_names
records = {}
for directory in (Path(draft_dir), Path(distribution_dir)):
    lines = (directory / 'SHA256SUMS').read_text().splitlines()
    expected = {}
    for line in lines:
        digest, name = line.split()
        assert name in expected_names - {'SHA256SUMS'} and name not in expected
        expected[name] = digest
    assert set(expected) == expected_names - {'SHA256SUMS'}
    for name in expected_names:
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if name != 'SHA256SUMS':
            assert digest == expected[name]
        if name in records:
            assert digest == records[name]
        records[name] = digest
Path(output_path).write_text(json.dumps({'result': 'PASS', 'release_source': expected_sha,
    'release_tag': 'v0.3.0', 'draft_and_tested_artifacts_match': True, 'sha256': records}, indent=2) + '\n')
print(json.dumps({'result': 'PASS', 'assets': len(records), 'package_sha256': records['webpatch_0.3.0_all.deb']}))
