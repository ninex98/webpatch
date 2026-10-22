"""Vendor boundary comparisons, explicitly conditional on unverified metadata."""

from collections import Counter
from datetime import datetime
import hashlib
from importlib.resources import files
import json
import re
from typing import Protocol

from .models import Assessment, Inventory
from .system import Collector, VERSION


class VersionComparator(Protocol):
    def at_least(self, installed: str, fixed: str) -> tuple[bool | None, str]: ...


class RuleProvider(Protocol):
    """New runtime families supply their own applicability and version semantics."""
    revision: str
    sha256: str
    reviewed: datetime
    expires: datetime

    def assess(self, inventory: Inventory, comparator: VersionComparator,
               now: datetime) -> list[Assessment]: ...


class DpkgComparator:
    def __init__(self, collector: Collector):
        self.collector = collector

    def at_least(self, installed: str, fixed: str) -> tuple[bool | None, str]:
        result, ident = self.collector.probe(
            "run", ("/usr/bin/dpkg", "--compare-versions", installed, "ge", fixed))
        if result is None or result.returncode not in (0, 1) or result.stderr:
            return None, ident
        return result.returncode == 0, ident


class RuleEngine:
    def __init__(self, data: bytes | None = None):
        raw = data if data is not None else files("webpatch").joinpath("data/php2shell.json").read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.data = json.loads(raw)
        self.revision = self.data["revision"]
        if self.data["schema_version"] != 1:
            raise ValueError("UNSUPPORTED_RULE_SCHEMA")
        self.reviewed = datetime.fromisoformat(self.data["reviewed_at"])
        self.expires = datetime.fromisoformat(self.data["valid_until"])
        if not self.reviewed.tzinfo or not self.expires.tzinfo or self.expires <= self.reviewed:
            raise ValueError("INVALID_RULE_VALIDITY")
        keys = [(r["os_id"], r["version_id"], r["codename"], r["source_name"]) for r in self.data["rules"]]
        if len(keys) != len(set(keys)):
            raise ValueError("AMBIGUOUS_RULES")
        for rule in self.data["rules"]:
            re.compile(rule["version_pattern"])
            for cve in self.data["cves"]:
                if not VERSION.fullmatch(rule["fixes"][cve]):
                    raise ValueError("INVALID_FIX_VERSION")

    def assess(self, inventory: Inventory, comparator: VersionComparator,
               now: datetime) -> list[Assessment]:
        if now.tzinfo is None:
            raise ValueError("TIMEZONE_REQUIRED")
        results = []
        counts = Counter(p.id for p in inventory.packages)
        env = inventory.environment
        for package in inventory.packages:
            rule = next((r for r in self.data["rules"]
                         if (r["os_id"], r["version_id"], r["codename"], r["source_name"])
                         == (env.os_id, env.version_id, env.codename, package.source_name)), None)
            for cve in self.data["cves"]:
                refs = tuple(rule["references"]) if rule else (self.data["upstream_reference"],)
                fixed = rule["fixes"][cve] if rule else None
                status = "UNKNOWN"
                evidence = (package.evidence_id,)
                if not self.reviewed <= now < self.expires:
                    reason = "RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW"
                elif counts[package.id] != 1:
                    reason = "AMBIGUOUS_PACKAGE_ID"
                elif package.status not in {"install ok installed", "hold ok installed"}:
                    reason = "PACKAGE_NOT_FULLY_CONFIGURED"
                elif package.sapi not in {"fpm", "apache2", "cli", "cgi"}:
                    reason = "PACKAGE_NOT_A_COVERED_ENGINE_BINARY"
                elif not rule:
                    reason = "NO_VENDOR_RELEASE_SOURCE_RULE"
                elif not (re.fullmatch(r"[a-z0-9][a-z0-9-]*", package.architecture)
                          and (":" not in package.name or package.name.split(":")[1] == package.architecture)
                          and package.name.split(":")[0] in {
                    f"{package.source_name}-fpm", f"{package.source_name}-cli",
                    f"{package.source_name}-cgi", f"libapache2-mod-{package.source_name}",
                } and package.architecture and package.version
                          and re.fullmatch(re.escape(package.source_version) + r"(?:\+b[0-9]+)?", package.version)):
                    reason = "INCONSISTENT_PACKAGE_IDENTITY"
                elif not re.fullmatch(rule["version_pattern"], package.source_version):
                    reason = "UNRECOGNIZED_VENDOR_VERSION_FAMILY"
                else:
                    meets, comparison_id = comparator.at_least(package.source_version, fixed)
                    evidence += (comparison_id,)
                    if meets is None:
                        reason = "VERSION_COMPARISON_FAILED"
                    else:
                        status = "MEETS_VENDOR_FIX" if meets else "BELOW_VENDOR_FIX"
                        reason = "VERSION_ONLY_ORIGIN_AND_RUNNING_CODE_UNVERIFIED"
                results.append(Assessment(package.id, cve, status, reason, fixed, refs, evidence))
        return results
