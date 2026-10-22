"""Disposable nested Debian VM. Never run on developer or production hosts."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request

assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
parser=argparse.ArgumentParser();parser.add_argument('release',choices=('12','13'));parser.add_argument('sapi',choices=('fpm','apache'))
args=parser.parse_args()
output=Path('ci-evidence');output.mkdir(exist_ok=True)
workspace=Path(tempfile.mkdtemp(prefix='webpatch-debian-vm-',dir=os.environ['RUNNER_TEMP']))
codename='bookworm' if args.release=='12' else 'trixie'
base=f'https://cloud.debian.org/images/cloud/{codename}/latest/'
filename=f'debian-{args.release}-genericcloud-amd64.qcow2'


def fetch(url,path):
    with urllib.request.urlopen(url,timeout=60) as response,path.open('wb') as stream:
        shutil.copyfileobj(response,stream,1024*1024)


fetch(base+'SHA512SUMS',workspace/'SHA512SUMS')
matches=[line.split()[0] for line in (workspace/'SHA512SUMS').read_text().splitlines()
         if len(line.split())==2 and line.split()[1].lstrip('*')==filename]
assert len(matches)==1 and re.fullmatch(r'[0-9a-f]{128}',matches[0])
fetch(base+filename,workspace/'base.qcow2')
hasher=hashlib.sha512()
with (workspace/'base.qcow2').open('rb') as stream:
    while chunk:=stream.read(1024*1024): hasher.update(chunk)
assert hasher.hexdigest()==matches[0]
(output/'guest-image.json').write_text(json.dumps({'url':base+filename,'sha512':matches[0],
    'checksum_source':base+'SHA512SUMS','transport':'official Debian HTTPS',
    'image_signature':'NOT_AVAILABLE_IN_THIS_CLOUD_DIRECTORY',
    'claim':'Recorded test-image transport/integrity; not a signed image attestation or product runtime-safety result.'},indent=2)+'\n')
subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(workspace/'base.qcow2'),str(workspace/'guest.qcow2'),'16G'],check=True)
subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(workspace/'ssh-key')],check=True)
public=(workspace/'ssh-key.pub').read_text().strip()
nonce=os.urandom(24).hex()
user_data=f'''#cloud-config
hostname: webpatch-debian-{args.release}-{args.sapi}
ssh_pwauth: false
disable_root: true
users:
  - name: webpatch
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - {public}
write_files:
  - path: /etc/webpatch-ci-guest
    permissions: '0644'
    content: {nonce}
'''
(workspace/'user-data').write_text(user_data)
(workspace/'meta-data').write_text(f'instance-id: webpatch-{nonce}\nlocal-hostname: webpatch-debian-{args.release}\n')
subprocess.run(['cloud-localds',str(workspace/'seed.iso'),str(workspace/'user-data'),str(workspace/'meta-data')],check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
names=subprocess.check_output(['git','ls-files','src','tests','scripts','.github','pyproject.toml','README.md','LICENSE','AGENTS.md'],text=True).splitlines()
source_hashes={}
with tarfile.open(workspace/'source.tar.gz','w:gz') as bundle:
    for name in names:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        raw=subprocess.check_output(['git','show',commit+':'+name])
        source_hashes[name]=hashlib.sha256(raw).hexdigest()
        item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644
        bundle.addfile(item,io.BytesIO(raw))
    raw=json.dumps({'commit':commit,'source_sha256':source_hashes},sort_keys=True).encode()
    item=tarfile.TarInfo('source-export.json');item.size=len(raw);item.mode=0o644;bundle.addfile(item,io.BytesIO(raw))
(output/'source-export.json').write_text(json.dumps({'commit':commit,'source_sha256':source_hashes},indent=2)+'\n')
acceleration='kvm' if Path('/dev/kvm').exists() else 'tcg'
command=['sudo','qemu-system-x86_64','-machine','q35','-accel',acceleration,'-cpu','host' if acceleration=='kvm' else 'max',
         '-m','2048','-smp','2','-display','none','-monitor','none','-no-reboot',
         '-serial','file:'+str((output/'guest-serial.log').resolve()),'-rtc','base=utc',
         '-drive',f'file={workspace}/guest.qcow2,format=qcow2,if=virtio',
         '-drive',f'file={workspace}/seed.iso,format=raw,if=virtio',
         '-device','virtio-rng-pci','-nic','user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22',
         '-pidfile',str(workspace/'qemu.pid')]
(output/'guest-runtime.json').write_text(json.dumps({'acceleration':acceleration,'shared_host_filesystems':[],
    'network':'user-mode NAT; SSH forwarded to 127.0.0.1:2222 only','memory_mib':2048,'cpus':2},indent=2)+'\n')
options=['-i',str(workspace/'ssh-key'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
         '-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(workspace/'known-hosts'),'-o','ConnectTimeout=5']
ssh=['ssh',*options,'-p','2222','webpatch@127.0.0.1']
environment={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C'}
with (output/'qemu.log').open('wb') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=environment)
    try:
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            if process.poll() is not None: raise RuntimeError('QEMU_EXITED_BEFORE_SSH')
            ready=subprocess.run([*ssh,'true'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if ready.returncode==0: break
            time.sleep(2)
        else: raise RuntimeError('GUEST_SSH_TIMEOUT')
        subprocess.run([*ssh,'sudo cloud-init status --wait'],check=True,timeout=180)
        assert subprocess.check_output([*ssh,'cat /etc/webpatch-ci-guest'],text=True).strip()==nonce
        subprocess.run(['scp',*options,'-P','2222',str(workspace/'source.tar.gz'),'webpatch@127.0.0.1:/home/webpatch/source.tar.gz'],check=True)
        subprocess.run([*ssh,'mkdir -p /home/webpatch/work && tar -xzf /home/webpatch/source.tar.gz -C /home/webpatch/work'],check=True)
        remote=shlex.join(['sudo','env','GITHUB_ACTIONS=true','RUNNER_ENVIRONMENT=github-hosted',
            'WEBPATCH_DEBIAN_GUEST='+nonce,'bash','/home/webpatch/work/scripts/ci_debian_guest.sh',args.sapi])
        with (output/'guest-test.log').open('wb') as stream:
            result=subprocess.run([*ssh,remote],stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
        subprocess.run([*ssh,'sudo tar -czf /home/webpatch/evidence.tar.gz -C /home/webpatch/work ci-evidence && sudo chown webpatch /home/webpatch/evidence.tar.gz'],check=True)
        subprocess.run(['scp',*options,'-P','2222','webpatch@127.0.0.1:/home/webpatch/evidence.tar.gz',str(workspace/'evidence.tar.gz')],check=True)
        with tarfile.open(workspace/'evidence.tar.gz') as bundle:
            for member in bundle.getmembers():
                assert member.isfile() or member.isdir()
                assert not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            bundle.extractall(output/'guest')
        assert result.returncode==0,'DEBIAN_GUEST_TEST_FAILED'
    finally:
        if (workspace/'qemu.pid').exists():
            pid=(workspace/'qemu.pid').read_text().strip()
            if pid.isdigit(): subprocess.run(['sudo','kill',pid],check=False)
        process.wait(timeout=20)
