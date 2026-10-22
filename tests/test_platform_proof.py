from dataclasses import replace
import hashlib

import pytest

from conftest import NOW
from test_trust import trust_fixture, DEB, EXECUTABLE
from webpatch.platform_proof import authenticate_service
from webpatch.service import scan
from webpatch.system import DPKG_QUERY, CommandResult, definition_command, environment_files_command, validate_command, PolicyError

SERVICE='php8.1-fpm.service'
UNIT='/lib/systemd/system/'+SERVICE
COMMON='/var/cache/apt/archives/php-common_2%3a92ubuntu1_all.deb'


def fixture():
    fake=trust_fixture()
    report=scan(fake,now=NOW)
    raw='[Service]\nExecStart=/usr/sbin/php-fpm8.1 --nodaemonize\n'
    value=hashlib.sha256(raw.encode()).hexdigest()
    fake.archives[DEB].update(control_metadata_complete=True,payload_files={EXECUTABLE:'c'*64,UNIT:value})
    fake.fingerprints[EXECUTABLE].update(uid=0,mode=0o100755)
    fake.fingerprints[UNIT]={'uid':0,'mode':0o100644,'sha256':value,'device':1,'inode':45}
    fake.reads[UNIT]=raw
    common_control={'Package':'php-common','Version':'2:92ubuntu1','Architecture':'all','Source':'php-defaults'}
    fake.archives[COMMON]={'control':common_control,'control_metadata_complete':True,'archive_sha256':'e'*64,
                           'payload_files':{'/usr/sbin/phpquery':'d'*64},'files':{'/usr/sbin/phpquery':'d'*64}}
    fake.fingerprints[COMMON]={'sha256':'e'*64,'size':100,'device':1,'inode':88}
    fake.fingerprints['/usr/sbin/phpquery']={'uid':0,'mode':0o100755,'sha256':'d'*64,'device':1,'inode':89}
    fake.dirs['/var/cache/apt/archives'].append(COMMON.rsplit('/',1)[1])
    query=fake.commands[DPKG_QUERY]
    fake.commands[DPKG_QUERY]=replace(query,stdout=query.stdout+'php-common\t2:92ubuntu1\tall\tphp-defaults\t2:92ubuntu1\tinstall ok installed\n')
    report.package_trust['candidates'].append({'name':'php-common','version':'2:92ubuntu1','architecture':'all',
        'source_name':'php-defaults','source_version':'2:92ubuntu1','sha256':'e'*64,'size':100})
    fake.commands[definition_command(SERVICE)]=CommandResult(0,'Id='+SERVICE+'\nFragmentPath='+UNIT+'\nDropInPaths=\nEnvironmentFiles=\nRootDirectory=\nRootImage=\nPassEnvironment=\n')
    fake.commands[environment_files_command(SERVICE)]=CommandResult(0,'a(sb) 0\n')
    return fake,report


def test_service_definition_launcher_and_helper_bytes_are_authenticated():
    fake,report=fixture()
    result=authenticate_service(report,system=fake,service=SERVICE,package_cache='/var/cache/apt/archives')
    assert result['status']=='AUTHENTICATED_SERVICE_DEFINITION',result['blockers']
    assert {f['path'] for f in result['files']}=={UNIT,EXECUTABLE,'/usr/sbin/phpquery'}
    assert result['unit_source']['content'].startswith('[Service]')


@pytest.mark.parametrize('mutation', ['unit','launcher','helper','dropin','environment-file','missing-cache','unreadable-definition'])
def test_unknown_service_inputs_cannot_authorize_restart(mutation):
    fake,report=fixture()
    if mutation=='unit': fake.fingerprints[UNIT]['sha256']='f'*64
    if mutation=='launcher': fake.fingerprints[EXECUTABLE]['sha256']='f'*64
    if mutation=='helper': fake.fingerprints['/usr/sbin/phpquery']['sha256']='f'*64
    if mutation in {'dropin','environment-file'}:
        command=definition_command(SERVICE)
        field='DropInPaths' if mutation=='dropin' else 'EnvironmentFiles'
        fake.commands[command]=replace(fake.commands[command],stdout=fake.commands[command].stdout.replace(field+'=\n',field+'=/etc/custom-input\n'))
    if mutation=='missing-cache': fake.dirs['/var/cache/apt/archives']=[]
    if mutation=='unreadable-definition': fake.commands[definition_command(SERVICE)]=CommandResult(1)
    result=authenticate_service(report,system=fake,service=SERVICE,package_cache='/var/cache/apt/archives')
    assert result['status']=='BLOCKED' and result['blockers']


def test_empty_structured_property_requires_typed_bus_observation():
    fake,report=fixture()
    cmd=definition_command(SERVICE)
    fake.commands[cmd]=replace(fake.commands[cmd],stdout=fake.commands[cmd].stdout.replace('EnvironmentFiles=\n',''))
    assert authenticate_service(report,system=fake,service=SERVICE,package_cache='/var/cache/apt/archives')['status']=='AUTHENTICATED_SERVICE_DEFINITION'
    for response in (CommandResult(1),CommandResult(0,''),CommandResult(0,'a(sb) 1 "/etc/custom" false\n')):
        fake.commands[environment_files_command(SERVICE)]=response
        result=authenticate_service(report,system=fake,service=SERVICE,package_cache='/var/cache/apt/archives')
        assert 'SERVICE_ENVIRONMENT_FILES_NOT_VERIFIED_EMPTY' in result['blockers']


def test_bus_command_only_reads_the_fixed_service_property():
    argv=environment_files_command(SERVICE)
    validate_command(argv)
    assert argv[4].endswith('/php8_2e1_2dfpm_2eservice')
    with pytest.raises(PolicyError): validate_command((*argv[:-1],'Environment'))
    with pytest.raises(PolicyError): environment_files_command('ssh.service')
