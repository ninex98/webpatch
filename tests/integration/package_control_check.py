"""Harmless native dpkg lifecycle, restricted to the disposable build container.

Synthetic archives exercise the capability only, not vendor admission or PHP
repair. No network, host mounts, service manager or exploit is involved.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from webpatch.package_control import ApprovedArchive, PackageOperation, LocalPackageControl
from webpatch.system import LocalSystem

assert os.environ.get('WEBPATCH_DISPOSABLE_CONTAINER')=='1' and Path('/.dockerenv').is_file()
assert Path.cwd()==Path('/work') and os.geteuid()==0


def package(root,name,version,*,script='',trigger=False):
    tree=root/(name+'-'+version)
    control=tree/'DEBIAN'; control.mkdir(parents=True)
    (control/'control').write_text(f'Package: {name}\nVersion: {version}\nArchitecture: all\nMaintainer: WebPatch test <test@example.invalid>\nDescription: Harmless isolated lifecycle fixture\n')
    if script:
        (control/'postinst').write_text('#!/bin/sh\nset -e\n'+script+'\n'); (control/'postinst').chmod(0o755)
    if trigger: (control/'triggers').write_text('interest-noawait /usr/share/webpatch-driver-test\n')
    else:
        directory=tree/'usr/share/webpatch-driver-test'; directory.mkdir(parents=True)
        (directory/'version').write_text(version+'\n')
    destination=root/(name+'_'+version+'_all.deb')
    subprocess.run(['/usr/bin/dpkg-deb','--build',str(tree),str(destination)],check=True,capture_output=True)
    return ApprovedArchive(name,'all',version,str(destination),hashlib.sha256(destination.read_bytes()).hexdigest())


with tempfile.TemporaryDirectory(prefix='webpatch-driver-native-') as directory:
    root=Path(directory)
    first=package(root,'webpatch-driver-test','1')
    second=package(root,'webpatch-driver-test','2',script='echo configured >> /var/lib/webpatch-driver-events')
    failing=package(root,'webpatch-driver-test','3',script='exit 42')
    handler=package(root,'webpatch-driver-handler','1',trigger=True,
                    script='if [ "$1" = triggered ]; then echo triggered >> /var/lib/webpatch-driver-events; fi')
    subprocess.run(['/usr/bin/dpkg','--install',handler.path,first.path],check=True,capture_output=True)
    Path('/var/lib/webpatch-driver-events').unlink(missing_ok=True)
    controller=LocalPackageControl('/var/lib/webpatch-ci-driver'); reader=LocalSystem()
    policy=Path('/usr/sbin/policy-rc.d'); backup=root/'container-policy'
    if policy.exists(): policy.rename(backup)
    try:
        outcomes={}
        with controller.locked():
            locked=subprocess.run(['/usr/bin/python3','-c',
                'import fcntl; f=open("/var/lib/dpkg/lock-frontend","r+"); fcntl.lockf(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'],capture_output=True)
            assert locked.returncode!=0 and b'BlockingIOError' in locked.stderr
            operation=PackageOperation(hashlib.sha256(b'native-upgrade').hexdigest(),(second,),('webpatch-driver-handler',))
            result=controller.install_operation(operation,reader); outcomes['upgrade']=asdict(result)
            assert result.success and result.changed,result
            assert Path('/usr/share/webpatch-driver-test/version').read_text()=='2\n'
            events=Path('/var/lib/webpatch-driver-events').read_text().splitlines()
            assert events==['configured','triggered'],events
            assert not policy.exists()
            bad=PackageOperation(hashlib.sha256(b'native-failure').hexdigest(),(failing,),('webpatch-driver-handler',))
            result=controller.install_operation(bad,reader); outcomes['failure']=asdict(result)
            assert not result.success and result.changed and result.reason=='PACKAGE_CONFIGURE_FAILED',result
            assert not policy.exists()
        subprocess.run(['/usr/bin/dpkg','--remove','webpatch-driver-test','webpatch-driver-handler'],check=True,capture_output=True)
        print(json.dumps({'result':'PASS','scope':'synthetic native capability, not PHP repair','frontend_lock':'PASS',**outcomes}))
    finally:
        if backup.exists(): backup.rename(policy)
