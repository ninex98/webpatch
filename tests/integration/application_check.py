"""Explicit application evidence on hosted VMs only; no production probing."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from webpatch.application import LocalApplicationProbe, collect_application_evidence, validate_exchange
from webpatch.service import scan
from webpatch.system import LocalSystem, ProbeError

assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
port, service, cache = sys.argv[1:]
url = f'http://127.0.0.1:{port}/webpatch-proof.php'
script = '/var/www/html/webpatch-proof.php'
reader = LocalSystem()
report = scan(reader, package_cache=cache)
result = collect_application_evidence(report, system=reader, probe=LocalApplicationProbe(),
                                      url=url, script_path=script, service=service)
Path('ci-evidence/application-probe.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['status'] == 'VERIFIED_PROCESS_RESPONSE', result['blockers']
assert not result['executable'] and result['loaded_configuration_file_bytes'] == 'UNKNOWN'
assert result['peer_pid'] in {r.pid for r in report.inventory.runtimes if r.service == service}
# Preserve a real exchange for independent replay/spoof checks (no stored secret).
challenge = 'a' * 64
exchange = LocalApplicationProbe().collect(url, script, challenge, report.inventory.environment.scope_sha256)
validate_exchange(exchange, report, challenge, url, script, service)
negative = []
try:
    LocalApplicationProbe().collect(url.replace('webpatch-proof.php', 'webpatch-ci.php'), script, challenge,
                                    report.inventory.environment.scope_sha256)
    raise AssertionError('ordinary HTTP marker unexpectedly attributed')
except ProbeError as exc:
    negative.append({'case':'real_http_marker_without_callback','result':'PASS','reason':str(exc)})
for case, bad, nonce in [('replayed_nonce', exchange, 'b' * 64),
                         ('forged_peer_pid', replace(exchange, peer_pid=os.getpid()), challenge),
                         ('ordinary_http_marker', replace(exchange, response=b'{"ok":true}'), challenge)]:
    try:
        validate_exchange(bad, report, nonce, url, script, service)
        raise AssertionError(case + ' unexpectedly accepted')
    except ValueError as exc:
        negative.append({'case': case, 'result': 'PASS', 'reason': str(exc)})
Path('ci-evidence/application-negative.json').write_text(json.dumps({
    'result':'PASS','cases':negative,'observed_at':datetime.now(timezone.utc).isoformat(),
    'boundary':'Kernel sender credentials bind a single response; loaded configuration file bytes remain UNKNOWN.'},indent=2)+'\n')
print('PASS: explicit real PHP callback attributed by kernel credentials; replay/PID/ordinary-marker negatives rejected.')
