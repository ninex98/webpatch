from copy import deepcopy
from dataclasses import replace

import pytest

from conftest import NOW
from test_maintenance import fixture as maintenance_fixture
from test_trust import trust_fixture, DEB, INDEX
from webpatch.execution_inputs import audit_execution_inputs
from webpatch.maintenance import inspect_maintenance, SCRIPTS
from webpatch.planning import choose_targets
from webpatch.service import scan
from webpatch.system import Collector, DPKG_QUERY, ProbeError
from webpatch.trust import metadata_only_archive


def metadata_archive():
    return {'files':{},'payload_entries':{
        '/usr':{'kind':'directory','mode':0o755,'link_target':None},
        '/usr/share/doc/php8.1/copyright':{'kind':'regular','mode':0o644,'link_target':None}},
        'control_metadata_complete':True,'control_files':{}}


def test_metadata_only_is_positive_payload_classification_not_empty_discovery():
    archive=metadata_archive()
    assert metadata_only_archive(archive)
    for mutation in ('empty','runtime-link','escaped-link','script'):
        changed=deepcopy(archive)
        if mutation=='empty': changed['payload_entries']={}
        if mutation=='runtime-link': changed['payload_entries']['/usr/bin/php']={'kind':'symlink','link_target':'/opt/custom/php'}
        if mutation=='escaped-link': changed['payload_entries']['/usr/share/doc/php8.1/link']={'kind':'symlink','link_target':'/etc/passwd'}
        if mutation=='script': changed['control_files']['postinst']={'text':'unknown effects'}
        assert not metadata_only_archive(changed)


def test_engine_with_empty_runtime_payload_does_not_gain_metadata_only_trust():
    fake=trust_fixture()
    fake.archives[DEB].update(metadata_archive())
    result=scan(fake,now=NOW)
    assert result.package_trust['installed'][0]['status']=='UNKNOWN'
    assert not result.safe


def test_phpdbg_archive_identity_is_separate_from_web_runtime_support():
    fake=trust_fixture()
    old=DEB; new=DEB.replace('php8.1-fpm_','php8.1-phpdbg_')
    query=fake.commands[DPKG_QUERY]
    fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('php8.1-fpm\t','php8.1-phpdbg\t'))
    fake.indexes[INDEX]['packages'][0]['Package']='php8.1-phpdbg'
    fake.indexes[INDEX]['packages'][0]['Filename']=fake.indexes[INDEX]['packages'][0]['Filename'].replace('php8.1-fpm_','php8.1-phpdbg_')
    fake.archives[new]=fake.archives.pop(old); fake.archives[new]['control']['Package']='php8.1-phpdbg'
    fake.archives[new]['files']={'/usr/bin/phpdbg8.1':'c'*64}
    fake.fingerprints['/usr/bin/phpdbg8.1']=fake.fingerprints['/usr/sbin/php-fpm8.1'].copy()
    fake.fingerprints[new]=fake.fingerprints.pop(old)
    fake.dirs['/var/cache/apt/archives']=[new.rsplit('/',1)[1]]
    report=scan(fake,now=NOW)
    assert report.package_trust['installed'][0]['status']=='AUTHENTICATED_RUNTIME_FILES'
    assert all(a.version_status=='UNKNOWN' and a.reason=='PACKAGE_NOT_A_COVERED_ENGINE_BINARY' for a in report.assessments)
    assert not report.safe


