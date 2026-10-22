"""Evidence-bound APT simulation plans. There is deliberately no executor."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re

from .models import Plan, Report, PackageTarget, PackageChange, InputBinding, Evidence
from .rules import DpkgComparator, RuleEngine
from .system import Collector, DPKG_QUERY, ProbeError
from .runtime import start_ticks


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stable_bindings(report):
    bindings = {}
    for evidence in report.evidence:
        op, path = evidence.operation, evidence.target
        keep = op in {"read_text", "listdir", "fingerprint", "package_index"} and not path.startswith("/proc/")
        keep |= path in {"/proc/self/ns/mnt", "/proc/sys/kernel/random/boot_id"}
        keep |= op == "run" and path == json.dumps(DPKG_QUERY)
        keep |= op == "run" and path.startswith('["/usr/bin/systemctl",')
        if keep:
            key = (op, path)
            value = InputBinding(op, path, evidence.outcome, evidence.sha256)
            if key in bindings and bindings[key] != value:
                raise ValueError("STATE_CHANGED_DURING_SCAN")
            bindings[key] = value
    return tuple(bindings[key] for key in sorted(bindings))


def state_digest(report, bindings):
    runtimes = [{k: v for k, v in asdict(r).items() if k != "evidence_ids"} for r in report.inventory.runtimes]
    return digest({"environment": asdict(report.inventory.environment), "bindings": [asdict(b) for b in bindings],
                   "runtimes": runtimes, "rules": report.rule_sha256})


def check_bindings(collector, bindings, report=None):
    for binding in bindings:
        target = tuple(json.loads(binding.target)) if binding.operation == "run" else binding.target
        collector.probe(binding.operation, target)
        current = collector.evidence[-1]
        if (current.outcome, current.sha256) != (binding.outcome, binding.sha256):
            return False
    if report is not None:
        for runtime in report.inventory.runtimes:
            stat, _ = collector.probe("read_text", f"/proc/{runtime.pid}/stat")
            path, _ = collector.probe("readlink", f"/proc/{runtime.pid}/exe")
            if not runtime.start_ticks or start_ticks(stat) != runtime.start_ticks or path != runtime.path:
                return False
        # Account for newly started PHP/web processes, not only previously observed PIDs.
        pids, _ = collector.probe("listdir", "/proc")
        if pids is None or sum(p.isdigit() for p in pids) > 4096:
            return False
        current = set()
        for pid in (p for p in pids if p.isdigit()):
            comm, _ = collector.probe("read_text", f"/proc/{pid}/comm")
            if comm is None:
                return False
            if any(s in comm.lower() for s in ("php", "apache", "httpd", "lshttpd", "lsphp")):
                current.add(int(pid))
        if current != {r.pid for r in report.inventory.runtimes}:
            return False
    return True


def lock_blockers(collector):
    raw, _ = collector.probe("read_text", "/proc/locks")
    if raw is None:
        return ["APT_LOCK_VISIBILITY_UNKNOWN"]
    blockers = []
    for path in ("/var/lib/dpkg/lock", "/var/lib/dpkg/lock-frontend", "/var/lib/apt/lists/lock", "/var/cache/apt/archives/lock"):
        identity, _ = collector.probe("identity", path)
        if identity is None:
            if collector.evidence[-1].outcome != "FileNotFoundError": blockers.append("APT_LOCK_VISIBILITY_UNKNOWN")
            continue
        for match in re.finditer(r"\b([0-9a-fA-F]+):([0-9a-fA-F]+):([0-9]+)\b", raw):
            if (os.makedev(int(match[1], 16), int(match[2], 16)), int(match[3])) == (identity["device"], identity["inode"]):
                blockers.append("PACKAGE_MANAGER_LOCK_HELD")
    return blockers


def choose_targets(report, collector, now):
    candidates = (report.package_trust or {}).get("candidates", [])
    targets, blockers = [], []
    rules = RuleEngine()
    if rules.sha256 != report.rule_sha256 or not rules.reviewed <= now < rules.expires:
        return (), ["RULE_BUNDLE_CHANGED_OR_EXPIRED"]
    comparator = DpkgComparator(collector)
    for package in report.inventory.packages:
        if package.sapi not in {"cli", "fpm", "apache2", "cgi"}: continue
        rule = next((r for r in rules.data["rules"] if (r["os_id"], r["codename"], r["source_name"])
                     == (report.inventory.environment.os_id, report.inventory.environment.codename, package.source_name)), None)
        if not rule or package.status != "install ok installed":
            blockers.append("TARGET_PACKAGE_RULE_OR_STATE_UNKNOWN:" + package.id)
            continue
        matches = [c for c in candidates if (c["name"], c["architecture"], c["source_name"])
                   == (package.name.split(":")[0], package.architecture, package.source_name)
                   and c["fresh_for_plan"] and re.fullmatch(rule["version_pattern"], c["source_version"])
                   and c["version"] == c["source_version"]]
        best = None
        for candidate in matches:
            versions = [package.version, *rule["fixes"].values()]
            if any(comparator.at_least(candidate["version"], version)[0] is not True for version in versions):
                continue
            if best is None or comparator.at_least(candidate["version"], best["version"])[0] is True:
                best = candidate
        if best is None:
            blockers.append("NO_TRUSTED_SAME_BRANCH_FIX_CANDIDATE:" + package.id)
            continue
        identical = [c for c in candidates if (c["name"], c["architecture"], c["version"]) == (best["name"], best["architecture"], best["version"])]
        if len({c["sha256"] for c in identical}) != 1:
            blockers.append("AMBIGUOUS_CANDIDATE_ARCHIVE:" + package.id)
            continue
        targets.append(PackageTarget(best["name"], best["architecture"], package.version, best["version"], best["sha256"]))
    return tuple(sorted(targets, key=lambda t: (t.name, t.architecture))), blockers


def parse_simulation(stdout):
    changes, configured, summaries = [], [], []
    for line in stdout.splitlines():
        if line.startswith("Inst "):
            match = re.fullmatch(r"Inst ([a-z0-9+.-]+)(?::([a-z0-9-]+))?(?: \[([^\]]+)\])? \(([^\s()]+) .+ \[([a-z0-9-]+)\]\)(?: \[.*\])?", line)
            if not match or (match[2] and match[2] != match[5]):
                raise ValueError("APT_INSTALL_LINE_UNPARSEABLE")
            changes.append(PackageChange("INSTALL" if match[3] is None else "UPGRADE", match[1], match[5], match[3], match[4]))
        elif line.startswith("Remv "):
            match = re.fullmatch(r"Remv ([a-z0-9+.-]+)(?::([a-z0-9-]+))?(?: \[([^\]]+)\])?(?: .*)?", line)
            if not match: raise ValueError("APT_REMOVE_LINE_UNPARSEABLE")
            changes.append(PackageChange("REMOVE", match[1], match[2] or "unknown", match[3], None))
        elif line.startswith("Conf "):
            match = re.fullmatch(r"Conf ([a-z0-9+.-]+)(?::([a-z0-9-]+))? \(([^\s()]+) .+ \[([a-z0-9-]+)\]\)", line)
            if not match or (match[2] and match[2] != match[4]): raise ValueError("APT_CONFIGURE_LINE_UNPARSEABLE")
            configured.append((match[1], match[4], match[3]))
        elif re.match(r"^(?:Purg|Unpack|Configure|Remove)\b", line):
            raise ValueError("APT_UNSUPPORTED_OPERATION")
        match = re.fullmatch(r"(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded\.", line)
        if match: summaries.append(tuple(map(int, match.groups())))
    identities = [(c.name, c.architecture) for c in changes]
    if len(identities) != len(set(identities)):
        raise ValueError("APT_DUPLICATE_PACKAGE_OPERATIONS")
    expected = [(c.name, c.architecture, c.new_version) for c in changes if c.operation != "REMOVE"]
    if sorted(configured) != sorted(expected):
        raise ValueError("APT_CONFIGURE_SET_MISMATCH")
    counts = tuple(sum(c.operation == op for c in changes) for op in ("UPGRADE", "INSTALL", "REMOVE"))
    if len(summaries) != 1 or summaries[0][:3] != counts:
        raise ValueError("APT_SUMMARY_MISMATCH")
    return tuple(changes)


def dependency_blockers(changes, targets, report, collector):
    blockers = []
    allowed = {(t.name, t.architecture): t for t in targets}
    comparator = DpkgComparator(collector)
    for change in changes:
        key = (change.name, change.architecture)
        target = allowed.get(key)
        if change.operation == "REMOVE":
            blockers.append("PACKAGE_REMOVAL_REJECTED:" + change.name)
        elif change.operation == "INSTALL":
            blockers.append("NEW_DEPENDENCY_REQUIRES_APPROVAL:" + change.name)
        elif change.old_version == change.new_version:
            blockers.append("REINSTALL_REQUIRES_REVIEW:" + change.name)
        elif comparator.at_least(change.new_version, change.old_version)[0] is not True:
            blockers.append("DOWNGRADE_OR_UNCOMPARABLE_VERSION:" + change.name)
        if target is None:
            blockers.append("UNAPPROVED_DEPENDENCY_CHANGE:" + change.name)
        elif (change.old_version, change.new_version) != (target.installed_version, target.version):
            blockers.append("SIMULATION_TARGET_OR_INSTALLED_VERSION_MISMATCH:" + change.name)
        records = [c for c in (report.package_trust or {}).get("candidates", [])
                   if (c["name"], c["architecture"], c["version"]) == (change.name, change.architecture, change.new_version)]
        if not records or len({c["sha256"] for c in records}) != 1:
            blockers.append("DEPENDENCY_ORIGIN_UNVERIFIED:" + change.name)
    observed = {(c.name, c.architecture) for c in changes}
    if any(t.version != t.installed_version and (t.name, t.architecture) not in observed for t in targets):
        blockers.append("REQUESTED_UPGRADE_MISSING_FROM_SIMULATION")
    return blockers


def plan(report: Report, *, system=None, simulator=None, now=None) -> Plan:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    blockers = ["REPAIR_EXECUTION_DISABLED"]
    blockers.extend(report.inventory.coverage_gaps)
    blockers.extend((report.apt_sources or {}).get("blockers", ["SOURCE_POLICY_UNKNOWN"]))
    blockers.extend((report.package_trust or {}).get("blockers", ["PACKAGE_TRUST_UNKNOWN"]))
    for identity in (report.package_trust or {}).get("installed", []):
        if identity["status"] != "AUTHENTICATED_RUNTIME_FILES":
            blockers.append("INSTALLED_PACKAGE_IDENTITY_UNKNOWN:" + identity["package_id"])
    if not report.inventory.environment.scope_sha256:
        blockers.append("SCOPE_IDENTITY_UNKNOWN")
    if report.inventory.environment.scope == "container":
        blockers.append("CONTAINER_REBUILD_REQUIRED")
    if report.inventory.environment.os_id != "ubuntu" or report.inventory.environment.codename not in {"jammy", "noble"}:
        blockers.append("APT_PLANNING_UNSUPPORTED_RELEASE")
    if any(a.version_status == "UNKNOWN" and a.fixed_version for a in report.assessments):
        blockers.append("PACKAGE_ASSESSMENT_UNKNOWN")
    try:
        bindings = stable_bindings(report)
    except ValueError as exc:
        blockers.append(str(exc)); bindings = ()
    targets, changes, evidence = (), (), ()
    simulation_status, simulation_hash = "NOT_RUN", None
    collector = Collector(system) if system else None
    supported = report.inventory.environment.os_id == "ubuntu" and report.inventory.environment.codename in {"jammy", "noble"}
    if collector and simulator and supported and report.inventory.environment.scope != "container":
        targets, candidate_blockers = choose_targets(report, collector, now)
        blockers.extend(candidate_blockers)
        if targets and bindings:
            blockers.extend(lock_blockers(collector))
            if not check_bindings(collector, bindings, report):
                blockers.append("STATE_DRIFT_BEFORE_SIMULATION")
            else:
                try:
                    simulation = simulator.simulate(tuple(f"{t.name}:{t.architecture}={t.version}" for t in targets))
                    result = simulation.result
                    simulation_hash = digest(asdict(simulation))
                    collector.evidence.append(Evidence(f"e{len(collector.evidence)+1}", "apt_simulation", json.dumps(simulation.command), f"EXIT_{result.returncode}", simulation_hash))
                    if not simulation.privileged: blockers.append("APT_SIMULATION_PERMISSION_COVERAGE_LIMITED")
                    if result.returncode or result.stderr:
                        raise ValueError("APT_SIMULATION_FAILED_OR_WARNED")
                    changes = parse_simulation(result.stdout)
                    blockers.extend(dependency_blockers(changes, targets, report, collector))
                    simulation_status = "PASS"
                except (ProbeError, ValueError) as exc:
                    blockers.append(str(exc)); simulation_status = "FAIL"
                if not check_bindings(collector, bindings, report):
                    blockers.append("STATE_DRIFT_DURING_SIMULATION")
                blockers.extend(lock_blockers(collector))
        evidence = tuple(collector.evidence)
    if simulation_status == "NOT_RUN": blockers.append("APT_DRY_RUN_NOT_PERFORMED")
    expiry = min(now + timedelta(minutes=30), datetime.fromisoformat(report.rule_valid_until))
    if expiry <= now: blockers.append("PLAN_RULES_EXPIRED")
    services = tuple(sorted({r.service for r in report.inventory.runtimes if r.service}))
    result = Plan(2, "BLOCKED", False, simulation_status, digest(asdict(report)), tuple(sorted(set(blockers))), (
        "Review every blocker and exact dependency change before any future repair stage.",
        "Prepare a tested image/snapshot restore and package/configuration backup; rollback is not guaranteed.",
        "Require explicit approval of the plan hash and repeat state checks and simulation before execution.",
    ), created_at=now.isoformat(), expires_at=expiry.isoformat(), rule_sha256=report.rule_sha256,
        state_sha256=state_digest(report, bindings), simulation_sha256=simulation_hash,
        targets=targets, changes=changes, services=services,
        interruptions=("Package maintainer scripts may stop/restart services and drop requests before explicit restart.",
                       "Downtime duration is UNKNOWN until reviewed with service owners; loaded config and health require verification."),
        bindings=bindings, evidence=evidence)
    return replace(result, plan_sha256=digest(asdict(result)))


def validate_plan(saved: Plan, report: Report, *, system, simulator, now):
    """Never grants execution; return reasons the reviewed plan can no longer apply."""
    blockers = []
    if digest(asdict(replace(saved, plan_sha256=""))) != saved.plan_sha256:
        blockers.append("PLAN_DIGEST_MISMATCH")
    if now < datetime.fromisoformat(saved.created_at) or now >= datetime.fromisoformat(saved.expires_at):
        blockers.append("PLAN_EXPIRED_OR_CLOCK_REVERSED")
    current = plan(report, system=system, simulator=simulator, now=now)
    if current.state_sha256 != saved.state_sha256 or current.rule_sha256 != saved.rule_sha256:
        blockers.append("PLAN_INPUT_STATE_DRIFT")
    if current.targets != saved.targets or current.simulation_sha256 != saved.simulation_sha256 or current.apt_simulation != "PASS":
        blockers.append("PLAN_SIMULATION_DRIFT")
    blockers.extend(b for b in current.blockers if b.startswith("STATE_DRIFT_"))
    return tuple(sorted(set(blockers)))


def verify_document(saved, current: Plan, now):
    """Compare an untrusted JSON document; never execute any of its contents."""
    try:
        if saved["schema_version"] != 2 or saved["executable"] is not False:
            return ("INVALID_PLAN_DOCUMENT",)
        expected = dict(saved, plan_sha256="")
        blockers = []
        if digest(expected) != saved["plan_sha256"]:
            blockers.append("PLAN_DIGEST_MISMATCH")
        created, expires = (datetime.fromisoformat(saved[k]) for k in ("created_at", "expires_at"))
        if not created.tzinfo or not expires.tzinfo or not created <= now < expires:
            blockers.append("PLAN_EXPIRED_OR_CLOCK_REVERSED")
        if current.state_sha256 != saved["state_sha256"] or current.rule_sha256 != saved["rule_sha256"]:
            blockers.append("PLAN_INPUT_STATE_DRIFT")
        if (current.simulation_sha256 != saved["simulation_sha256"] or current.apt_simulation != "PASS"
                or [asdict(t) for t in current.targets] != saved["targets"]):
            blockers.append("PLAN_SIMULATION_DRIFT")
        blockers.extend(b for b in current.blockers if b.startswith("STATE_DRIFT_"))
        return tuple(sorted(set(blockers)))
    except (KeyError, ValueError, TypeError):
        return ("INVALID_PLAN_DOCUMENT",)
