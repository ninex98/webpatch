"""Evidence requirements and package impact, independent of discovery I/O.

VERIFIED always names a narrow relationship, never overall runtime safety.
Legacy string gaps remain in inventory for consumers of report schema 1.
"""
import hashlib
import json
import re
from dataclasses import replace

from .models import CoverageCheck, EntityRef, PackageImpact, PlanScope, ScanScope


def ref(kind, identity):
    return EntityRef(kind, identity)


def runtime_id(inventory, runtime):
    return f"{inventory.environment.scope_sha256 or 'unidentified'}:{runtime.pid}:{runtime.start_ticks or 'unknown'}"


def relation_ref(relation):
    key = json.dumps([relation.kind, relation.path, relation.name, relation.target])
    return ref("pool" if relation.kind == "fpm_pool" else "route", hashlib.sha256(key.encode()).hexdigest())


def check(requirement, status, subjects, evidence_ids, reason, next_step, *, blocks=True):
    subjects = tuple(sorted(set(subjects), key=lambda s: (s.kind, s.id)))
    key = json.dumps([requirement, [(s.kind, s.id) for s in subjects]])
    return CoverageCheck(hashlib.sha256(key.encode()).hexdigest(), requirement, status,
                         subjects, tuple(sorted(set(evidence_ids))), reason, next_step, blocks)


