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
# Hosted images use mirror+file and third-party feeds. Set up the explicitly
# supported direct official repository fixture, only inside this disposable VM.
sudo python3 - <<'PY'
from pathlib import Path
import hashlib, json, shutil, tempfile
backup = Path(tempfile.mkdtemp(prefix='webpatch-vm-original-sources-'))
paths = [Path('/etc/apt/sources.list')]
paths += list(Path('/etc/apt/sources.list.d').glob('*.list'))
paths += list(Path('/etc/apt/sources.list.d').glob('*.sources'))
hashes = {}
for path in paths:
    if path.exists():
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.move(str(path), backup / path.name)
Path('ci-evidence/original-source-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
PY
codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
sudo tee /etc/apt/sources.list >/dev/null <<EOF
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu $codename main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu $codename-updates main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://security.ubuntu.com/ubuntu $codename-security main universe restricted multiverse
EOF
sudo apt-get update
if [[ "$sapi" == apache ]]; then
  # The hosted image can contain an older Apache version absent from current
  # signed indexes. Establish a current official fixture before invariants begin.
  sudo apt-get install -y "$package" apache2 apache2-bin
else
  sudo apt-get install -y "$package"
fi
if [[ "$sapi" == fpm ]]; then
  sudo tee "/etc/php/${php_branch}/fpm/pool.d/webpatch-ci-extra.conf" >/dev/null <<EOF
[webpatch_ci_extra]
user = www-data
group = www-data
listen = /run/php/webpatch-ci-extra.sock
listen.owner = www-data
listen.group = www-data
pm = static
pm.max_children = 1
EOF
  sudo systemctl restart "$service"
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
    location = /webpatch-extra.php {
      include /etc/nginx/fastcgi.conf;
      fastcgi_pass unix:/run/php/webpatch-ci-extra.sock;
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
# Explicit collector preparation is confined to this guarded disposable VM.
sudo install -o root -g root -m 0644 src/webpatch/data/application_probe.php /var/www/html/webpatch-proof.php
sudo install -o root -g root -m 0644 src/webpatch/data/application_probe.php /var/www/html/webpatch-extra.php
sudo mkdir -p /etc/webpatch
echo '/var/www/html/webpatch-proof.php' | sudo tee /etc/webpatch/probe-blacklist >/dev/null
echo '/var/www/html/webpatch-extra.php' | sudo tee -a /etc/webpatch/probe-blacklist >/dev/null
php_sapi_dir="$sapi"
[[ "$sapi" == apache ]] && php_sapi_dir=apache2
echo 'opcache.blacklist_filename=/etc/webpatch/probe-blacklist' | sudo tee "/etc/php/${php_branch}/${php_sapi_dir}/conf.d/99-webpatch-probe.ini" >/dev/null
sudo systemctl restart "$service"
package_cache="${RUNNER_TEMP}/webpatch-archives"
mkdir -p "$package_cache"
(cd "$package_cache" && apt-get download "$package=$(dpkg-query -W -f='${Version}' "$package")")
python3 scripts/build_deb.py
sudo apt-get install -y ./dist/webpatch_0.1.0_all.deb
sudo systemctl start "$service"
[[ "$(curl --fail --silent "http://127.0.0.1:${probe_port}/webpatch-ci.php")" == webpatch-ci-route-ok ]]
sudo systemctl is-active --quiet "$service"
# Complete package setup before establishing the no-special-dpkg-options fixture.
# Every relocated input is recorded. Production audits still reject these hooks.
sudo python3 - <<'PYHOOK'
from pathlib import Path
import hashlib, json, re, shutil, tempfile
backup=Path(tempfile.mkdtemp(prefix='webpatch-vm-original-dpkg-options-'))
records=[]
paths=[Path('/etc/dpkg/dpkg.cfg')]
paths += [p for p in Path('/etc/dpkg/dpkg.cfg.d').iterdir() if re.fullmatch(r'[0-9A-Za-z_-]+',p.name)]
for path in paths:
    if not path.exists(): continue
    raw=path.read_text()
    active=[line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if all(line in {'no-debsig','log /var/log/dpkg.log'} for line in active): continue
    records.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'action':'RELOCATED_IN_DISPOSABLE_FIXTURE'})
    shutil.move(path,backup/path.name)
Path('ci-evidence/original-dpkg-options.json').write_text(json.dumps(records,indent=2)+'\n')
PYHOOK
pid_before="$(systemctl show "$service" --property=MainPID --value)"
test "$pid_before" -gt 0
snapshot() {
  sudo python3 - <<'PY'
from pathlib import Path
import hashlib
h = hashlib.sha256()
for root in ('/etc/php', '/etc/apache2', '/etc/nginx', '/etc/apt', '/etc/dpkg', '/var/lib/apt/lists'):
    for p in sorted(Path(root).rglob('*')):
        if p.is_file():
            h.update(str(p).encode())
            h.update(p.read_bytes())
h.update(Path('/var/lib/dpkg/status').read_bytes())
print(h.hexdigest())
PY
}
before="$(snapshot)"
runtime_snapshot() {
  sudo python3 - <<'PY'
from pathlib import Path
import json
rows = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit(): continue
    try:
        comm = (proc / 'comm').read_text().strip()
        if 'php' in comm or comm in {'apache2', 'httpd'}:
            rows.append((int(proc.name), (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19], str((proc / 'exe').readlink())))
    except FileNotFoundError:
        continue
print(json.dumps(sorted(rows)))
PY
}
runtime_snapshot > ci-evidence/runtime-processes-before.json
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
sudo webpatch plan --dry-run --package-cache "$package_cache" --format json > ci-evidence/vm-root-plan.json || rc=$?
[[ "$rc" == 4 ]]
rc=0
sudo webpatch verify-plan ci-evidence/vm-root-plan.json --package-cache "$package_cache" --format json > ci-evidence/vm-plan-verification.json || rc=$?
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
assert not p['executable']
root_plan = json.load(open('ci-evidence/vm-root-plan.json'))
assert not root_plan['executable'] and root_plan['apt_simulation'] == 'PASS', root_plan['blockers']
assert root_plan['schema_version'] == 4 and root_plan['admission_status'] == 'BLOCKED'
gates = root_plan['gates']
assert next(g for g in gates if g['category'] == 'diagnostic_simulation')['status'] == 'PASS'
assert next(g for g in gates if g['category'] == 'installation_equivalence')['status'] == 'UNKNOWN'
assert all('GATE:' + g['id'] in root_plan['blockers'] for g in gates if g['status'] != 'PASS')
ids = [e['id'] for e in root_plan['scan_evidence'] + root_plan['evidence']]
assert len(set(ids)) == len(ids)
assert all(set(g['evidence_ids']) <= set(ids) for g in gates)
assert any(e['operation'] == 'apt_simulation' and e['outcome'] == 'EXIT_0' for e in root_plan['evidence'])
verification = json.load(open('ci-evidence/vm-plan-verification.json'))
assert verification['drift'] == [], verification
PY
PYTHONPATH=src python3 tests/integration/crypto_check.py
PYTHONPATH=src python3 tests/integration/apt_check.py "$package"
sudo systemctl is-active --quiet "$service"
# Complete package setup before establishing the no-special-dpkg-options fixture.
# Every relocated input is recorded. Production audits still reject these hooks.
sudo python3 - <<'PYHOOK'
from pathlib import Path
import hashlib, json, re, shutil, tempfile
backup=Path(tempfile.mkdtemp(prefix='webpatch-vm-original-dpkg-options-'))
records=[]
paths=[Path('/etc/dpkg/dpkg.cfg')]
paths += [p for p in Path('/etc/dpkg/dpkg.cfg.d').iterdir() if re.fullmatch(r'[0-9A-Za-z_-]+',p.name)]
for path in paths:
    if not path.exists(): continue
    raw=path.read_text()
    active=[line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if all(line in {'no-debsig','log /var/log/dpkg.log'} for line in active): continue
    records.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'action':'RELOCATED_IN_DISPOSABLE_FIXTURE'})
    shutil.move(path,backup/path.name)
Path('ci-evidence/original-dpkg-options.json').write_text(json.dumps(records,indent=2)+'\n')
PYHOOK
[[ "$pid_before" == "$(systemctl show "$service" --property=MainPID --value)" ]]
[[ "$before" == "$(snapshot)" ]]
runtime_snapshot > ci-evidence/runtime-processes-after.json
cmp ci-evidence/runtime-processes-before.json ci-evidence/runtime-processes-after.json
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/runtime_check.py "$package" "$sapi" "$pid_before" "$package_cache"
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/application_check.py "$probe_port" "$service" "$package_cache"
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/maintenance_check.py "$package" "$package_cache"
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/consumers_check.py "$package" "$package_cache"
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/execution_inputs_check.py "$package" "$package_cache"
[[ "$pid_before" == "$(systemctl show "$service" --property=MainPID --value)" ]]
[[ "$before" == "$(snapshot)" ]]
sudo systemctl show "$service" --property=ActiveState,SubState,MainPID > ci-evidence/vm-service.txt
sudo env PYTHONPATH=src GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=github-hosted python3 tests/integration/preparation_check.py "$package" "$service" "$probe_port" "$package_cache"
python3 scripts/evidence_manifest.py ci-evidence
sha256sum dist/*.deb > ci-evidence/package-sha256.txt
uname -a > ci-evidence/kernel.txt
echo "PASS: Ubuntu $release / $sapi; read-only phase preserved PID/state, explicit controlled-startup phase validated new PIDs and immutable config views."
