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
if [[ "$sapi" == fpm ]]; then
  sudo apt-get install -y nginx
  sudo tee /etc/nginx/nginx.conf >/dev/null <<EOF
user www-data;
events {}
http {
  server {
    listen 18080;
    root /var/www/html;
    location ~ \.php\$ {
      include /etc/nginx/fastcgi.conf;
      fastcgi_pass unix:/run/php/php${php_branch}-fpm.sock;
    }
  }
}
EOF
  sudo systemctl restart nginx
  probe_port=18080
else
  for conf in /etc/apache2/mods-enabled/php*.load; do
    [[ -f "$conf" ]] && sudo a2dismod "$(basename "$conf" .load)"
  done
  sudo a2enmod "php${php_branch}"
  sudo systemctl restart apache2
  probe_port=80
fi
echo '<?php echo "webpatch-ci-route-ok";' | sudo tee /var/www/html/webpatch-ci.php >/dev/null
package_cache="${RUNNER_TEMP}/webpatch-archives"
mkdir -p "$package_cache"
(cd "$package_cache" && apt-get download "$package=$(dpkg-query -W -f='${Version}' "$package")")
python3 scripts/build_deb.py
sudo apt-get install -y ./dist/webpatch_0.1.0_all.deb
sudo systemctl start "$service"
[[ "$(curl --fail --silent "http://127.0.0.1:${probe_port}/webpatch-ci.php")" == webpatch-ci-route-ok ]]
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
sudo webpatch scan --package-cache "$package_cache" --format json > ci-evidence/vm-root-scan.json || rc=$?
[[ "$rc" == 1 || "$rc" == 2 ]]
rc=0
webpatch plan --dry-run --format json > ci-evidence/vm-plan.json || rc=$?
[[ "$rc" == 4 ]]
rc=0
webpatch apply > ci-evidence/vm-apply.txt 2>&1 || rc=$?
[[ "$rc" == 4 ]]
python3 - "$package" "$sapi" "$pid_before" "$service" <<'PY'
import json, sys
r = json.load(open('ci-evidence/vm-scan.json'))
assert r['safe'] is False
assert any(p['name'].split(':')[0] == sys.argv[1] for p in r['inventory']['packages'])
assert any(h['pid'] is not None for h in r['inventory']['runtime_hints'])
assert all(a['runtime_status'] == 'UNKNOWN' for a in r['assessments'])
privileged = json.load(open('ci-evidence/vm-root-scan.json'))
runtime = next(x for x in privileged['inventory']['runtimes'] if x['pid'] == int(sys.argv[3]))
assert runtime['association'] == 'VERIFIED_LOCAL_ASSOCIATION', runtime
assert runtime['service'] == sys.argv[4], runtime
assert any(p.split(':')[0] == sys.argv[1] for p in runtime['package_ids']), runtime
assert privileged['safe'] is False
assert privileged['inventory']['config_relations']
identity = next(p for p in privileged['package_trust']['installed'] if p['package_id'].split(':')[0] == sys.argv[1])
assert identity['status'] == 'AUTHENTICATED_RUNTIME_FILES', identity
assert privileged['package_trust']['candidates']
p = json.load(open('ci-evidence/vm-plan.json'))
assert not p['executable'] and p['apt_simulation'] == 'NOT_IMPLEMENTED'
PY
PYTHONPATH=src python3 tests/integration/crypto_check.py
sudo systemctl is-active --quiet "$service"
[[ "$pid_before" == "$(systemctl show "$service" --property=MainPID --value)" ]]
[[ "$before" == "$(snapshot)" ]]
sudo systemctl show "$service" --property=ActiveState,SubState,MainPID > ci-evidence/vm-service.txt
python3 scripts/evidence_manifest.py ci-evidence
sha256sum dist/*.deb > ci-evidence/package-sha256.txt
uname -a > ci-evidence/kernel.txt
echo "PASS: Ubuntu $release / $sapi; package installed, service active, scans preserved PID and state."
