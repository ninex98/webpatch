"""Local identity correlation. A local match is never vendor authentication."""

import os
import re

from .models import RuntimeInstance
from .system import SAFE_PATH, service_command


def start_ticks(raw):
    # comm may contain spaces and parentheses. Field 22 follows its final ')'.
    try:
        value = raw.rsplit(")", 1)[1].split()[19]
        return value if value.isdigit() else None
    except (AttributeError, IndexError):
        return None


def package_owners(collector, path, inventory, evidence):
    if not path or not SAFE_PATH.fullmatch(path) or ".." in path.split("/"):
        return ()
    result, ident = collector.probe("run", ("/usr/bin/dpkg-query", "-S", path))
    evidence.append(ident)
    if result is None or result.returncode or result.stderr:
        return ()
    owners = []
    for line in result.stdout.splitlines():
        if ": " not in line:
            return ()
        owner, owned = line.rsplit(": ", 1)
        if owned != path:
            return ()
        matches = [p.id for p in inventory.packages if owner in (p.name, p.id)
                   and p.status == "install ok installed"]
        if len(matches) != 1:
            return ()
        owners.extend(matches)
    return tuple(owners) if len(owners) == 1 else ()


def process_service(probe, pid):
    cgroup = probe("read_text", f"/proc/{pid}/cgroup")
    groups = [line.split(":", 2)[2] for line in (cgroup or "").splitlines()
              if re.match(r"^(?:0::|[0-9]+:name=systemd:)", line)]
    units = {part for group in groups for part in group.split("/")
             if re.fullmatch(r"(?:php[0-9]+\.[0-9]+-fpm|apache2)\.service", part)}
    if len(units) != 1:
        return None
    unit = next(iter(units))
    result = probe("run", service_command(unit))
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line) if result and result.returncode == 0 and not result.stderr else {}
    control = props.get("ControlGroup", "")
    if (props.get("Id") == unit and props.get("LoadState") == "loaded"
            and props.get("ActiveState") == "active" and props.get("MainPID", "0").isdigit()
            and int(props.get("MainPID", "0")) > 0 and control == f"/system.slice/{unit}"
            and all(g == control or g.startswith(control + "/") for g in groups)):
        main = props["MainPID"]
        if (probe("readlink", f"/proc/{main}/ns/mnt") == probe("readlink", f"/proc/{pid}/ns/mnt")
                and probe("identity", f"/proc/{main}/root") == probe("identity", f"/proc/{pid}/root")):
            return unit
    return None