def test_explicit_source_cohort_includes_authenticated_metadata_component():
    fake=trust_fixture()
    new_path=DEB.replace('php8.1-fpm_','php8.1_')
    query=fake.commands[DPKG_QUERY]
    fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout.replace('php8.1-fpm\t','php8.1\t'))
    fake.indexes[INDEX]['packages'][0]['Package']='php8.1'
    fake.indexes[INDEX]['packages'][0]['Filename']=fake.indexes[INDEX]['packages'][0]['Filename'].replace('php8.1-fpm_','php8.1_')
    archive=fake.archives.pop(DEB)
    archive['control']['Package']='php8.1'
    archive.update(metadata_archive())
    fake.archives[new_path]=archive
    fake.fingerprints[new_path]=fake.fingerprints.pop(DEB)
    fake.dirs['/var/cache/apt/archives']=[new_path.rsplit('/',1)[1]]
    report=scan(fake,now=NOW)
    assert report.package_trust['installed'][0]['status']=='AUTHENTICATED_METADATA_ONLY_ARCHIVE'
    assert choose_targets(report,Collector(fake),NOW)[0]==()
    targets,blockers=choose_targets(report,Collector(fake),NOW,include_components=True)
    assert len(targets)==1 and targets[0].name=='php8.1' and not blockers
    assert not report.safe


def execution_fixture():
    fake,report,proposal=maintenance_fixture()
    inspection=inspect_maintenance(report,proposal,system=fake,package_cache='/var/cache/apt/archives',now=NOW)
    for archive in inspection['archives']:
        for name in SCRIPTS|{'triggers'}:
            path='/var/lib/dpkg/info/'+archive['info_basename']+'.'+name
            value=archive['control_files'].get(name)
            fake.fingerprints[path]=({'uid':0,'mode':0o100000|value['mode'],'sha256':value['sha256'],'device':1,'inode':123}
                                     if value else ProbeError('FileNotFoundError'))
    fake.reads['/etc/dpkg/dpkg.cfg']='# fixture\nno-debsig\nlog /var/log/dpkg.log\n'
    fake.dirs['/etc/dpkg/dpkg.cfg.d']=[]
    fake.fingerprints['/usr/sbin/policy-rc.d']=ProbeError('FileNotFoundError')
    fake.reads['/var/lib/dpkg/triggers/File']='/etc/php php8.1-fpm/noawait other-handler\n/usr/share/man man-db/noawait\n'
    fake.reads['/var/lib/dpkg/triggers/Unincorp']=''
    return fake,inspection


def test_installed_script_bytes_configuration_and_trigger_handlers_are_reviewable():
    fake,inspection=execution_fixture()
    result=audit_execution_inputs(inspection,system=fake)
    assert result['status']=='READY_FOR_EXECUTION_POLICY_REVIEW',result['blockers']
    assert result['triggers']['package_names']==['other-handler','php8.1-fpm']
    assert result['triggers']['named_script_activations']=='REQUIRES_EXPLICIT_REVIEW'
    assert not result['executable']


@pytest.mark.parametrize('mutation', ['changed-script','unexpected-script','owner','mode','config','pending','policy','registry'])
def test_unknown_execution_inputs_remain_blocked(mutation):
    fake,inspection=execution_fixture()
    base='/var/lib/dpkg/info/php8.1-fpm.'
    if mutation=='changed-script': fake.fingerprints[base+'postinst']['sha256']='f'*64
    if mutation=='unexpected-script': fake.fingerprints[base+'preinst']={'uid':0,'mode':0o100755,'sha256':'f'*64}
    if mutation=='owner': fake.fingerprints[base+'postinst']['uid']=1000
    if mutation=='mode': fake.fingerprints[base+'postinst']['mode']=0o100777
    if mutation=='config': fake.reads['/etc/dpkg/dpkg.cfg']='force-confnew\n'
    if mutation=='pending': fake.reads['/var/lib/dpkg/triggers/Unincorp']='unknown-trigger target\n'
    if mutation=='policy': fake.fingerprints['/usr/sbin/policy-rc.d']={'sha256':'f'*64,'uid':0,'mode':0o100755}
    if mutation=='registry': fake.reads['/var/lib/dpkg/triggers/File']='unparseable registry'
    result=audit_execution_inputs(inspection,system=fake)
    assert result['status']=='BLOCKED' and result['blockers']
