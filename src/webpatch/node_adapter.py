"""Read-only Node discovery: no node execution, application reads or npm scan."""
from datetime import datetime, timezone
from pathlib import PurePosixPath
import re

from .coverage import check,ref,runtime_id
from .discovery import environment
from .models import Inventory,Package,Report,RuntimeHint,RuntimeInstance,RuntimeFile,ScanScope
from .node_rules import NodeRuleProvider
from .planning import digest
from .rules import DpkgComparator
from .runtime import start_ticks,package_owners
from .system import Collector,DPKG_QUERY,SAFE_PATH


class NodeAdapter:
    name='node-local-inventory-v1'

    def supports(self,env): return env.os_id in {'debian','ubuntu'}

    def discover(self,collector,inventory):
        query,ident=collector.probe('run',DPKG_QUERY)
        if query is None or query.returncode or query.stderr:
            inventory.coverage_gaps.append('NODE_PACKAGE_QUERY_UNAVAILABLE')
        else:
            for line in query.stdout.splitlines():
                row=line.split('\t')
                if len(row)!=6:
                    inventory.coverage_gaps.append('NODE_PACKAGE_QUERY_MALFORMED'); continue
                name,version,arch,source,source_version,status=row
                if not re.fullmatch(r'(?:nodejs|libnode[0-9]+)(?::[a-z0-9-]+)?',name): continue
                if status.endswith(('not-installed','config-files')): continue
                inventory.packages.append(Package(name,version,arch,source,source_version,status,
                    'node' if name.split(':')[0]=='nodejs' else 'node_library',ident))
        for path in ('/usr/local/bin/node','/opt/node/bin/node','/opt/nodejs/bin/node','/snap/node/current/bin/node'):
            info,ident=collector.probe('fingerprint',path)
            if info:
                inventory.runtime_hints.append(RuntimeHint('custom_node_path',path,None,inventory.environment.scope,(ident,)))
                inventory.coverage_gaps.append('NODE_CUSTOM_INSTALLATION_UNVERIFIED:'+path)
            elif collector.evidence[-1].outcome!='FileNotFoundError':
                inventory.coverage_gaps.append('NODE_CUSTOM_PATH_READ_UNAVAILABLE:'+path)
        names,ident=collector.probe('listdir','/proc')
        pids=sorted((n for n in names or [] if n.isdigit()),key=int)
        if names is None or len(pids)>4096: inventory.coverage_gaps.append('NODE_PROCESS_VISIBILITY_UNAVAILABLE_OR_LIMIT')
        for pid in pids[:4096]:
            path,path_id=collector.probe('readlink',f'/proc/{pid}/exe')
            comm,comm_id=collector.probe('read_text',f'/proc/{pid}/comm')
            if path is None and comm is None:
                inventory.coverage_gaps.append('NODE_PROCESS_READ_UNAVAILABLE:'+pid)
            if (comm or '').strip() not in {'node','nodejs'} and PurePosixPath((path or '').removesuffix(' (deleted)')).name not in {'node','nodejs'}:
                continue
            evidence=[path_id,comm_id]; reasons=[]
            def read(op,target):
                value,ident=collector.probe(op,target); evidence.append(ident); return value
            first=read('read_text',f'/proc/{pid}/stat'); ticks=start_ticks(first)
            namespace=[read('readlink',f'/proc/{pid}/ns/'+kind) for kind in ('mnt','pid')]
            own_pid=read('readlink','/proc/self/ns/pid')
            root=read('identity',f'/proc/{pid}/root'); own_root=read('identity','/')
            if not all(namespace) or not own_pid or namespace!=[inventory.environment.mount_namespace,own_pid] or not root or root!=own_root:
                reasons.append('NODE_FOREIGN_OR_UNVERIFIED_NAMESPACE')
            executable=read('fingerprint',f'/proc/{pid}/exe')
            files=[]; owned=()
            if path and SAFE_PATH.fullmatch(path) and '..' not in PurePosixPath(path).parts:
                disk=read('fingerprint',path); owned=package_owners(collector,path,inventory,evidence)
                matches=(disk and executable and all(disk[k]==executable[k] for k in ('device','inode','sha256')))
                if not matches or not owned: reasons.append('NODE_EXECUTABLE_REPLACED_OR_UNOWNED')
                if disk:
                    files.append(RuntimeFile(path,'node_executable',owned,disk['sha256'],disk['device'],disk['inode'],
                        'VERIFIED_LOCAL_FILE' if matches else 'UNKNOWN',tuple(evidence)))
            else: reasons.append('NODE_EXECUTABLE_PATH_UNSUPPORTED_OR_DELETED')
            maps=read('read_text',f'/proc/{pid}/maps')
            if maps is None: reasons.append('NODE_MAPPINGS_UNREADABLE')
            # libnode is kept explicit; local ownership is not vendor byte trust.
            mapped=sorted({line.split(None,5)[5] for line in (maps or '').splitlines()
                           if len(line.split(None,5))==6 and re.search(r'/libnode\.so(?:\.|$)',line.split(None,5)[5])})
            for module in mapped:
                if not SAFE_PATH.fullmatch(module):
                    reasons.append('NODE_LIBRARY_DELETED_OR_PATH_UNSUPPORTED'); continue
                image=read('fingerprint',module); owners=package_owners(collector,module,inventory,evidence)
                if not image or not owners: reasons.append('NODE_LIBRARY_UNREADABLE_OR_UNOWNED'); continue
                owned=tuple(sorted(set(owned)|set(owners)))
                files.append(RuntimeFile(module,'node_library',owners,image['sha256'],image['device'],image['inode'],'OBSERVED_DISK_FILE',tuple(evidence)))
            if (not ticks or start_ticks(read('read_text',f'/proc/{pid}/stat'))!=ticks
                    or read('readlink',f'/proc/{pid}/exe')!=path
                    or read('fingerprint',f'/proc/{pid}/exe')!=executable):
                reasons.append('NODE_PROCESS_CHANGED_DURING_READ')
            inventory.runtime_hints.append(RuntimeHint('node_process',path,int(pid),inventory.environment.scope,tuple(evidence),bool(path and path.endswith(' (deleted)'))))
            inventory.runtimes.append(RuntimeInstance(int(pid),'node',path,owned,None,ticks,
                executable.get('sha256') if executable else None,
                'VERIFIED_LOCAL_FILE_ASSOCIATION' if not reasons else 'UNKNOWN',tuple(sorted(set(reasons))),tuple(evidence),
                tuple(files),mapping_status='OBSERVED_NODE_LIBRARIES',namespace_sha256=digest([namespace,root])))
        inventory.coverage_gaps.extend(['NODE_DISCOVERY_NOT_EXHAUSTIVE','NODE_VENDOR_BYTES_AND_LOADED_LIBRARY_IDENTITY_UNVERIFIED',
            'NODE_APPLICATION_ROUTING_AND_HEALTH_UNVERIFIED','NPM_DEPENDENCIES_NOT_ASSESSED'])
        if not any(p.sapi=='node' for p in inventory.packages): inventory.coverage_gaps.append('NODE_EMPTY_PACKAGE_INVENTORY_IS_NOT_ABSENCE_PROOF')


