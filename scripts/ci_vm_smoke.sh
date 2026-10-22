#!/usr/bin/env bash
# NEVER run this installation script on a developer/server host.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != "true" || "${RUNNER_ENVIRONMENT:-}" != "github-hosted" ]]; then
  echo 'Refusing: installation/service test requires an ephemeral GitHub-hosted VM.' >&2
  exit 1
fi
case "${1:-}" in
  fpm|apache) sapi="$1" ;;
  *) echo 'Expected fpm or apache' >&2; exit 1 ;;
esac
release="$(. /etc/os-release && echo "$VERSION_ID")"
case "$release" in
  22.04) php_branch=8.1 ;;
  24.04) php_branch=8.3 ;;
  *) echo 'Unsupported VM release' >&2; exit 1 ;;
esac
if [[ "$sapi" == fpm ]]; then
  package="php${php_branch}-fpm"
  service="php${php_branch}-fpm.service"
else
  package="libapache2-mod-php${php_branch}"
  service=apache2.service
fi
mkdir -p ci-evidence
sudo apt-get update
sudo apt-get install -y "$package"
python3 scripts/build_deb.py
sudo apt-get install -y ./dist/webpatch_0.1.0_all.deb
sudo systemctl start "$service"
sudo systemctl is-active --quiet "$service"
pid_before="$(systemctl show "$service" --property=MainPID --value)"
test "$pid_before" -gt 0
snapshot() {
  sudo python3 - <<'PY'
from pathlib import Path
import hashlib
h = hashlib.sha256()
for root in ('/etc/php', '/etc/apache2', '/etc/apt', '/var/lib/apt/lists'):
    for p in sorted(Path(root).rglob('*')):
        if p.is_file():
            h.update(str(p).encode())
            h.update(p.read_bytes())
h.update(Path('/var/lib/dpkg/status').read_bytes())
print(h.hexdigest())
PY
}
before="$(snapshot)"
rc=0
webpatch scan --format json > ci-evidence/vm-scan.json || rc=$?
[[ "$rc" == 1 || "$rc" == 2 ]]
rc=0
webpatch plan --dry-run --format json > ci-evidence/vm-plan.json || rc=$?
[[ "$rc" == 4 ]]
rc=0
webpatch apply > ci-evidence/vm-apply.txt 2>&1 || rc=$?
[[ "$rc" == 4 ]]
python3 - "$package" "$sapi" <<'PY'
import json, sys
r = json.load(open('ci-evidence/vm-scan.json'))
assert r['safe'] is False
assert any(p['name'].split(':')[0] == sys.argv[1] for p in r['inventory']['packages'])
assert any(h['pid'] is not None for h in r['inventory']['runtime_hints'])
assert all(a['runtime_status'] == 'UNKNOWN' for a in r['assessments'])
p = json.load(open('ci-evidence/vm-plan.json'))
assert not p['executable'] and p['apt_simulation'] == 'NOT_IMPLEMENTED'
PY
sudo systemctl is-active --quiet "$service"
[[ "$pid_before" == "$(systemctl show "$service" --property=MainPID --value)" ]]
[[ "$before" == "$(snapshot)" ]]
sudo systemctl show "$service" --property=ActiveState,SubState,MainPID > ci-evidence/vm-service.txt
echo "PASS: Ubuntu $release / $sapi; package installed, service active, scans preserved PID and state."
