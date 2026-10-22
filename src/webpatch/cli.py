import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import sys

from . import __version__
from .planning import plan, verify_document
from .service import scan
from .system import LocalSystem, ProbeError
from .apt import LocalAptSimulator


def main(argv=None, *, system=None, simulator=None, now=None) -> int:
    parser = argparse.ArgumentParser(description="WebPatch read-only security inventory and APT simulation")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command")
    for command in ("scan", "plan", "verify-plan"):
        child = subs.add_parser(command)
        child.add_argument("--format", choices=("text", "json"), default="text")
        child.add_argument("--package-cache", default="/var/cache/apt/archives",
                           help="read existing .deb files for signed archive identity verification; never downloads")
        if command == "plan":
            child.add_argument("--target-package", action="append", dest="target_package_ids",
                               help="binary:architecture target; scan and shared-package impact remain scope-wide")
            child.add_argument("--dry-run", action="store_true", required=True,
                               help="simulate exact trusted Ubuntu candidates without installing or refreshing indexes")
        if command == "verify-plan":
            child.add_argument("path", help="saved plan JSON; only compares data and never runs saved commands")
    subs.add_parser("apply", help="disabled in this preview")
    args = parser.parse_args(argv)
    if args.command == "apply":
        print("BLOCKED: repair execution is disabled. No changes performed.", file=sys.stderr)
        return 4
    try:
        reader = system if system is not None else LocalSystem()
        report = scan(reader, now=now,
                      package_cache=getattr(args, "package_cache", "/var/cache/apt/archives"))
        backend = simulator if simulator is not None else (LocalAptSimulator() if isinstance(reader, LocalSystem) else None)
        saved = json.loads(reader.read_text(args.path)) if args.command == "verify-plan" else None
        if args.command == "verify-plan" and (not isinstance(saved, dict) or not isinstance(saved.get("scope", {}), dict)):
            raise ValueError("INVALID_PLAN_DOCUMENT")
        requested = saved.get("scope", {}).get("requested_package_ids") if isinstance(saved, dict) else getattr(args, "target_package_ids", None)
        result = plan(report, system=reader, simulator=backend, now=now, target_package_ids=requested) if args.command in {"plan", "verify-plan"} else report
        if args.command == "verify-plan":
            verification = {"status": "BLOCKED", "executable": False,
                            "drift": verify_document(saved, result, now or datetime.now(timezone.utc)),
                            "current_plan_sha256": result.plan_sha256,
                            "blockers": result.blockers}
            print(json.dumps(verification, ensure_ascii=True, indent=2))
            return 4
    except (OSError, ValueError, KeyError, ProbeError) as exc:
        print(f"ERROR: scan incomplete ({type(exc).__name__}); safety is UNKNOWN.", file=sys.stderr)
        return 3
    if getattr(args, "format", "text") == "json":
        print(json.dumps(asdict(result), ensure_ascii=True, indent=2))
    elif args.command == "plan":
        print(f"BLOCKED — repair disabled; APT dry-run: {result.apt_simulation}.")
        print(f"Plan: {result.plan_sha256}; expires: {result.expires_at}")
        print(json.dumps({"scope": asdict(result.scope)}, ensure_ascii=True))
        for change in result.changes:
            print(json.dumps(asdict(change), ensure_ascii=True))
        for blocker in result.blockers:
            print("  " + json.dumps(blocker, ensure_ascii=True))
        for recommendation in result.recommendations:
            print("  " + json.dumps(recommendation, ensure_ascii=True))
    else:
        env = report.inventory.environment
        print(f"{report.overall} — runtime safety UNKNOWN; never treat a version match as safe.")
        print(json.dumps({"scope": env.scope, "os": env.os_id,
                          "release": env.version_id, "codename": env.codename}, ensure_ascii=True))
        print(f"Rules: {report.rule_revision}; expires: {report.rule_valid_until}")
        for assessment in report.assessments:
            # Escape observed strings to prevent terminal control-sequence injection.
            print(json.dumps({"package": assessment.package_id, "cve": assessment.cve,
                              "version_status": assessment.version_status,
                              "reason": assessment.reason}, ensure_ascii=True))
        print(f"Runtime hints: {len(report.inventory.runtime_hints)}")
        for check in report.inventory.coverage:
            print(json.dumps({"requirement": check.requirement, "status": check.status,
                              "subjects": [asdict(s) for s in check.subjects], "reason": check.reason,
                              "next_step": check.next_step}, ensure_ascii=True))
        for gap in report.inventory.coverage_gaps:
            print(f"  coverage: {gap}")
        print("Use --format json for package versions, source references and evidence digests.")
    return 4 if args.command == "plan" else (1 if report.overall == "POTENTIALLY_AFFECTED" else 2)
