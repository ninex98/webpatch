from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import tarfile

import pytest

from conftest import NOW
from test_planning import setup_plan
from test_trust import DEB, EXECUTABLE
from webpatch.maintenance import inspect_maintenance, conffiles
from webpatch.planning import plan
from webpatch.system import LocalSystem, ProbeError


def metadata(text, mode=0o755):
    raw = text.encode()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw),'mode':mode,'text':text}


def fixture():
    fake, _, simulator = setup_plan()
    archive = fake.archives[DEB]
    archive.update(control_metadata_complete=True, control_files={
        'postinst': metadata('#!/bin/sh\n# fixture only, never run\nexit 0\n'),
        'conffiles':metadata('/etc/php/8.1/fpm/php-fpm.conf\n', 0o644),
        'triggers':metadata('interest-noawait fixture-php\n', 0o644)},
        payload_files={EXECUTABLE:'c'*64, '/etc/php/8.1/fpm/php-fpm.conf':'a'*64})
    fake.fingerprints['/etc/php/8.1/fpm/php-fpm.conf'] = {'device':1,'inode':500,'sha256':'a'*64,'size':100}
    from webpatch.service import scan
    report = scan(fake, now=NOW)
    proposal = plan(report, system=fake, simulator=simulator, now=NOW)
    return fake, report, proposal


def test_authenticated_old_and_new_control_scripts_are_reviewable_but_not_executed():
    fake, report, proposal = fixture()
    review = inspect_maintenance(report, proposal, system=fake, package_cache='/var/cache/apt/archives', now=NOW)
    assert review['status'] == 'READY_FOR_MAINTENANCE_REVIEW'
    archive = review['archives'][0]
    assert archive['roles'] == ['candidate','installed']
    assert archive['archive_sha256'] == 'b'*64
    assert archive['control_files']['postinst']['text'].startswith('#!/bin/sh')
    assert review['local_conffiles'][0]['status'] == 'UNCHANGED_FROM_AUTHENTICATED_ARCHIVE'
    assert review['installation_effects'] == 'REQUIRES_OPERATOR_REVIEW'
    assert review['trigger_cascade'] == 'NOT_PROVEN' and not review['executable']
    assert all('postinst' not in str(args) and '/bin/sh' not in str(args) for op,args in fake.calls if op == 'run')


@pytest.mark.parametrize('mutation,expected', [
    ('missing','AUTHENTICATED_CONTROL_ARCHIVE_UNAVAILABLE'),
    ('bad-hash','AUTHENTICATED_CONTROL_ARCHIVE_UNAVAILABLE'),
    ('control','CONTROL_ARCHIVE_IDENTITY_MISMATCH'),
    ('opaque','MAINTAINER_SCRIPT_OPAQUE'),
    ('incomplete','CONTROL_METADATA_UNAVAILABLE'),
    ('removal','CONFFILE_REMOVAL_REQUIRES_REVIEW'),
    ('payload','CONFFILE_PAYLOAD_UNVERIFIED'),
    ('local-change','CONFFILE_LOCAL_DECISION_REQUIRED'),
])
def test_incomplete_maintenance_identity_and_configuration_decisions_block(mutation, expected):
    fake, report, proposal = fixture()
    if mutation == 'missing': fake.dirs['/var/cache/apt/archives'] = []
    if mutation == 'bad-hash': fake.fingerprints[DEB]['sha256'] = 'f'*64
    if mutation == 'control': fake.archives[DEB]['control']['Version'] = 'evil'
    if mutation == 'opaque': fake.archives[DEB]['control_files']['postinst']['text'] = None
    if mutation == 'incomplete': fake.archives[DEB]['control_metadata_complete'] = False
    if mutation == 'removal': fake.archives[DEB]['control_files']['conffiles'] = metadata('remove-on-upgrade /etc/php/8.1/fpm/php-fpm.conf\n')
    if mutation == 'payload': del fake.archives[DEB]['payload_files']['/etc/php/8.1/fpm/php-fpm.conf']
    if mutation == 'local-change': fake.fingerprints['/etc/php/8.1/fpm/php-fpm.conf']['sha256'] = 'f'*64
    result = inspect_maintenance(report, proposal, system=fake, package_cache='/var/cache/apt/archives', now=NOW)
    assert result['status'] == 'BLOCKED'
    assert any(expected in b for b in result['blockers'])


@pytest.mark.parametrize('text', ['/a\n/a\n', 'relative\n', '/a/../b\n', '\n', 'unknown-flag /etc/a\n'])
def test_conffile_ambiguity_is_rejected(text):
    with pytest.raises(ValueError): conffiles({'conffiles':metadata(text)})


def tar(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, text in members.items():
            raw = text.encode()
            member = tarfile.TarInfo(name)
            member.mode = 0o755
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return buffer.getvalue()


def test_archive_reader_retains_control_data_without_running_it(monkeypatch):
    controls = tar({'control':'Package: php8.1-fpm\nVersion: 1\nArchitecture: amd64\n',
                    'postinst':'#!/bin/sh\nprintf never-executed\n', 'conffiles':'/etc/php/test.conf\n'})
    payload = tar({'usr/sbin/php-fpm8.1':'fixture executable bytes','etc/php/test.conf':'config bytes'})
    calls = []
    def execute(self, argv, limit=None):
        calls.append(argv)
        return 0, controls if argv[1] == '--ctrl-tarfile' else payload, b''
    monkeypatch.setattr(LocalSystem, '_execute', execute)
    result = LocalSystem().package_archive('/cache/test.deb')
    assert result['control_metadata_complete']
    assert 'never-executed' in result['control_files']['postinst']['text']
    assert '/etc/php/test.conf' in result['payload_files']
    assert '/etc/php/test.conf' not in result['files']
    assert all(c[0] == '/usr/bin/dpkg-deb' for c in calls)
