from datetime import datetime, timezone

from .discovery import discover
from .models import Report
from .rules import DpkgComparator, RuleEngine, RuleProvider
from .system import Collector, SystemReader


def scan(system: SystemReader, *, now: datetime | None = None,
         rules: RuleProvider | None = None, adapters=None) -> Report:
    now = now if now is not None else datetime.now(timezone.utc)
    rules = rules if rules is not None else RuleEngine()
    collector = Collector(system)
    inventory = discover(collector, adapters)
    if not rules.reviewed <= now < rules.expires:
        inventory.coverage_gaps.append("RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW")
    assessments = rules.assess(inventory, DpkgComparator(collector), now)
    overall = ("POTENTIALLY_AFFECTED" if any(a.version_status == "BELOW_VENDOR_FIX" for a in assessments)
               else "UNKNOWN")
    return Report(1, now.isoformat(), rules.revision, rules.sha256,
                  rules.expires.isoformat(), inventory, assessments, collector.evidence, overall)
