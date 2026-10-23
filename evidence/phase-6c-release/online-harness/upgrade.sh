#!/bin/bash
set -euo pipefail
[ "$(id -u)" != 0 ]
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/download/v0.1.0/install.sh | sh -s -- --version 0.1.0 > initial-install.log 2>&1
[ "$(webpatch --version)" = 0.1.0 ]
printf '%s\n' 'BASELINE: published v0.1.0 installed as non-root via sudo.'
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh | sh > upgrade-output.txt 2>&1
cat upgrade-output.txt
[ "$(webpatch --version)" = 0.2.0 ]
python3 - <<'PY'
from pathlib import Path
import json
text=Path('upgrade-output.txt').read_text()
assert 'Installed WebPatch 0.2.0' in text
assert 'unsandboxed as root' not in text and 'Reading package lists' not in text
assert len(text.splitlines())<20
print(json.dumps({'result':'PASS','upgrade':'0.1.0 -> 0.2.0','quiet_output':True,'apt_sandbox_warning':False},indent=2))
PY