def scan_node(system, *, now=None, rules=None, adapter=None):
    now=now or datetime.now(timezone.utc); rules=rules or NodeRuleProvider(); adapter=adapter or NodeAdapter()
    collector=Collector(system); inventory=Inventory(environment(collector))
    if adapter.supports(inventory.environment):
        adapter.discover(collector,inventory); inventory.adapters.append(adapter.name)
    else: inventory.coverage_gaps.append('NODE_PLATFORM_UNSUPPORTED')
    if not rules.reviewed<=now<rules.expires: inventory.coverage_gaps.append('NODE_RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW')
    assessments=rules.assess(inventory,DpkgComparator(collector),now)
    scope=inventory.environment.scope_sha256 or 'unidentified'
    inventory.scan_scope=ScanScope(scope,inventory.environment.scope,'UNKNOWN',tuple(p.id for p in inventory.packages),
        tuple(runtime_id(inventory,r) for r in inventory.runtimes),('Hidden/custom installations and other namespaces','npm dependencies and application logic'))
    inventory.coverage=[check('node:'+gap,'UNKNOWN',(ref('scope',scope),),(),gap,
        'Resolve this Node-specific evidence gap; no package-version match authorizes repair.') for gap in sorted(set(inventory.coverage_gaps))]
    overall='POTENTIALLY_AFFECTED' if any(a.version_status=='BELOW_VENDOR_FIX' for a in assessments) else 'UNKNOWN'
    return Report(2,now.isoformat(),rules.revision,rules.sha256,rules.expires.isoformat(),inventory,assessments,collector.evidence,overall)
