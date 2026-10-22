from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from conftest import NOW
from test_runtime_evidence import connected_fixture
from test_application import FakeProbe
from webpatch.application import ProbeExchange
from webpatch.preparation import preparation_plan, execute_preparation, verify_snapshot_views, restricted_ini_value
from webpatch.receipts import ReceiptStore
from webpatch.planning import digest
from webpatch.service import scan

SERVICE='php8.1-fpm.service'
ROOT='/etc/php/8.1/fpm'


class Journal:
    def __init__(self): self.rows=[]
    def events(self): return self.rows
    def append(self,row): self.rows.append(row)


def fixture(monkeypatch):
    fake=connected_fixture()
    fake.reads[ROOT+'/php.ini']='; controlled fixture\nauto_prepend_file = ""\nenable_dl = Off\n'
    fake.dirs[ROOT+'/conf.d']=[]
    for pid, socket_fd, inode in ((43,'8','1234'),(44,'9','1235')):
        fake.dirs['/proc'].append(str(pid))
        for mapping in (fake.reads,fake.links,fake.identities,fake.fingerprints,fake.dirs):
            for path,value in list(mapping.items()):
                if path.startswith('/proc/42/'):
                    mapping[path.replace('/42/',f'/{pid}/')]=deepcopy(value)
        fake.dirs[f'/proc/{pid}/fd']=[socket_fd]
    for index,(path,text) in enumerate(fake.reads.items()):
        if path.startswith(ROOT+'/') and isinstance(text,str):
            fake.fingerprints[path]={'uid':0,'mode':0o100644,'device':1,'inode':800+index,'size':len(text),'sha256':hashlib.sha256(text.encode()).hexdigest()}
    def definition(report, **kwargs):
        return {'service':kwargs['service'],'status':'AUTHENTICATED_SERVICE_DEFINITION','blockers':[],
                'files':[],'archives':[],'definition_sha256':'a'*64,'evidence':[],
                'unit_source':{'path':'/lib/systemd/system/'+SERVICE,'content':'[Service]\n','sha256':hashlib.sha256(b'[Service]\n').hexdigest()}}
    monkeypatch.setattr('webpatch.preparation.authenticate_service',definition)
    probes=[{'service':SERVICE,'url':'http://127.0.0.1:18080/webpatch-proof.php',
             'script':'/var/www/html/webpatch-proof.php','pool_listener':'/run/php/php8.1-fpm.sock'},
            {'service':SERVICE,'url':'http://127.0.0.1:18080/webpatch-jobs.php',
             'script':'/var/www/html/webpatch-jobs.php','pool_listener':'/run/php/jobs.sock'}]
    report=scan(fake,now=NOW)
    return fake,report,probes


class Probe(FakeProbe):
    def collect(self,url,script,challenge,scope):
        result=super().collect(url,script,challenge,scope)
        payload=json.loads(result.payload)
        pid=44 if 'jobs.php' in url else 43
        payload.update(pid=pid,request_path=url.split(':18080',1)[1])
        data=json.dumps(payload).encode()
        response=json.dumps({'challenge':challenge,'payload_sha256':hashlib.sha256(data).hexdigest()}).encode()
        return replace(result,payload=data,response=response,peer_pid=pid)


class Controller:
    state_dir=Path('/var/lib/webpatch')
    def __init__(self,fake,tmp_path):
        self.fake=fake; self.store=ReceiptStore(tmp_path/'store'); self.calls=[]; self.owns_lock=False
    @contextmanager
    def locked(self):
        self.owns_lock=True
        try: yield
        finally: self.owns_lock=False
    def materialize(self,plan,system):
        assert self.owns_lock
        self.calls.append('materialize')
        snapshots=[]
        for tree in plan['configuration']:
            files=[]
            for index,item in enumerate(tree['files']):
                info={'device':9,'inode':1000+index,'sha256':item['sha256']}
                files.append({'path':item['path'],**info})
                for pid in (42,43,44): self.fake.fingerprints[f'/proc/{pid}/root'+item['path']]=info
            snapshots.append({'service':tree['service'],'root':tree['root'],'snapshot':'/var/lib/webpatch/snapshot-fixture','files':files})
        for pid in (42,43,44): self.fake.reads[f'/proc/{pid}/mountinfo']='1 0 0:9 / '+ROOT+' ro - tmpfs fixture rw\n'
        return {'snapshots':snapshots,'overrides':[{'service':SERVICE,'path':'/run/systemd/system/'+SERVICE,'sha256':'b'*64}]}
    def verify_loaded_definitions(self,record,system): self.calls.append('definitions')
    def command(self,action,service=None):
        assert self.owns_lock
        self.calls.append(action)
        if action=='restart':
            for pid in (42,43,44):
                self.fake.reads[f'/proc/{pid}/stat']=self.fake.reads[f'/proc/{pid}/stat'].replace('123','456')
                self.fake.links[f'/proc/{pid}/ns/mnt']='mnt:[2]'
                self.fake.fingerprints[f'/proc/{pid}/root/usr/sbin/php-fpm8.1']=self.fake.fingerprints['/usr/sbin/php-fpm8.1']
    def wait_stable(self,service): self.calls.append('stable')


