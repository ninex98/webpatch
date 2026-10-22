"""Bounded dpkg capability. This module does not decide repair admission.

The policy layer must authenticate and approve the complete exact package and
trigger set before calling it. No argv from a saved document is ever executed.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from .service_control import LocalServiceControl
from .system import DPKG_QUERY, ProbeError
from .transaction import StepResult
from .planning import digest

POLICY = b'#!/bin/sh\n# WebPatch approved maintenance: suppress service autostart.\nexit 101\n'
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?\Z')


@dataclass(frozen=True)
class ApprovedArchive:
    name: str
    architecture: str
    version: str
    path: str
    sha256: str


@dataclass(frozen=True)
class PackageOperation:
    transaction_sha256: str
    archives: tuple[ApprovedArchive, ...]
    trigger_handlers: tuple[str, ...]
    timeout_seconds: int = 180

    def validate(self):
        if (not re.fullmatch(r'[0-9a-f]{64}',self.transaction_sha256) or not self.archives
                or len(self.archives)>128 or type(self.timeout_seconds) is not int
                or not 10<=self.timeout_seconds<=600):
            raise ProbeError('PACKAGE_OPERATION_INVALID')
        seen=set()
        for item in self.archives:
            key=(item.name,item.architecture)
            if (not NAME.fullmatch(item.name) or ':' in item.name or not re.fullmatch(r'[a-z0-9-]+',item.architecture)
                    or not re.fullmatch(r'[0-9][0-9A-Za-z.+:~\-]*',item.version)
                    or not re.fullmatch(r'[0-9a-f]{64}',item.sha256) or key in seen):
                raise ProbeError('PACKAGE_ARCHIVE_SPEC_INVALID')
            seen.add(key)
        if (len(self.trigger_handlers)>128 or len(set(self.trigger_handlers))!=len(self.trigger_handlers)
                or any(not NAME.fullmatch(p) for p in self.trigger_handlers)):
            raise ProbeError('PACKAGE_TRIGGER_SPEC_INVALID')


def database_rows(query):
    rows=[line.split('\t') for line in query.stdout.splitlines()]
    if (query.returncode or query.stderr or not rows or any(len(row)!=6 or not NAME.fullmatch(row[0]) for row in rows)
            or len({(row[0],row[2]) for row in rows})!=len(rows)):
        raise ProbeError('PACKAGE_DATABASE_QUERY_INVALID')
    return rows


def pending_triggers(query):
    return tuple(sorted(row[0] for row in database_rows(query) if row[5].endswith('triggers-pending')))


class LocalPackageControl(LocalServiceControl):
    """Own the frontend lock; dpkg retains its own backend database lock."""

    def require_lock(self):
        self.require_root()
        if not self.owns_package_lock: raise ProbeError('PACKAGE_LOCK_REQUIRED')

    def stage_archives(self, operation, system):
        self.require_lock()
        operation.validate()
        root=self.state_dir/'transactions'/operation.transaction_sha256
        root.mkdir(mode=0o700,parents=True,exist_ok=False)
        paths=[]
        for item in operation.archives:
            # Verify the sealed parser's identity, then copy while hashing again.
            archive=system.package_archive((item.path,item.sha256))
            control=archive.get('control',{})
            if ((control.get('Package'),control.get('Architecture'),control.get('Version'))
                    !=(item.name,item.architecture,item.version) or archive.get('archive_sha256')!=item.sha256):
                raise ProbeError('PACKAGE_ARCHIVE_IDENTITY_CHANGED')
            destination=root/(item.sha256+'.deb')
            descriptor=os.open(item.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(descriptor,'rb') as source:
                info=os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size>256*1024*1024:
                    raise ProbeError('PACKAGE_ARCHIVE_TYPE_OR_SIZE_INVALID')
                value=hashlib.sha256(); count=0
                with destination.open('xb') as target:
                    while chunk:=source.read(65536):
                        count+=len(chunk)
                        if count>256*1024*1024: raise ProbeError('PACKAGE_ARCHIVE_SIZE_LIMIT')
                        value.update(chunk); target.write(chunk)
                    target.flush(); os.fsync(target.fileno()); os.fchmod(target.fileno(),0o400)
                if value.hexdigest()!=item.sha256:
                    destination.unlink()
                    raise ProbeError('PACKAGE_ARCHIVE_CHANGED_DURING_STAGING')
            paths.append(destination)
        return root,tuple(paths)

    @contextmanager
    def suppress_service_start(self):
        self.require_lock()
        path=Path('/usr/sbin/policy-rc.d')
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(prefix='.webpatch-policy-',dir=path.parent,delete=False) as stream:
                temporary=Path(stream.name)
                stream.write(POLICY); stream.flush(); os.fsync(stream.fileno())
                os.fchmod(stream.fileno(),0o755)
                identity=os.fstat(stream.fileno())
            os.link(temporary,path)  # publish complete bytes atomically, never replace
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)
        try:
            yield
        finally:
            current=path.lstat()
            if (not stat.S_ISREG(current.st_mode) or (current.st_dev,current.st_ino)!=(identity.st_dev,identity.st_ino)
                    or current.st_uid!=0 or path.read_bytes()!=POLICY):
                raise ProbeError('PACKAGE_OWNED_SERVICE_POLICY_CHANGED')
            path.unlink()

    def run_dpkg(self, action, arguments, root, timeout):
        self.require_lock()
        if action=='unpack':
            if not arguments or any(Path(p).parent!=root or not re.fullmatch(r'[0-9a-f]{64}\.deb',Path(p).name) for p in arguments):
                raise ProbeError('PACKAGE_UNPACK_ARGUMENT_INVALID')
        elif action in {'configure','triggers-only'}:
            if not arguments or any(not NAME.fullmatch(p) for p in arguments):
                raise ProbeError('PACKAGE_CONFIGURE_ARGUMENT_INVALID')
        else:
            raise ProbeError('PACKAGE_ACTION_NOT_ALLOWLISTED')
        argv=('/usr/bin/dpkg','--no-triggers','--'+action,*map(str,arguments))
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C',
             'DPKG_FRONTEND_LOCKED':'true','DEBIAN_FRONTEND':'noninteractive','DEBIAN_PRIORITY':'critical'}
        # No inherited environment or personal dpkg configuration is consumed.
        private_home=root/'empty-home'
        private_home.mkdir(mode=0o700,exist_ok=True)
        env['HOME']=str(private_home)
        output=bytearray(); deadline=time.monotonic()+timeout
        with subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              env=env,cwd='/',shell=False,start_new_session=True) as child:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout,selectors.EVENT_READ)
                    while selector.get_map():
                        if time.monotonic()>=deadline: raise ProbeError('PACKAGE_COMMAND_TIMEOUT')
                        for key,_ in selector.select(0.1):
                            chunk=os.read(key.fileobj.fileno(),65536)
                            if not chunk: selector.unregister(key.fileobj)
                            else:
                                output.extend(chunk)
                                if len(output)>8*1024*1024: raise ProbeError('PACKAGE_COMMAND_OUTPUT_LIMIT')
                    child.wait(timeout=max(0.001,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGKILL); child.wait(); raise
            finally:
                # Package scripts can print site-specific values: private logs only.
                log=root/('dpkg-'+action+'-'+str(time.time_ns())+'.log')
                with log.open('xb') as stream:
                    os.fchmod(stream.fileno(),0o600); stream.write(output)
        return {'action':action,'returncode':child.returncode,'output_sha256':hashlib.sha256(output).hexdigest(),
                'log':str(log)}

    def install_operation(self, operation, system):
        self.require_lock()
        changed=False; results=[]
        try:
            root,paths=self.stage_archives(operation,system)
            with self.suppress_service_start():
                changed=True
                for action,args in (('unpack',paths),('configure',tuple(a.name+':'+a.architecture for a in operation.archives))):
                    row=self.run_dpkg(action,args,root,operation.timeout_seconds); results.append(row)
                    if row['returncode']:
                        return StepResult(False,True,digest(results),'PACKAGE_'+action.upper()+'_FAILED')
                for _ in range(4):
                    pending=pending_triggers(system.run(DPKG_QUERY))
                    if not pending: break
                    if not set(pending)<=set(operation.trigger_handlers):
                        return StepResult(False,True,digest(results),'PACKAGE_UNAPPROVED_TRIGGER_PENDING')
                    row=self.run_dpkg('triggers-only',pending,root,operation.timeout_seconds); results.append(row)
                    if row['returncode']: return StepResult(False,True,digest(results),'PACKAGE_TRIGGER_FAILED')
                else:
                    return StepResult(False,True,digest(results),'PACKAGE_TRIGGER_CASCADE_LIMIT')
            query=system.run(DPKG_QUERY)
            metadata={(row[0],row[2]):row for row in database_rows(query)}
            if (query.returncode or query.stderr or not metadata
                    or any(row[5].startswith('install ') and row[5]!='install ok installed' for row in metadata.values())):
                return StepResult(False,True,digest(results),'PACKAGE_INCOMPLETE_DATABASE_STATE')
            for item in operation.archives:
                row=metadata.get((item.name,item.architecture)) or metadata.get((item.name+':'+item.architecture,item.architecture))
                if query.returncode or query.stderr or not row or row[1]!=item.version or row[5]!='install ok installed':
                    return StepResult(False,True,digest(results),'PACKAGE_FINAL_DATABASE_STATE_MISMATCH')
            return StepResult(True,True,digest(results),'EXACT_PACKAGES_CONFIGURED_RUNTIME_VERIFICATION_REQUIRED')
        except (OSError,ValueError,ProbeError) as exc:
            return StepResult(False,changed,digest(results),'PACKAGE_OPERATION_FAILED:'+type(exc).__name__)
