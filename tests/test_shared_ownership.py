from copy import deepcopy

from conftest import NOW
from test_runtime import runtime_fixture
from webpatch.service import scan
from webpatch.system import CommandResult


def test_shared_file_ownership_observation_is_reused_only_inside_one_scan():
    fake=runtime_fixture(); fake.dirs['/proc'].append('43')
    for attr in ('reads','links','identities','fingerprints','dirs'):
        mapping=getattr(fake,attr)
        for path,value in list(mapping.items()):
            if isinstance(path,str) and path.startswith('/proc/42/'):
                mapping[path.replace('/42/','/43/')]=deepcopy(value)
    command=('/usr/bin/dpkg-query','-S','/usr/sbin/php-fpm8.1')
    first=scan(fake,now=NOW)
    assert len(first.inventory.runtimes)==2
    assert sum(op=='run' and args==command for op,args in fake.calls)==1
    owner_ids={e.id for e in first.evidence if e.operation=='run' and 'dpkg-query' in e.target and '"-S"' in e.target}
    assert len(owner_ids)==1 and all(owner_ids<=set(r.evidence_ids) for r in first.inventory.runtimes)
    fake.commands[command]=CommandResult(1,'','ownership no longer available')
    second=scan(fake,now=NOW)
    assert sum(op=='run' and args==command for op,args in fake.calls)==2
    assert all(r.association=='UNKNOWN' for r in second.inventory.runtimes)
