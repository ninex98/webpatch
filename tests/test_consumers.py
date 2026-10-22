from dataclasses import replace
from copy import deepcopy
from datetime import timedelta

import pytest

from conftest import NOW
from test_runtime import runtime_fixture, report as runtime_report
from webpatch.consumers import census, map_rows
from webpatch.system import ProbeError


def fixture():
    fake = runtime_fixture()
    result = runtime_report(fake)
    path = '/usr/sbin/php-fpm8.1'
    fake.identities['/proc/42/exe'] = {'device':1,'inode':5}
    trusted = {'installed':[{'package_id':'php8.1-fpm:amd64','status':'AUTHENTICATED_RUNTIME_FILES','files':{path:'a'*64}}]}
    return fake, replace(result, package_trust=trusted)


def test_census_matches_file_identity_independently_of_process_name():
    fake, report = fixture()
    fake.reads['/proc/42/comm'] = 'renamed-worker'
    result = census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)
    assert result['status'] == 'VERIFIED_ACTIVE_MAPPING_CENSUS'
    assert result['consumers'][0]['pid'] == 42
    assert result['idle_and_future_consumers'] == 'NOT_PROVEN' and not result['executable']
    assert not any(path.endswith('/comm') for op,path in fake.calls[-8:] if isinstance(path,str))


@pytest.mark.parametrize('held_path',['/usr/sbin/php-fpm8.1','/tmp/another-hardlink-name'])
def test_unmapped_open_file_holder_is_accounted_by_inode(held_path):
    fake,report=fixture(); fake.dirs['/proc'].append('43')
    for attr in ('reads','identities','links'):
        mapping=getattr(fake,attr)
        for path,value in list(mapping.items()):
            if path.startswith('/proc/42/'): mapping[path.replace('/42/','/43/')]=deepcopy(value)
    fake.reads['/proc/43/maps']='300-400 r-xp 0 00:01 77 /usr/bin/python3\n'
    fake.identities['/proc/43/exe']={'device':1,'inode':77}
    fake.fd_tables['43']={'files':[{'fd':7,'target':held_path,'device':1,'inode':5,'mode':0o100755}],
                          'observed_count':1,'all_descriptors_sha256':'b'*64}
    result=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],now=NOW)
    assert result['status']=='BLOCKED' and 'CONSUMER_NOT_ACCOUNTED:43' in result['blockers']
    assert next(c for c in result['consumers'] if c['pid']==43)['open_file_descriptor_observations']==1


def test_unreadable_or_changing_descriptor_tables_never_prove_absence():
    fake,report=fixture()
    fake.fd_tables['42']=ProbeError('PermissionError')
    result=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],now=NOW)
    assert result['status']=='BLOCKED' and result['file_descriptor_coverage']=='UNKNOWN'
    fake.file_descriptors=None
    missing=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],now=NOW)
    assert missing['status']=='BLOCKED'
    assert any(e['outcome']=='CAPABILITY_UNAVAILABLE:file_descriptors' for e in missing['evidence'])
    count=0
    def changing(pid):
        nonlocal count
        count+=1
        files=[] if count==1 else [{'fd':7,'target':'/usr/sbin/php-fpm8.1','device':1,'inode':5,'mode':0o100755}]
        return {'files':files,'observed_count':len(files),'all_descriptors_sha256':'c'*64}
    fake.file_descriptors=changing
    result=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],now=NOW)
    assert 'CONSUMER_PROCESS_DESCRIPTORS_CHANGED:42' in result['blockers']


def test_census_detects_target_bytes_changed_during_observation():
    fake,report=fixture(); original=fake.fingerprint; calls=0
    def changed(path):
        nonlocal calls
        value=original(path)
        if path=='/usr/sbin/php-fpm8.1':
            calls+=1
            if calls>1: return {**value,'sha256':'f'*64}
        return value
    fake.fingerprint=changed
    result=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],now=NOW)
    assert 'CONSUMER_FILE_CHANGED_DURING_CENSUS:/usr/sbin/php-fpm8.1' in result['blockers']


