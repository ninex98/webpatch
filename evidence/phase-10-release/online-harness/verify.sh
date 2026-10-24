#!/bin/bash
set -euo pipefail
[ "$(id -u)" != 0 ]
[ ! -x /usr/bin/python3 ]
cat /etc/os-release
wp_online_tmp=$(mktemp -d)
curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 --connect-timeout 15 --max-time 60 --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh -o "$wp_online_tmp/install.sh"
sh "$wp_online_tmp/install.sh" </dev/null
[ "$(/usr/bin/webpatch --version)" = 0.3.0 ]
webpatch scan --help > scan-help.txt
before=$(sha256sum /var/lib/dpkg/status)
COLUMNS=80 webpatch scan --lang zh > human.txt || test "$?" = 2
webpatch scan --format json > scan.json || test "$?" = 2
[ "$before" = "$(sha256sum /var/lib/dpkg/status)" ]
python3 - <<'PY'
import json
from pathlib import Path
text=Path('human.txt').read_text()
assert 'UNKNOWN' in text and 'Docker' in text and '下一步' in text
assert '--docker-socket' in Path('scan-help.txt').read_text()
r=json.loads(Path('scan.json').read_text())
assert not r['safe'] and not r['inventory']['packages']
assert r['docker']['status']=='NOT_CHECKED' and r['docker']['gaps']==['DOCKER_CURRENT_CONTAINER_ONLY']
print(text)
print(json.dumps({'result':'PASS','version':'0.3.0','install':'public latest release','python_dependency':'installed','sudo_elevation':'PASS','scan':'UNKNOWN','docker_options':'PASS','scope':'current container only','dpkg_unchanged':True}))
PY
