"""Phase-one advisory plans cannot be promoted to executable plans."""

from dataclasses import asdict
import hashlib
import json

from .models import Plan, Report


def plan(report: Report) -> Plan:
    digest = hashlib.sha256(json.dumps(asdict(report), sort_keys=True).encode()).hexdigest()
    recommendations = [
        "Verify every web SAPI, package origin, running image and container separately.",
        "Obtain a fresh vendor advisory and an authenticated same-branch package candidate.",
        "Require a reviewed APT dependency simulation and explicit plan confirmation before any repair.",
        "Schedule service downtime and verify running processes and application health after repair.",
    ]
    for assessment in report.assessments:
        if assessment.version_status == "BELOW_VENDOR_FIX":
            recommendations.append(
                f"Review {assessment.package_id} for {assessment.cve}: vendor minimum "
                f"{assessment.fixed_version}; this is not a verified install candidate.")
    return Plan(1, "BLOCKED", False, "NOT_IMPLEMENTED", digest, (
        "PHASE_1_HAS_NO_EXECUTOR", "APT_SOURCES_AND_DEPENDENCIES_NOT_VERIFIED",
        "APT_DRY_RUN_NOT_PERFORMED", "RUNTIME_COVERAGE_NOT_VERIFIED",
    ), tuple(recommendations))
