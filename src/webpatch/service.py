from datetime import datetime, timezone
from dataclasses import asdict

from .discovery import discover
from .models import Report
from .rules import DpkgComparator, RuleEngine, RuleProvider
from .system import Collector, SystemReader
from .sources import audit_sources
from .trust import authenticate
from .coverage import build_coverage


def scan(system: SystemReader, *, now: datetime | None = None,
         rules: RuleProvider | None = None, adapters=None,
         package_cache="/var/cache/apt/archives") -> Report:
    now = now if now is not None else datetime.now(timezone.utc)
    rules = rules if rules is not None else RuleEngine()
    collector = Collector(system)
    inventory = discover(collector, adapters)
    sources = audit_sources(collector, inventory) if inventory.environment.os_id in {"ubuntu", "debian"} else None
    trust = authenticate(collector, inventory, sources, now, package_cache) if sources else None
    if not rules.reviewed <= now < rules.expires:
        inventory.coverage_gaps.append("RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW")
    assessments = rules.assess(inventory, DpkgComparator(collector), now)
    build_coverage(inventory, collector.evidence, trust)
    overall = ("POTENTIALLY_AFFECTED" if any(a.version_status == "BELOW_VENDOR_FIX" for a in assessments)
               else "UNKNOWN")
    return Report(2, now.isoformat(), rules.revision, rules.sha256,
                  rules.expires.isoformat(), inventory, assessments, collector.evidence, overall,
                  apt_sources=asdict(sources) if sources else None, package_trust=trust)
