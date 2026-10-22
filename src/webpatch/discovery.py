"""Adapters produce observations only. No CVE thresholds live here."""

import re
import shlex
from typing import Protocol

from .models import Environment, Inventory, Package, RuntimeHint
from .system import Collector, DPKG_QUERY
from .runtime import RuntimeAdapter
from .configuration import ConfigurationAdapter


MAX_PROCESSES = 4096


class EnvironmentAdapter(Protocol):
    name: str
    def supports(self, environment: Environment) -> bool: ...
    def discover(self, collector: Collector, inventory: Inventory) -> None: ...


def environment(collector: Collector) -> Environment:
    raw, _ = collector.probe("read_text", "/etc/os-release")
    data = {}
    if raw:
        try:
            for line in raw.splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    parts = shlex.split(value, comments=True)
                    if len(parts) == 1:
                        data[key] = parts[0]
        except ValueError:
            data = {}
    cgroup, _ = collector.probe("read_text", "/proc/self/cgroup")
    docker, _ = collector.probe("read_text", "/.dockerenv")
    podman, _ = collector.probe("read_text", "/run/.containerenv")
    ns, _ = collector.probe("readlink", "/proc/self/ns/mnt")
    container = (docker is not None or podman is not None
                 or bool(re.search(r"docker|containerd|kubepods|libpod|lxc", cgroup or "")))
    return Environment(data.get("ID", "unknown"), data.get("VERSION_ID", "unknown"),
                       data.get("VERSION_CODENAME", "unknown"),
                       "container" if container else "host_or_unidentified_container", ns)


def sapi_for(name: str) -> str:
    name = name.split(":")[0]
    match = re.fullmatch(r"php[0-9]+\.[0-9]+-(cli|fpm|cgi|phpdbg)", name)
    if match:
        return match[1]
    if re.fullmatch(r"libapache2-mod-php[0-9]+\.[0-9]+", name):
        return "apache2"
    return "component_or_unknown"


class AptAdapter:
    name = "apt-package-inventory-v1"

    def supports(self, environment: Environment) -> bool:
        return environment.os_id in {"ubuntu", "debian"}

    def discover(self, collector: Collector, inventory: Inventory) -> None:
        result, evidence_id = collector.probe("run", DPKG_QUERY)
        if result is None or result.returncode != 0 or result.stderr:
            inventory.coverage_gaps.append("PACKAGE_QUERY_FAILED_OR_WARNED")
            return
        seen = set()
        for line in result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 6:
                inventory.coverage_gaps.append("MALFORMED_PACKAGE_RECORD")
                continue
            name, version, arch, source, source_version, status = fields
            if not re.match(r"^(php(?:[0-9-]|$)|libapache2-mod-php|libphp)", name):
                continue
            if status.split()[-1:] in (["not-installed"], ["config-files"]):
                continue
            package = Package(name, version, arch, source, source_version, status,
                              sapi_for(name), evidence_id)
            if package.id in seen:
                inventory.coverage_gaps.append("DUPLICATE_PACKAGE_ID")
            seen.add(package.id)
            inventory.packages.append(package)


class PhpHintsAdapter:
    name = "php-runtime-hints-v1"

    def supports(self, environment: Environment) -> bool:
        return True

    def discover(self, collector: Collector, inventory: Inventory) -> None:
        for directory, predicate in (
            ("/etc/php", lambda n: bool(re.fullmatch(r"[0-9]+\.[0-9]+", n))),
            ("/www/server/php", lambda n: True),
            ("/opt/php", lambda n: True),
            ("/usr/local/bin", lambda n: "php" in n.lower()),
            ("/usr/local/sbin", lambda n: "php" in n.lower()),
        ):
            names, ident = collector.probe("listdir", directory)
            if names is None:
                # Missing conventional paths are normal; unreadable ones are a gap.
                if collector.evidence[-1].outcome != "FileNotFoundError":
                    inventory.coverage_gaps.append(f"PATH_UNREADABLE:{directory}")
                continue
            for name in names:
                if predicate(name):
                    inventory.runtime_hints.append(RuntimeHint(
                        "installation_path", f"{directory}/{name}", None, "current", (ident,)))

        for directory in ("/run", "/run/containerd"):
            names, _ = collector.probe("listdir", directory)
            if names and any(n in {"docker.sock", "containerd.sock"} for n in names):
                inventory.coverage_gaps.append("CONTAINER_DAEMON_PRESENT_NOT_INSPECTED")

        pids, _ = collector.probe("listdir", "/proc")
        if pids is None:
            inventory.coverage_gaps.append("PROCESS_LIST_UNAVAILABLE")
            return
        pids = sorted((p for p in pids if p.isdigit()), key=int)
        if len(pids) > MAX_PROCESSES:
            inventory.coverage_gaps.append("PROCESS_LIMIT_REACHED")
        for pid in pids[:MAX_PROCESSES]:
            comm, comm_id = collector.probe("read_text", f"/proc/{pid}/comm")
            if comm is None:
                inventory.coverage_gaps.append("PROCESS_IDENTITY_UNREADABLE_OR_EXITED")
                continue
            comm = comm.strip().lower()
            if not any(s in comm for s in ("php", "apache", "httpd", "lshttpd", "lsphp")):
                continue
            executable, exe_id = collector.probe("readlink", f"/proc/{pid}/exe")
            namespace, ns_id = collector.probe("readlink", f"/proc/{pid}/ns/mnt")
            own_ns = inventory.environment.mount_namespace
            scope = "unknown" if not namespace or not own_ns else (
                "current" if namespace == own_ns else "foreign")
            if scope != "current":
                inventory.coverage_gaps.append("PROCESS_SCOPE_UNVERIFIED_OR_FOREIGN")
            kind = "fpm" if "fpm" in comm else "php_or_webserver"
            inventory.runtime_hints.append(RuntimeHint(
                kind, executable, int(pid), scope, (comm_id, exe_id, ns_id),
                bool(executable and executable.endswith(" (deleted)"))))
            if executable is None:
                inventory.coverage_gaps.append("PROCESS_EXECUTABLE_UNREADABLE_OR_EXITED")
            # No cmdline/environ collection; Apache presence does not prove mod_php loading.


def discover(collector: Collector, adapters: tuple[EnvironmentAdapter, ...] | None = None) -> Inventory:
    inventory = Inventory(environment(collector))
    inventory.coverage_gaps.extend([
        "DISCOVERY_NOT_EXHAUSTIVE", "PACKAGE_ORIGIN_AND_BYTES_UNVERIFIED",
        "RUNNING_IMAGES_AND_WEB_ROUTES_UNVERIFIED", "OTHER_CONTAINERS_NOT_INSPECTED",
    ])
    for adapter in adapters if adapters is not None else (AptAdapter(), PhpHintsAdapter(), RuntimeAdapter(), ConfigurationAdapter()):
        if adapter.supports(inventory.environment):
            inventory.adapters.append(adapter.name)
            adapter.discover(collector, inventory)
    if not inventory.packages:
        inventory.coverage_gaps.append("NO_PHP_PACKAGES_OBSERVED_IS_NOT_PROOF_OF_ABSENCE")
    inventory.coverage_gaps = sorted(set(inventory.coverage_gaps))
    return inventory
