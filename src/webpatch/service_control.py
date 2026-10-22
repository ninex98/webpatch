"""Explicit Linux service preparation capability, separate from SystemReader."""
from contextlib import contextmanager
try:
    import fcntl
except ImportError:
    fcntl = None
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time
import tempfile

from .receipts import ReceiptStore
from .system import ProbeError


class LocalServiceControl:
    def __init__(self, state_dir='/var/lib/webpatch'):
        if not re.fullmatch(r'/var/lib/webpatch(?:-[a-z0-9-]+)?',state_dir):
            raise ValueError('SERVICE_STATE_DIRECTORY_INVALID')
        self.state_dir = Path(state_dir)
        self.store = ReceiptStore(self.state_dir)
        self.owns_package_lock = False
        self._lock_descriptors = ()

    @staticmethod
    def require_root():
        if sys.platform != 'linux' or fcntl is None or os.geteuid() != 0:
            raise ProbeError('SERVICE_CONTROL_REQUIRES_LINUX_ROOT')

    @contextmanager
    def locked(self):
        self.require_root()
        if self.owns_package_lock:
            raise ProbeError('SERVICE_LOCK_ALREADY_OWNED')
        self.store._key(create=True)
        descriptors = []
        try:
            for path in (self.state_dir/'operation.lock', Path('/var/lib/dpkg/lock-frontend')):
                flags = os.O_RDWR | getattr(os,'O_NOFOLLOW',0)
                if path.parent == self.state_dir: flags |= os.O_CREAT
                descriptor = os.open(path, flags, 0o600)
                descriptors.append(descriptor)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
                    raise ProbeError('SERVICE_LOCK_IDENTITY_INVALID')
                fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.owns_package_lock = True
            self._lock_descriptors = tuple(descriptors)
            yield
        finally:
            self.owns_package_lock = False
            self._lock_descriptors = ()
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def frontend_lock_identity(self):
        self.require_root()
        if not self.owns_package_lock or len(self._lock_descriptors)!=2:
            raise ProbeError('PACKAGE_FRONTEND_LOCK_NOT_OWNED')
        info=os.fstat(self._lock_descriptors[1])
        return {'path':'/var/lib/dpkg/lock-frontend','device':info.st_dev,'inode':info.st_ino,'pid':os.getpid()}

    def command(self, action, service=None, timeout_seconds=60):
        self.require_root()
        if type(timeout_seconds) not in {int,float} or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=60:
            raise ProbeError('SERVICE_CONTROL_BUDGET_INVALID')
        if action == 'daemon-reload' and service is None:
            argv = ('/usr/bin/systemctl','daemon-reload')
        elif action in {'restart','stop','start'} and isinstance(service,str) and re.fullmatch(r'(?:php[0-9]+\.[0-9]+-fpm|apache2)\.service',service):
            argv = ('/usr/bin/systemctl',action,service)
        else:
            raise ProbeError('SERVICE_MUTATION_NOT_ALLOWLISTED')
        env = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C'}
        buffers = [bytearray(),bytearray()]
        with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              env=env,cwd='/',shell=False) as child:
            deadline = time.monotonic()+timeout_seconds
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout,selectors.EVENT_READ,0)
                    selector.register(child.stderr,selectors.EVENT_READ,1)
                    while selector.get_map():
                        if time.monotonic() >= deadline: raise ProbeError('SERVICE_CONTROL_TIMEOUT')
                        for key,_ in selector.select(min(0.1, max(0.001,deadline-time.monotonic()))):
                            chunk = os.read(key.fileobj.fileno(),65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                            else:
                                buffers[key.data].extend(chunk)
                                if sum(map(len,buffers))>1048576: raise ProbeError('SERVICE_CONTROL_OUTPUT_LIMIT')
                    child.wait(timeout=max(0.001,deadline-time.monotonic()))
            except BaseException:
                child.kill(); child.wait(); raise
        if child.returncode or buffers[1]:
            raise ProbeError('SERVICE_CONTROL_FAILED_OR_WARNED')
        return {'action':action,'service':service,'result':'PASS',
                'output_sha256':hashlib.sha256(bytes(buffers[0])+b'\0'+bytes(buffers[1])).hexdigest()}

    def wait_stable(self, service, timeout_seconds=10):
        self.require_root()
        if type(timeout_seconds) not in {int,float} or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=10:
            raise ProbeError('SERVICE_STABILITY_BUDGET_INVALID')
        if not re.fullmatch(r'(?:php[0-9]+\.[0-9]+-fpm|apache2)\.service',service):
            raise ProbeError('SERVICE_MUTATION_NOT_ALLOWLISTED')
        path = Path('/sys/fs/cgroup/system.slice')/service/'cgroup.procs'
        previous, stable = None, 0
        deadline=time.monotonic()+timeout_seconds
        for _ in range(40):
            if time.monotonic()>=deadline: break
            current = tuple(sorted(path.read_text().split()))
            stable = stable+1 if current and current==previous else 0
            if stable>=4: return
            previous = current
            time.sleep(0.25)
        raise ProbeError('SERVICE_PROCESS_SET_DID_NOT_SETTLE')

    def materialize(self, plan, system):
        self.require_root()
        root = self.state_dir/'snapshots'/plan['preparation_sha256']
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        snapshots = []
        for index, tree in enumerate(plan['configuration']):
            source_root = Path(tree['root'])
            destination = root/('tree-'+str(index))
            destination.mkdir(mode=0o755)
            files = []
            for item in tree['files']:
                source = Path(item['path'])
                relative = source.relative_to(source_root)
                if '..' in relative.parts: raise ProbeError('SNAPSHOT_PATH_INVALID')
                raw = system.read_text(str(source))
                if hashlib.sha256(raw.encode()).hexdigest() != item['sha256']:
                    raise ProbeError('SNAPSHOT_INPUT_CHANGED')
                target = destination/relative
                target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
                with target.open('xb') as stream: stream.write(raw.encode('utf-8'))
                target.chmod(0o444)
                info = target.stat()
                files.append({'path':str(source),'sha256':item['sha256'],'device':info.st_dev,'inode':info.st_ino})
            snapshots.append({'service':tree['service'],'root':tree['root'],'snapshot':str(destination),'files':files})
        overrides, definitions_to_write = [], []
        for service in plan['services']:
            if not re.fullmatch(r'(?:php[0-9]+\.[0-9]+-fpm|apache2)\.service',service):
                raise ProbeError('SERVICE_MUTATION_NOT_ALLOWLISTED')
            definition = next(d for d in plan['definitions'] if d['service']==service)
            unit_source = definition['unit_source']
            if hashlib.sha256(unit_source['content'].encode()).hexdigest()!=unit_source['sha256']:
                raise ProbeError('SERVICE_UNIT_SOURCE_DIGEST_MISMATCH')
            path = Path('/run/systemd/system')/service
            content = unit_source['content']+'\n[Service]\n'+''.join('BindReadOnlyPaths='+s['snapshot']+':'+s['root']+'\n' for s in snapshots if s['service']==service)
            if path.exists() or path.is_symlink():
                raise ProbeError('SERVICE_RUNTIME_DEFINITION_ALREADY_EXISTS')
            definitions_to_write.append((service,path,content))
        try:
            for service,path,content in definitions_to_write:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(mode='wb',prefix='.webpatch-',suffix='.tmp',dir=path.parent,delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(content.encode('utf-8')); stream.flush(); os.fsync(stream.fileno())
                        os.fchmod(stream.fileno(),0o644)
                    os.link(temporary,path)  # atomic, refuses an existing definition
                    overrides.append({'service':service,'path':str(path),'sha256':hashlib.sha256(content.encode()).hexdigest()})
                finally:
                    if temporary is not None: temporary.unlink(missing_ok=True)
        except Exception:
            for item in overrides:
                path = Path(item['path'])
                if not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']:
                    path.unlink()
            raise
        return {'snapshots':snapshots,'overrides':overrides}

    def verify_loaded_definitions(self, record, system):
        from .system import definition_command
        for item in record['overrides']:
            response = system.run(definition_command(item['service']))
            props = dict(line.split('=',1) for line in response.stdout.splitlines() if '=' in line)
            if response.returncode or response.stderr or props.get('FragmentPath')!=item['path'] or props.get('DropInPaths')!='':
                raise ProbeError('SERVICE_LOADED_DEFINITION_MISMATCH')
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
                raise ProbeError('SERVICE_RUNTIME_DEFINITION_CHANGED')

    def retire_overrides(self, record):
        """Remove only this collector's unchanged runtime units; active mounts persist."""
        self.require_root()
        for item in record['overrides']:
            if not re.fullmatch(r'(?:php[0-9]+\.[0-9]+-fpm|apache2)\.service',item['service']):
                raise ProbeError('SERVICE_MUTATION_NOT_ALLOWLISTED')
            expected = Path('/run/systemd/system')/item['service']
            if str(expected) != item['path'] or expected.is_symlink() or hashlib.sha256(expected.read_bytes()).hexdigest() != item['sha256']:
                raise ProbeError('OWNED_SERVICE_OVERRIDE_CHANGED')
        for item in record['overrides']:
            Path(item['path']).unlink()
        self.command('daemon-reload')
