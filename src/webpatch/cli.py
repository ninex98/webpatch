import argparse
from dataclasses import asdict
import json
import sys

from . import __version__
from .planning import plan
from .service import scan
from .system import LocalSystem


def main(argv=None, *, system=None, now=None) -> int:
    parser = argparse.ArgumentParser(description="WebPatch read-only security inventory (phase 1)")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command")
    for command in ("scan", "plan"):
        child = subs.add_parser(command)
        child.add_argument("--format", choices=("text", "json"), default="text")
        if command == "plan":
            child.add_argument("--dry-run", action="store_true", required=True,
                               help="advisory only; APT simulation is not implemented")
    subs.add_parser("apply", help="disabled in this preview")
    args = parser.parse_args(argv)
    if args.command == "apply":
        print("BLOCKED: phase 1 has no repair executor. No changes performed.", file=sys.stderr)
        return 4
    try:
        report = scan(system if system is not None else LocalSystem(), now=now)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: scan incomplete ({type(exc).__name__}); safety is UNKNOWN.", file=sys.stderr)
        return 3
    result = plan(report) if args.command == "plan" else report
    if getattr(args, "format", "text") == "json":
        print(json.dumps(asdict(result), ensure_ascii=True, indent=2))
    elif args.command == "plan":
        print("BLOCKED — advisory plan only; APT dry-run NOT PERFORMED.")
        for blocker in result.blockers:
            print(f"  {blocker}")
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
        for gap in report.inventory.coverage_gaps:
            print(f"  coverage: {gap}")
        print("Use --format json for package versions, source references and evidence digests.")
    return 4 if args.command == "plan" else (1 if report.overall == "POTENTIALLY_AFFECTED" else 2)
