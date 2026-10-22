#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]]
[[ -n "${WEBPATCH_DEBIAN_GUEST:-}" && "$(cat /etc/webpatch-ci-guest)" == "$WEBPATCH_DEBIAN_GUEST" ]]
cd /home/webpatch/work
mkdir -p ci-evidence
case "${1:-}" in fpm|apache) sapi="$1";; *) exit 1;; esac
codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
case "$codename" in bookworm) branch=8.2;; trixie) branch=8.4;; *) exit 1;; esac
python3 - <<'PY'
from pathlib import Path
import hashlib,json
export=json.loads(Path('source-export.json').read_text())
for name,value in export['source_sha256'].items():
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==value,name
Path('ci-evidence/source-export.json').write_text(json.dumps(export,indent=2)+'\n')
PY
# Explicit official-main fixture, only inside the disposable Debian guest.
mkdir -p /var/lib/webpatch-ci-original-sources
python3 - <<'PY'
from pathlib import Path
import hashlib,json,shutil
paths=[Path('/etc/apt/sources.list'),*Path('/etc/apt/sources.list.d').glob('*.list'),*Path('/etc/apt/sources.list.d').glob('*.sources')]
records=[]
for number,path in enumerate(paths):
    if path.exists():
        records.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        shutil.move(path,Path('/var/lib/webpatch-ci-original-sources')/(str(number)+'-'+path.name))
Path('ci-evidence/original-sources.json').write_text(json.dumps(records,indent=2)+'\n')
PY
cat > /etc/apt/sources.list <<EOF
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian $codename main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian $codename-updates main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://security.debian.org/debian-security $codename-security main
EOF
export DEBIAN_FRONTEND=noninteractive
apt-get update
if [[ "$sapi" == fpm ]]; then
  package="php${branch}-fpm"; service="php${branch}-fpm.service"
  apt-get install -y "$package" php-cli nginx gpgv curl
else
  package="libapache2-mod-php${branch}"; service=apache2.service
  apt-get install -y "$package" php-cli apache2 gpgv curl
  echo 'Listen 127.0.0.1:80' > /etc/apache2/ports.conf
  echo 'ServerName localhost' > /etc/apache2/conf-available/webpatch-ci.conf
  a2enconf webpatch-ci
fi
mkdir -p /var/cache/webpatch-ci
(cd /var/cache/webpatch-ci && apt-get download "$package=$(dpkg-query -W -f='${Version}' "$package")")
systemctl restart "$service"
systemctl is-active --quiet "$service"
python3 scripts/build_deb.py
apt-get install -y ./dist/webpatch_0.1.0_all.deb
rc=0
webpatch scan --format json --package-cache /var/cache/webpatch-ci > ci-evidence/scan.json || rc=$?
[[ "$rc" == 1 || "$rc" == 2 ]]
python3 - "$package" "$service" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path('ci-evidence/scan.json').read_text())
assert r['package_trust']['status']=='VERIFIED_INDEX_CHAIN',r['package_trust']['blockers']
p=next(p for p in r['package_trust']['installed'] if p['package_id'].split(':')[0]==sys.argv[1])
assert p['status']=='AUTHENTICATED_RUNTIME_FILES',p
instances=[v for v in r['inventory']['runtimes'] if v['service']==sys.argv[2]]
assert instances and all(v['association']=='VERIFIED_LOCAL_ASSOCIATION' for v in instances),instances
assert not r['safe'] and r['inventory']['environment']['scope']!='container'
Path('ci-evidence/result.json').write_text(json.dumps({'result':'PASS','scope':'Debian VM service discovery and signed archive identity only',
    'package':sys.argv[1],'service':sys.argv[2],'runtime_count':len(instances),'environment':r['inventory']['environment']},indent=2)+'\n')
PY
uname -a > ci-evidence/kernel.txt
systemctl show "$service" --property=ActiveState,SubState,MainPID,FragmentPath > ci-evidence/service.txt