def test_census_must_finish_inside_its_evidence_window():
    fake,report=fixture(); times=iter([NOW,NOW+timedelta(minutes=6)])
    result=census(report,system=fake,package_ids=['php8.1-fpm:amd64'],clock=lambda:next(times))
    assert result['status']=='BLOCKED' and 'CONSUMER_EVIDENCE_EXPIRED_OR_CLOCK_REVERSED' in result['blockers']


def test_renamed_extra_consumer_is_not_hidden_by_existing_inventory():
    fake, report = fixture()
    fake.dirs['/proc'].append('43')
    fake.fd_tables['43']=fake.fd_tables['42'].copy()
    for mapping in (fake.reads, fake.identities, fake.links):
        for path,value in list(mapping.items()):
            if path.startswith('/proc/42/'):
                mapping[path.replace('/42/','/43/')] = value
    result = census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)
    assert result['status'] == 'BLOCKED'
    assert 'CONSUMER_NOT_ACCOUNTED:43' in result['blockers']
    assert {c['pid'] for c in result['consumers']} == {42,43}


@pytest.mark.parametrize('change', ['permission','replaced','deleted','namespace','package-identity','empty-proc','malformed-map'])
def test_census_gaps_and_old_images_block_completeness(change):
    fake, report = fixture()
    if change == 'permission': fake.reads['/proc/42/maps'] = ProbeError('PermissionError')
    if change == 'replaced':
        fake.identities['/proc/42/exe'] = {'device':1,'inode':99}
        fake.reads['/proc/42/maps'] = fake.reads['/proc/42/maps'].replace('00:01 5','00:01 99')
    if change == 'deleted':
        fake.identities['/proc/42/exe'] = {'device':1,'inode':99}
        fake.reads['/proc/42/maps'] = fake.reads['/proc/42/maps'].replace('00:01 5','00:01 99').rstrip()+' (deleted)\n'
    if change == 'namespace': fake.links['/proc/42/ns/pid'] = 'pid:[2]'
    if change == 'package-identity': report.package_trust['installed'][0]['status'] = 'UNKNOWN'
    if change == 'empty-proc': fake.dirs['/proc'] = []
    if change == 'malformed-map': fake.reads['/proc/42/maps'] = 'malformed\n'
    result = census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)
    assert result['status'] == 'BLOCKED' and result['blockers']


def test_new_pid_during_census_blocks_even_if_not_in_original_proc_listing():
    fake, report = fixture()
    listdir, count = fake.listdir, 0
    def changed(path):
        nonlocal count
        result = listdir(path)
        if path == '/proc':
            count += 1
            if count > 1: return [*result,'99']
        return result
    fake.listdir = changed
    result = census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)
    assert 'CONSUMER_PROCESS_SET_CHANGED' in result['blockers']


def test_unrelated_anonymous_mapping_churn_is_not_a_target_consumer_change():
    fake, report = fixture()
    read, count = fake.read_text, 0
    def changing(path):
        nonlocal count
        result = read(path)
        if path == '/proc/42/maps':
            count += 1
            if count > 1: return result + '900-999 rw-p 00000000 00:00 0 [heap]\n'
        return result
    fake.read_text = changing
    assert census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)['status'] == 'VERIFIED_ACTIVE_MAPPING_CENSUS'


def test_changed_target_file_is_not_an_authenticated_consumer_index():
    fake, report = fixture()
    fake.fingerprints['/usr/sbin/php-fpm8.1']['sha256'] = 'f'*64
    result = census(report, system=fake, package_ids=['php8.1-fpm:amd64'], now=NOW)
    assert any(b.startswith('CONSUMER_FILE_CHANGED_OR_UNREADABLE') for b in result['blockers'])
