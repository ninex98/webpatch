from dataclasses import replace
from datetime import datetime,timedelta
import json
from pathlib import Path

import pytest

from conftest import FakeSystem
from webpatch.cli import main
from webpatch.node_adapter import scan_node
from webpatch.node_rules import NodeRuleProvider
from webpatch.system import CommandResult,DPKG_QUERY,ProbeError

NOW=datetime.fromisoformat('2026-10-23T00:00:00+00:00')


def fixture(release='12',version=None):
    version=version or ('18.20.4+dfsg-1~deb12u2' if release=='12' else '20.19.2+dfsg-1+deb13u2')
    fake=FakeSystem({'os':['debian',release,'bookworm' if release=='12' else 'trixie'],
        'packages':[['nodejs',version,'amd64','nodejs',version,'install ok installed']]})
    for installed,fixed,meets in json.loads((Path(__file__).parent/'fixtures/node-comparisons.json').read_text()):
        fake.commands[('/usr/bin/dpkg','--compare-versions',installed,'ge',fixed)]=CommandResult(0 if meets else 1)
    for path in ('/usr/local/bin/node','/opt/node/bin/node','/opt/nodejs/bin/node','/snap/node/current/bin/node'):
        fake.fingerprints[path]=ProbeError('FileNotFoundError')
    return fake


@pytest.mark.parametrize('release',['12','13'])
def test_node_uses_independent_vendor_boundaries_for_each_cve(release):
    result=scan_node(fixture(release),now=NOW)
    assert [a.version_status for a in result.assessments]==['MEETS_VENDOR_FIX','BELOW_VENDOR_FIX']
    assert result.overall=='POTENTIALLY_AFFECTED' and not result.safe
    assert all(a.runtime_status=='UNKNOWN' for a in result.assessments)
    assert all(a.cve not in {'CVE-2026-109618','CVE-2026-109619'} for a in result.assessments)


@pytest.mark.parametrize('case',['upstream','ubuntu','foreign-source','bad-identity','unconfigured','duplicate','expired','empty'])
def test_node_unknown_cases_never_become_safe(case):
    fake=fixture(); now=NOW
    query=fake.commands[DPKG_QUERY]
    if case=='upstream': fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('18.20.4+dfsg-1~deb12u2','18.20.4'))
    elif case=='ubuntu': fake.reads['/etc/os-release']='ID=ubuntu\nVERSION_ID=24.04\nVERSION_CODENAME=noble\n'
    elif case=='foreign-source': fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('\tnodejs\t','\tnodesource\t'))
    elif case=='bad-identity': fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('nodejs\t','nodejs:arm64\t',1))
    elif case=='unconfigured': fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('install ok installed','install ok unpacked'))
    elif case=='duplicate': fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout*2)
    elif case=='expired': now+=timedelta(days=8)
    elif case=='empty': fake.commands[DPKG_QUERY]=CommandResult(0,'')
    result=scan_node(fake,now=now)
    assert not result.safe and all(a.version_status=='UNKNOWN' for a in result.assessments)
    assert result.inventory.coverage_gaps


def process_fixture():
    fake=fixture(); fake.dirs['/proc']=['42']; fake.reads['/proc/42/comm']='renamed-worker\n'
    fake.links['/proc/42/exe']='/usr/bin/node'
    fake.links['/proc/42/ns/mnt']='mnt:[1]'; fake.links['/proc/42/ns/pid']='pid:[1]'
    fake.identities['/proc/42/root']={'device':1,'inode':1}
    fake.reads['/proc/42/stat']='42 (renamed worker) S '+' '.join(['0']*18+['123']+['0']*20)
    fake.reads['/proc/42/maps']='1000-2000 r-xp 00000000 00:01 88 /usr/bin/node\n'
    info={'sha256':'a'*64,'device':1,'inode':88,'uid':0,'mode':0o100755}
    fake.fingerprints['/proc/42/exe']=info.copy(); fake.fingerprints['/usr/bin/node']=info.copy()
    fake.commands[('/usr/bin/dpkg-query','-S','/usr/bin/node')]=CommandResult(0,'nodejs: /usr/bin/node\n')
    return fake


def test_renamed_node_is_discovered_by_executable_without_running_node():
    fake=process_fixture(); result=scan_node(fake,now=NOW)
    runtime=result.inventory.runtimes[0]
    assert runtime.pid==42 and runtime.start_ticks=='123'
    assert runtime.association=='VERIFIED_LOCAL_FILE_ASSOCIATION',runtime.blockers
    assert runtime.files[0].status=='VERIFIED_LOCAL_FILE' and not result.safe
    assert not any('/usr/bin/node'==call[1][0] for call in fake.calls if call[0]=='run')


@pytest.mark.parametrize('case',['foreign','deleted','replaced','missing-pid-namespace'])
def test_node_process_unknown_identity_remains_explicit(case):
    fake=process_fixture()
    if case=='foreign': fake.links['/proc/42/ns/mnt']='mnt:[9]'
    elif case=='deleted': fake.links['/proc/42/exe']+=" (deleted)"
    elif case=='replaced': fake.fingerprints['/usr/bin/node']['inode']=99
    else: fake.links['/proc/42/ns/pid']=ProbeError('PermissionError')
    result=scan_node(fake,now=NOW)
    assert result.inventory.runtimes[0].association=='UNKNOWN' and not result.safe


def test_node_cli_is_separate_from_php_and_reports_uncovered_npm(capsys):
    assert main(['scan-node','--format','json'],system=fixture(),now=NOW)==1
    result=json.loads(capsys.readouterr().out)
    assert 'NPM_DEPENDENCIES_NOT_ASSESSED' in result['inventory']['coverage_gaps']
    assert result['rule_revision'].startswith('nodejs-')


def test_node_rule_provider_rejects_ambiguous_or_expired_contract():
    provider=NodeRuleProvider(); data=provider.data
    data['rules'].append(data['rules'][0])
    with pytest.raises(ValueError,match='NODE_RULE_AMBIGUOUS'): NodeRuleProvider(json.dumps(data).encode())