def make_plan(fake,report,probes):
    return preparation_plan(report,system=fake,services=[SERVICE],probes=probes,package_cache='/var/cache/apt/archives',now=NOW,package_lock_owned=True)


def test_controlled_startup_links_new_processes_to_readonly_input_views(monkeypatch,tmp_path):
    fake,report,probes=fixture(monkeypatch)
    proposal=make_plan(fake,report,probes)
    assert proposal['status']=='READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION',proposal['blockers']
    controller, journal=Controller(fake,tmp_path), Journal()
    result=execute_preparation(proposal,confirmation_sha256=proposal['preparation_sha256'],system=fake,
        controller=controller,probe=Probe(),journal=journal,clock=lambda:NOW)
    assert result['status']=='VERIFIED_CONTROLLED_STARTUP',result
    body=controller.store.verify(result['receipt'])
    assert body['kind']=='controlled_startup' and len(body['probes'])==2
    assert all(':456' in identity for identity in body['runtime_ids'])
    assert controller.calls==['materialize','daemon-reload','definitions','restart','stable']
    assert journal.rows[-1]['state']=='PREPARATION_VERIFIED'


@pytest.mark.parametrize('line', ['auto_prepend_file="/tmp/evil.php"', 'auto_prepend_file=";evil.php"',
    'php_admin_value["auto_append_file"]="/tmp/evil.php"', 'extension=unknown.so', 'enable_dl=On',
    'ffi.preload=/tmp/ffi.h', 'opcache.preload=/tmp/preload.php'])
def test_code_hooks_and_new_unverified_modules_block_before_restart(line,monkeypatch):
    fake,report,probes=fixture(monkeypatch)
    fake.reads[ROOT+'/php.ini'] += line+'\n'
    fake.fingerprints[ROOT+'/php.ini']['sha256']=hashlib.sha256(fake.reads[ROOT+'/php.ini'].encode()).hexdigest()
    result=make_plan(fake,scan(fake,now=NOW),probes)
    assert result['status']=='BLOCKED' and result['blockers']


def test_missing_pool_probe_and_forged_actions_cannot_authorize_preparation(monkeypatch,tmp_path):
    fake,report,probes=fixture(monkeypatch)
    assert make_plan(fake,report,probes[:1])['status']=='BLOCKED'
    proposal=make_plan(fake,report,probes)
    proposal['actions']=['No interruptions or mutations']
    proposal['preparation_sha256']=digest(dict(proposal,preparation_sha256=''))
    controller=Controller(fake,tmp_path)
    result=execute_preparation(proposal,confirmation_sha256=proposal['preparation_sha256'],system=fake,
                              controller=controller,probe=Probe(),journal=Journal(),clock=lambda:NOW)
    assert result['status']=='BLOCKED' and not controller.calls


def test_wrong_confirmation_and_untrusted_state_path_never_mutate(monkeypatch,tmp_path):
    fake,report,probes=fixture(monkeypatch)
    proposal=make_plan(fake,report,probes)
    controller=Controller(fake,tmp_path)
    result=execute_preparation(proposal,confirmation_sha256='f'*64,system=fake,controller=controller,probe=Probe(),journal=Journal(),clock=lambda:NOW)
    assert result['status']=='BLOCKED' and not controller.calls
    proposal['state_directory']='/etc/ssh'
    proposal['preparation_sha256']=digest(dict(proposal,preparation_sha256=''))
    result=execute_preparation(proposal,confirmation_sha256=proposal['preparation_sha256'],system=fake,controller=controller,probe=Probe(),journal=Journal(),clock=lambda:NOW)
    assert result['status']=='BLOCKED' and not controller.calls


def test_receipt_signature_and_file_permissions_prevent_caller_fabrication(tmp_path):
    store=ReceiptStore(tmp_path/'private')
    document=store.seal({'kind':'fixture','scope':'known'})
    assert store.verify(document)['scope']=='known'
    document['payload']['scope']='forged'
    with pytest.raises(ValueError,match='RECEIPT_AUTHENTICATION_FAILED'): store.verify(document)
    store.key_path.chmod(0o644)
    with pytest.raises(ValueError,match='RECEIPT_KEY_UNTRUSTED'): store.seal({'kind':'fixture'})


def test_readonly_mount_and_inode_are_required_not_just_matching_file_text(monkeypatch,tmp_path):
    fake,report,probes=fixture(monkeypatch)
    controller=Controller(fake,tmp_path)
    proposal=make_plan(fake,report,probes)
    controller.owns_lock=True
    material=controller.materialize(proposal,fake)
    assert verify_snapshot_views(report,material['snapshots'],fake)['status']=='VERIFIED_READONLY_RUNTIME_VIEWS'
    fake.reads['/proc/42/mountinfo']=fake.reads['/proc/42/mountinfo'].replace(ROOT+' ro',ROOT+' rw')
    assert verify_snapshot_views(report,material['snapshots'],fake)['status']=='BLOCKED'
