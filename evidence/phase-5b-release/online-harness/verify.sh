#!/bin/bash
set -euo pipefail
[ "$(id -u)" != 0 ]
[ ! -x /usr/bin/python3 ]
printf '%s\n' 'BASELINE: non-root user; Python absent; no Git/pip/venv setup.'
cat /etc/os-release
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh | sh
[ "$(webpatch --version)" = 0.1.0 ]
printf '%s\n' 'ONLINE_INSTALL: PASS; sudo APT installed WebPatch and Python dependencies.'
webpatch --help > cli-help.txt
before=$(sha256sum /var/lib/dpkg/status)
set +e
webpatch scan --format json > scan.json
scan_exit=$?
set -e
[ "$scan_exit" = 2 ]
[ "$before" = "$(sha256sum /var/lib/dpkg/status)" ]
python3 - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('scan.json').read_text())
assert r['safe'] is False and r['overall']=='UNKNOWN'
assert not r['inventory']['packages']
print(json.dumps({'result':'PASS','version':'0.1.0','online_install':'PASS','nonroot_sudo_elevation':'PASS','python_dependency_install':'PASS','empty_inventory':'UNKNOWN','safe':False,'scan_exit':2},indent=2))
PY