def build_coverage(inventory, evidence, trust):
    """Derive independently assessable requirements from actual observations."""
    scope_id = inventory.environment.scope_sha256 or "unidentified"
    scope = ref("scope", scope_id)
    inventory.scan_scope = ScanScope(scope_id, inventory.environment.scope, "UNKNOWN",
        tuple(sorted(p.id for p in inventory.packages)),
        tuple(sorted(runtime_id(inventory, r) for r in inventory.runtimes)),
        ("Other containers and foreign roots", "Hidden processes and arbitrary custom installation paths",
         "Loaded configuration, dynamic routes and request attribution"))
    checks = []
    def add(*args, **kwargs):
        checks.append(check(*args, **kwargs))
    scope_evidence = [e.id for e in evidence if e.target in {
        "/proc/self/ns/mnt", "/proc/self/ns/pid", "/proc/sys/kernel/random/boot_id", "/etc/machine-id"}]
    add("scan_boundary", "OBSERVED" if scope_id != "unidentified" else "UNKNOWN", [scope], scope_evidence,
        "Current namespace and boot identity only; container/host classification is not exhaustive.",
        "Confirm the intended host/container boundary and inventory other namespaces separately.")
    add("discovery_completeness", "UNKNOWN", [scope], [e.id for e in evidence if e.target == "/proc"],
        "Bounded discovery cannot prove absence of hidden/custom runtimes, even with an empty inventory.",
        "Reconcile all services and custom installations with an operator-supplied deployment inventory.")
    required = {"package_inventory": "apt-package-inventory-v1",
                "runtime_inventory": "linux-local-runtime-association-v2",
                "configuration_inventory": "php-static-configuration-v2"}
    for requirement, adapter in required.items():
        if adapter not in inventory.adapters:
            add(requirement, "NOT_CHECKED", [scope], [], "Required adapter was not run in this scan.",
                "Run the supported adapter in the intended namespace; unsupported OSes need separate validation.")
    installed = {r["package_id"]: r for r in (trust or {}).get("installed", [])}
    for package in inventory.packages:
        package_ref = ref("package", package.id)
        identity = installed.get(package.id, {})
        verified = identity.get("status") in {"AUTHENTICATED_RUNTIME_FILES", "AUTHENTICATED_METADATA_ONLY_ARCHIVE"}
        add("installed_package_files", "VERIFIED" if verified else "UNKNOWN", [package_ref],
            identity.get("evidence_ids", [package.evidence_id]),
            ("Authenticated archive contains only documentation/metadata payload, not a runtime image." if identity.get('status')=='AUTHENTICATED_METADATA_ONLY_ARCHIVE' else
             "Authenticated archive runtime files match disk; this says nothing about running processes.") if verified
            else "Installed file identity is incomplete: " + ", ".join(identity.get("blockers", ["archive evidence unavailable"])),
            "Provide authenticated matching archives and verify every relevant installed runtime file.", blocks=not verified)
        runtimes = [r for r in inventory.runtimes if package.id in r.package_ids]
        add("package_runtime_coverage", "UNKNOWN", [package_ref, *[ref("runtime", runtime_id(inventory, r)) for r in runtimes]],
            [package.evidence_id, *[e for r in runtimes for e in r.evidence_ids]],
            f"{len(runtimes)} locally associated processes observed; unobserved consumers are not excluded.",
            "Account for every consumer of this package, including idle services, pools and CLI jobs.")
    for runtime in inventory.runtimes:
        subjects = [ref("runtime", runtime_id(inventory, runtime)), *[ref("package", p) for p in runtime.package_ids]]
        if runtime.service:
            subjects.append(ref("service", runtime.service))
        verified = runtime.association == "VERIFIED_LOCAL_ASSOCIATION"
        add("local_runtime_association", "VERIFIED" if verified else "UNKNOWN", subjects, runtime.evidence_ids,
            "Stable local process, file view, package owner and live service association." if verified
            else "Local runtime association incomplete: " + ", ".join(runtime.blockers),
            "Resolve namespace, process identity, file replacement and service ownership failures; rescan.", blocks=not verified)
        add("loaded_configuration", "UNKNOWN", subjects, runtime.evidence_ids,
            "Local association does not prove which configuration this process loaded.",
            "Supply process-bound loaded-configuration evidence through an explicit reviewed interface.")
        for file in runtime.files:
            authenticated = [installed.get(p, {}) for p in file.package_ids]
            verified_file = (file.status == "VERIFIED_LOCAL_FILE" and runtime.association == "VERIFIED_LOCAL_ASSOCIATION"
                and bool(authenticated) and all(i.get("status") == "AUTHENTICATED_RUNTIME_FILES"
                    and i.get("files", {}).get(file.path) == file.sha256 for i in authenticated))
            add("runtime_file_identity", "VERIFIED" if verified_file else "UNKNOWN",
                [ref("runtime", runtime_id(inventory, runtime)), ref("file", file.path),
                 *[ref("package", p) for p in file.package_ids]],
                [*file.evidence_ids, *[e for i in authenticated for e in i.get("evidence_ids", [])]],
                "Authenticated disk bytes match the stable executable/mapped file identity; memory contents are not attested." if verified_file
                else "Runtime file lacks a complete stable mapping/executable and authenticated archive chain (" + file.role + ").",
                "Resolve deleted/replaced/unreadable images and authenticate the exact owning package archive.", blocks=not verified_file)
        add("php_module_coverage", "UNKNOWN", subjects, runtime.evidence_ids,
            "Standard /usr/lib/php and libphp mappings: " + runtime.mapping_status + "; custom extensions/native dependencies are not exhaustively authenticated.",
            "Reconcile loaded PHP/native modules with the deployment inventory; authenticate custom module paths separately.")
        if runtime.sapi == "fpm":
            for endpoint in runtime.endpoints:
                stable = runtime.association == "VERIFIED_LOCAL_ASSOCIATION"
                add("process_unix_listener", "VERIFIED" if stable else "UNKNOWN", [ref("runtime", runtime_id(inventory, runtime)),
                    ref("endpoint", endpoint.network_namespace + ":" + endpoint.path + ":" + endpoint.socket_inode)], endpoint.evidence_ids,
                    "This process holds a listening UNIX socket inode in the scanner's network namespace.",
                    "Separately establish stable process identity, loaded pool configuration and request attribution.", blocks=not stable)
            if runtime.endpoint_status != "OBSERVED" or not runtime.endpoints:
                add("process_unix_listener", "UNKNOWN", subjects, runtime.evidence_ids,
                    "No stable owned UNIX listener observed; TCP and other namespaces are not covered.",
                    "Resolve procfs permissions and listener ownership; TCP needs a separately validated interface.")
    for relation in inventory.config_relations:
        add("static_configuration", "OBSERVED", [relation_ref(relation), ref("file", relation.path)], relation.evidence_ids,
            "Configuration text observed: " + relation.status,
            "Bind the pool/handler to a stable runtime and separately prove loaded state and request attribution.")
        related = []
        if relation.kind == "fpm_pool":
            branch = re.match(r"/etc/php/([0-9]+\.[0-9]+)/fpm/", relation.path)
            related = [r for r in inventory.runtimes if branch and r.service == f"php{branch[1]}-fpm.service"
                       and any(e.path == relation.target for e in r.endpoints)]
        else:
            pools = [p for p in inventory.config_relations if p.kind == "fpm_pool" and relation.target == "unix:" + p.target]
            for pool in pools:
                branch = re.match(r"/etc/php/([0-9]+\.[0-9]+)/fpm/", pool.path)
                related.extend(r for r in inventory.runtimes if branch and r.service == f"php{branch[1]}-fpm.service"
                               and any(e.path == pool.target for e in r.endpoints))
            if relation.target == "application/x-httpd-php" or relation.target.startswith("/usr/lib/apache2/modules/libphp"):
                related.extend(r for r in inventory.runtimes if r.sapi == "apache2" and r.service == "apache2.service"
                               and any(f.role == "php_module" and (relation.target == "application/x-httpd-php" or f.path == relation.target) for f in r.files))
        related = {runtime_id(inventory, r): r for r in related}
        add("configured_runtime_link", "OBSERVED" if related and not relation.constraints else "UNKNOWN",
            [relation_ref(relation), *[ref("runtime", identity) for identity in related],
             *[ref("service", r.service) for r in related.values() if r.service]],
            [*relation.evidence_ids, *[e for r in related.values() for e in r.evidence_ids]],
            "Static endpoint/module matches observed runtime candidates; neither pool identity nor route activation is proven. " + ", ".join(relation.constraints),
            "Prove the loaded configuration and selected handler for a specific request; includes/conditions/overrides remain unresolved.")
        if relation.kind == "configured_web_handler":
            add("request_attribution", "NOT_CHECKED", [relation_ref(relation)], [],
                "Default scan sends no requests and installs no diagnostic page. A 200 or ordinary marker is not instance attribution.",
                "Provide explicit request evidence bound to scope, process starttime, executable/mappings and loaded-config digest; define a reviewed probe first.")
    for hint in inventory.runtime_hints:
        if hint.pid is None and hint.path and not hint.path.startswith("/etc/php/"):
            add("custom_installation", "UNSUPPORTED", [ref("installation", hint.path)], hint.evidence_ids,
                "Custom installation is outside the authenticated Ubuntu package repair scope.",
                "Inventory and validate this installation separately; do not apply local APT conclusions.")
    for item in evidence:
        if item.outcome not in {"OK", "EXIT_0", "FileNotFoundError"} and item.operation != "run":
            subjects = [ref("file", item.target)]
            subjects.extend(ref("runtime", runtime_id(inventory, r)) for r in inventory.runtimes if item.id in r.evidence_ids)
            add("read_coverage", "UNKNOWN", subjects, [item.id], "Read failed: " + item.outcome,
                "Obtain read access in the intended namespace and repeat the scan; never infer absence.")
    # Retain adapter-specific limits, including future adapters, as unresolved requirements.
    # These supplement the entity checks above; no string gap is treated as proof.
    for gap in inventory.coverage_gaps:
        if gap.startswith("RUNTIME:"):
            continue  # already explained by local_runtime_association
        add("adapter_limit:" + gap, "UNKNOWN", [scope], [], gap,
            "Resolve the named adapter limitation and rescan; consult the entity checks for observed relationships.")
    merged = {}
    for item in checks:
        previous = merged.get(item.id)
        if previous:
            item = replace(item, evidence_ids=tuple(sorted(set(previous.evidence_ids + item.evidence_ids))))
        merged[item.id] = item
    inventory.coverage = list(merged.values())


def plan_scope(inventory, requested, targets, changes):
    affected = set(requested)
    affected.update(f"{t.name}:{t.architecture}" for t in targets)
    affected.update(f"{c.name}:{c.architecture}" for c in changes)
    impacts = []
    for package in sorted(affected):
        runtimes = [r for r in inventory.runtimes if package in r.package_ids]
        impacts.append(PackageImpact(package, tuple(sorted(runtime_id(inventory, r) for r in runtimes)),
            tuple(sorted({r.service for r in runtimes if r.service})),
            tuple(c.id for c in inventory.coverage if ref("package", package) in c.subjects)))
    return PlanScope(inventory.environment.scope_sha256 or "unidentified", tuple(sorted(requested)),
        tuple(sorted(affected)), tuple(sorted(runtime_id(inventory, r) for r in inventory.runtimes)),
        tuple(sorted(runtime_id(inventory, r) for r in inventory.runtimes
                     if r.association != "VERIFIED_LOCAL_ASSOCIATION" or not r.package_ids)), tuple(impacts))
