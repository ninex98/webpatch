#!/bin/bash
set -euo pipefail
[ "$(id -u)" != 0 ]
[ ! -x /usr/bin/python3 ]
printf '%s\n' 'BASELINE: non-root user; Python absent; no Git/pip/venv setup.'
cat /etc/os-release
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh | sh
[ "$(webpatch --version)" = 0.2.0 ]
printf '%s\n' 'ONLINE_INSTALL: PASS; sudo APT installed WebPatch and Python dependencies.'
webpatch --help > cli-help.txt
COLUMNS=72 webpatch scan --lang zh > human.txt || test "$?" = 2
python3 - <<'CHECK'
from pathlib import Path
text=Path('human.txt').read_text()
assert '未发现 PHP' in text and '下一步' in text and 'UNKNOWN' in text
assert 'adapter_limit:' not in text and '{"requirement"' not in text
assert '\x1b' not in text
print(text)
CHECK
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
print(json.dumps({'result':'PASS','version':'0.2.0','online_install':'PASS','nonroot_sudo_elevation':'PASS','python_dependency_install':'PASS','empty_inventory':'UNKNOWN','safe':False,'scan_exit':2},indent=2))
PY
