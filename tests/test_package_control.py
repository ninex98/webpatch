from contextlib import contextmanager
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from webpatch.package_control import ApprovedArchive, PackageOperation, LocalPackageControl, pending_triggers
from webpatch.system import CommandResult, ProbeError


def operation(tmp_path):
    path=tmp_path/'candidate.deb'; path.write_bytes(b'fixture archive')
    archive=ApprovedArchive('php8.1-fpm','amd64','8.1.2-1ubuntu2.28',str(path),hashlib.sha256(path.read_bytes()).hexdigest())
    return PackageOperation('a'*64,(archive,),('libc-bin',))


def test_operation_rejects_duplicate_or_command_shaped_inputs(tmp_path):
    value=operation(tmp_path)
    value.validate()
    for bad in (replace(value,archives=value.archives*2),replace(value,trigger_handlers=('--pending',)),
                replace(value,timeout_seconds=True),replace(value,archives=(replace(value.archives[0],name='--force'),))):
        with pytest.raises(ProbeError): bad.validate()


def test_pending_trigger_packages_are_exact_and_multiarch_aware():
    assert pending_triggers(CommandResult(0,'one\t1\tall\tone\t1\tinstall ok installed\ntwo:amd64\t1\tamd64\ttwo\t1\tinstall ok triggers-pending\n'))==('two:amd64',)


class Reader:
    def package_archive(self,request):
        return {'archive_sha256':request[1],'control':{'Package':'php8.1-fpm','Architecture':'amd64','Version':'8.1.2-1ubuntu2.28'}}
    def run(self,argv): return CommandResult(0,'php8.1-fpm\t8.1.2-1ubuntu2.28\tamd64\tphp8.1\t8.1.2-1ubuntu2.28\tinstall ok installed\nlibc-bin\t1\tamd64\tglibc\t1\tinstall ok triggers-pending\n')


class Control(LocalPackageControl):
    def __init__(self,path):
        self.state_dir=path; self.owns_package_lock=True; self.calls=[]
    def require_root(self): pass
    @contextmanager
    def suppress_service_start(self): yield
    def run_dpkg(self,action,args,root,timeout):
        self.calls.append((action,args))
        return {'action':action,'returncode':0}


def test_archive_race_is_rejected_before_package_process(tmp_path):
    value=operation(tmp_path); controller=Control(tmp_path/'state')
    class RacingReader(Reader):
        def package_archive(self,request):
            result=super().package_archive(request)
            Path(request[0]).write_bytes(b'replaced after sealed verification')
            return result
    result=controller.install_operation(value,RacingReader())
    assert not result.success and not result.changed and not controller.calls


def test_no_lock_means_no_archive_or_process_work(tmp_path):
    control=Control(tmp_path/'state'); control.owns_package_lock=False
    with pytest.raises(ProbeError,match='PACKAGE_LOCK_REQUIRED'):
        control.install_operation(operation(tmp_path),Reader())


def test_unapproved_trigger_never_executes_handler(tmp_path):
    control=Control(tmp_path/'state')
    result=control.install_operation(replace(operation(tmp_path),trigger_handlers=()),Reader())
    assert not result.success and result.changed and result.reason=='PACKAGE_UNAPPROVED_TRIGGER_PENDING'
    assert [c[0] for c in control.calls]==['unpack','configure']


def test_trigger_cascade_is_bounded_and_staging_never_reused(tmp_path):
    control=Control(tmp_path/'state'); value=operation(tmp_path)
    result=control.install_operation(value,Reader())
    assert not result.success and result.reason=='PACKAGE_TRIGGER_CASCADE_LIMIT'
    assert len(control.calls)==6
    again=control.install_operation(value,Reader())
    assert not again.success and not again.changed and len(control.calls)==6


def test_exact_configured_versions_still_require_runtime_verification(tmp_path):
    control=Control(tmp_path/'state')
    reader=Reader(); reader.run=lambda argv:replace(Reader().run(argv),stdout=Reader().run(argv).stdout.replace('triggers-pending','installed'))
    result=control.install_operation(operation(tmp_path),reader)
    assert result.success and result.changed
    assert result.reason=='EXACT_PACKAGES_CONFIGURED_RUNTIME_VERIFICATION_REQUIRED'


def test_process_capability_cannot_execute_arbitrary_actions(tmp_path):
    control=Control(tmp_path/'state')
    with pytest.raises(ProbeError,match='PACKAGE_ACTION_NOT_ALLOWLISTED'):
        LocalPackageControl.run_dpkg(control,'remove',('php8.1-fpm',),tmp_path,10)
    with pytest.raises(ProbeError,match='PACKAGE_UNPACK_ARGUMENT_INVALID'):
        LocalPackageControl.run_dpkg(control,'unpack',('/tmp/unreviewed.deb',),tmp_path,10)
