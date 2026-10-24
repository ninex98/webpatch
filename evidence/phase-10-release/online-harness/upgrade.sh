#!/bin/bash
set -euo pipefail
[ "$(id -u)" != 0 ]
wp_upgrade_tmp=$(mktemp -d)
curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 --connect-timeout 15 --max-time 60 --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/download/v0.2.0/install.sh -o "$wp_upgrade_tmp/old-install.sh"
sh "$wp_upgrade_tmp/old-install.sh" --version 0.2.0 </dev/null
[ "$(/usr/bin/webpatch --version)" = 0.2.0 ]
curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 --connect-timeout 15 --max-time 60 --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh -o "$wp_upgrade_tmp/new-install.sh"
sh "$wp_upgrade_tmp/new-install.sh" </dev/null > upgrade-output.txt 2>&1
cat upgrade-output.txt
[ "$(/usr/bin/webpatch --version)" = 0.3.0 ]
webpatch scan --help > scan-help.txt
python3 - <<'PY'
from pathlib import Path
import json
text=Path('upgrade-output.txt').read_text()
assert 'Installed WebPatch 0.3.0' in text and 'unsandboxed as root' not in text
assert len(text.splitlines()) < 20
assert '--docker-socket' in Path('scan-help.txt').read_text()
print(json.dumps({'result':'PASS','upgrade':'0.2.0 -> 0.3.0','docker_options':True,'quiet_output':True}))
PY