class RuntimeAdapter:
    name = "linux-local-runtime-association-v2"

    def supports(self, environment):
        return environment.os_id in {"ubuntu", "debian"}

    def discover(self, collector, inventory):
        for hint in inventory.runtime_hints:
            if hint.pid is None:
                continue
            evidence = list(hint.evidence_ids)
            blockers = []
            pid = hint.pid
            def probe(operation, path):
                value, ident = collector.probe(operation, path)
                evidence.append(ident)
                return value
            initial = start_ticks(probe("read_text", f"/proc/{pid}/stat"))
            if not initial:
                blockers.append("PROCESS_START_ID_UNREADABLE")
            initial_ns = probe("readlink", f"/proc/{pid}/ns/mnt")
            pid_ns = probe("readlink", f"/proc/{pid}/ns/pid")
            self_ns = probe("readlink", "/proc/self/ns/pid")
            root = probe("identity", f"/proc/{pid}/root")
            own_root = probe("identity", "/")
            if not pid_ns or pid_ns != self_ns or root is None or root != own_root:
                blockers.append("PID_NAMESPACE_OR_ROOT_UNVERIFIED")
            if hint.deleted:
                blockers.append("DELETED_RUNNING_IMAGE")
            path = hint.path
            file_hash = None
            owners = ()
            service = process_service(probe, pid) if not blockers else None
            # systemd PrivateTmp creates a mount namespace even for official units.
            # Only correlate its file view after root, PID namespace and live unit proof.
            if hint.scope != "current" and not (service and initial_ns and hint.scope == "foreign"):
                blockers.append("FOREIGN_OR_UNKNOWN_MOUNT_NAMESPACE")
            sapi = hint.kind
            # Never map a foreign process path to packages in the current root.
            can_read_local = not blockers and path and SAFE_PATH.fullmatch(path)
            if can_read_local:
                loaded = probe("fingerprint", f"/proc/{pid}/exe")
                disk = probe("fingerprint", path)
                if loaded is None or loaded != disk:
                    blockers.append("LOADED_EXECUTABLE_DIFFERS_OR_UNREADABLE")
                else:
                    file_hash = disk["sha256"]
                if hint.scope == "foreign" and probe("fingerprint", f"/proc/{pid}/root{path}") != disk:
                    blockers.append("SERVICE_NAMESPACE_FILE_VIEW_DIFFERS")
                owners = package_owners(collector, path, inventory, evidence)
                if "apache" in path or "httpd" in path:
                    sapi = "apache2"
                    maps = probe("read_text", f"/proc/{pid}/maps")
                    modules = []
                    for line in (maps or "").splitlines():
                        parts = line.split(None, 5)
                        if len(parts) == 6 and re.search(r"/libphp[^/]*\.so(?: \(deleted\))?$", parts[5]):
                            if parts not in modules:
                                modules.append(parts)
                    if not modules:
                        blockers.append("MOD_PHP_MAPPING_UNVERIFIED")
                    module_owners = set()
                    for parts in modules:
                        module_path = parts[5]
                        if module_path.endswith(" (deleted)"):
                            blockers.append("DELETED_MOD_PHP_MAPPING")
                            continue
                        module = probe("fingerprint", module_path)
                        if hint.scope == "foreign" and probe("fingerprint", f"/proc/{pid}/root{module_path}") != module:
                            blockers.append("SERVICE_NAMESPACE_MODULE_VIEW_DIFFERS")
                        try:
                            major, minor = (int(v, 16) for v in parts[3].split(":"))
                            same = module and (module["inode"], module["device"]) == (int(parts[4]), os.makedev(major, minor))
                        except (ValueError, OverflowError):
                            same = False
                        if not same:
                            blockers.append("MOD_PHP_MAPPING_DIFFERS_OR_UNREADABLE")
                        module_owners.update(package_owners(collector, module_path, inventory, evidence))
                    owners = tuple(sorted(module_owners))
                    if len(owners) != 1:
                        blockers.append("MOD_PHP_PACKAGE_AMBIGUOUS")
                    if probe("read_text", f"/proc/{pid}/maps") != maps:
                        blockers.append("MAPPINGS_CHANGED_DURING_SCAN")
                elif owners:
                    sapi = next(p.sapi for p in inventory.packages if p.id == owners[0])
                if not owners:
                    blockers.append("PACKAGE_OWNERSHIP_UNVERIFIED")
                if not service:
                    blockers.append("SYSTEMD_SERVICE_UNVERIFIED")
                if probe("fingerprint", path) != disk:
                    blockers.append("DISK_IMAGE_CHANGED_DURING_SCAN")
                if process_service(probe, pid) != service:
                    blockers.append("SERVICE_CHANGED_DURING_SCAN")
            else:
                blockers.append("LOCAL_PACKAGE_CORRELATION_BLOCKED")
            if (start_ticks(probe("read_text", f"/proc/{pid}/stat")) != initial
                    or probe("readlink", f"/proc/{pid}/exe") != hint.path
                    or probe("readlink", f"/proc/{pid}/ns/mnt") != initial_ns
                    or probe("readlink", f"/proc/{pid}/ns/pid") != pid_ns
                    or probe("identity", f"/proc/{pid}/root") != root):
                blockers.append("PROCESS_CHANGED_DURING_SCAN")
            inventory.runtimes.append(RuntimeInstance(
                pid, sapi, path, owners, service, initial, file_hash,
                "VERIFIED_LOCAL_ASSOCIATION" if not blockers else "UNKNOWN",
                tuple(sorted(set(blockers))), tuple(evidence)))
            inventory.coverage_gaps.extend(f"RUNTIME:{pid}:{b}" for b in blockers)
        if len({p.source_name for p in inventory.packages if p.sapi in {"cli", "fpm", "apache2"}}) > 1:
            inventory.coverage_gaps.append("MULTIPLE_PHP_BRANCHES_REQUIRE_SEPARATE_REVIEW")
