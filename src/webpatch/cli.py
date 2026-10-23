import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
import sys

from . import __version__
from .planning import plan, verify_document
from .service import scan
from .system import LocalSystem, ProbeError
from .apt import LocalAptSimulator
from .deployment import create_manifest, reconcile
from .application import probe_source, collect_application_evidence, LocalApplicationProbe
from .maintenance import inspect_maintenance
from .consumers import census
from .preparation import preparation_plan, execute_preparation
from .service_control import LocalServiceControl
from .transaction import AuditJournal
from .planning import digest
from .discovery import environment
from .system import Collector
from .execution_inputs import audit_execution_inputs
from .prepared_verification import verify_prepared_scope
from .container_rebuild import rebuild_advice
from .node_adapter import scan_node
from .repair_policy import build_repair_review
from .repair_execution import execute_repair_review
from .package_control import LocalPackageControl
from .documents import load_document
from . import release_gate


def main(argv=None, *, system=None, simulator=None, probe=None, service_controller=None, package_controller=None, journal=None, now=None) -> int:
    parser = argparse.ArgumentParser(description="WebPatch runtime evidence, scoped maintenance and verification")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command")
    for command in ("scan", "scan-node", "plan", "verify-plan", "deployment-manifest", "verify-deployment", "probe-application", "review-maintenance", "review-execution", "audit-consumers", "prepare-plan", "prepare-scope", "retire-preparation", "verify-preparation", "rebuild-plan", "repair-plan"):
        child = subs.add_parser(command)
        child.add_argument("--format", choices=("text", "json"), default="text")
        if command!='scan-node':
            child.add_argument("--package-cache", default="/var/cache/apt/archives",
                               help="read existing .deb files for signed archive identity verification; never downloads")
        if command=='rebuild-plan':
            child.add_argument('--image',required=True,help='declared image@sha256:digest; does not authenticate registry or deployment identity')
        if command=='repair-plan':
            child.add_argument('--prepared-receipt',required=True)
            child.add_argument('--source-cohort',required=True)
            child.add_argument('--budget-seconds',type=int,required=True)
            child.add_argument('--state-directory',default='/var/lib/webpatch')
            child.add_argument('--refresh-probes',action='store_true',required=True,
                               help='explicitly repeat the prepared collector requests while reviewing the exact repair')
        if command in {"plan", "review-maintenance", "review-execution"}:
            selection = child.add_mutually_exclusive_group()
            selection.add_argument("--target-package", action="append", dest="target_package_ids",
                               help="binary:architecture target; scan and shared-package impact remain scope-wide")
            selection.add_argument('--source-cohort',help='explicitly select all installed packages from one PHP source branch')
            child.add_argument("--dry-run", action="store_true", required=True,
                               help="simulate exact trusted Ubuntu/Debian candidates without installing or refreshing indexes")
        if command == "audit-consumers":
            child.add_argument("--target-package", action="append", dest="target_package_ids", required=True)
        if command == "prepare-plan":
            child.add_argument("--service", action="append", required=True, dest="services")
            child.add_argument("--probes", required=True, help="explicit collector URL/script/pool declarations JSON")
            child.add_argument("--state-directory", default="/var/lib/webpatch")
        if command in {"prepare-scope", "retire-preparation"}:
            child.add_argument("path")
            child.add_argument("--confirm-sha256", required=True, help="exact plan or signed receipt document digest")
        if command == 'retire-preparation':
            child.add_argument('--state-directory',default='/var/lib/webpatch')
        if command == 'verify-preparation':
            child.add_argument('path',help='signed startup receipt; repeats its explicitly declared loopback probes')
            child.add_argument('--expect-sha256',required=True)
            child.add_argument('--state-directory',default='/var/lib/webpatch')
        if command == "verify-plan":
            child.add_argument("path", help="saved plan JSON; only compares data and never runs saved commands")
        if command == "verify-deployment":
            child.add_argument("path", help="deployment manifest to reconcile with a new scan")
            child.add_argument("--expect-sha256", help="pin the manifest digest reviewed by the operator")
        if command == "probe-application":
            child.add_argument("--url", required=True, help="explicit loopback HTTP URL of a separately deployed probe")
            child.add_argument("--script", required=True, help="root-controlled copy of the shipped probe script")
            child.add_argument("--service", required=True, help="expected previously observed systemd service")
    subs.add_parser("probe-template", help="print the collector source; never deploys it")
    apply_parser=subs.add_parser('apply',help='apply an exactly confirmed managed repair after native certification')
    apply_parser.add_argument('path',nargs='?',help='schema 5 managed repair review JSON')
    apply_parser.add_argument('--confirm-sha256',help='exact plan hash reviewed by the operator')
    apply_parser.add_argument('--format',choices=('text','json'),default='json')
    args = parser.parse_args(argv)
    if args.command == "probe-template":
        print(probe_source().decode(), end="")
        return 0
    if args.command == 'apply' and not release_gate.PUBLIC_REPAIR_ENABLED:
        print("BLOCKED: repair execution is disabled pending native certification. No changes performed.", file=sys.stderr)
        return 4
    if args.command == 'apply' and (not args.path or not args.confirm_sha256):
        print("BLOCKED: a reviewed managed repair document and its exact plan hash are required. No changes performed.", file=sys.stderr)
        return 4
    try:
        native = system is None
        reader = system if system is not None else LocalSystem()
        if args.command=='apply':
            saved=load_document(reader.read_plan_document(args.path))
            if not isinstance(saved,dict) or not isinstance(saved.get('contract'),dict): raise ValueError('INVALID_REPAIR_DOCUMENT')
            if not isinstance(saved['contract'].get('state_directory'),str): raise ValueError('INVALID_REPAIR_STATE_DIRECTORY')
            controller=package_controller if package_controller is not None else (LocalPackageControl(saved['contract']['state_directory']) if native else None)
            capability=probe if probe is not None else (LocalApplicationProbe() if native else None)
            solver=simulator if simulator is not None else (LocalAptSimulator() if native else None)
            audit=journal if journal is not None else (AuditJournal(controller.state_dir/'operations.jsonl') if native and controller else None)
            if controller is None or capability is None or solver is None or audit is None: raise ValueError('REPAIR_CAPABILITIES_REQUIRED')
            result=execute_repair_review(saved,confirmation_sha256=args.confirm_sha256,system=reader,simulator=solver,
                controller=controller,probe=capability,journal=audit,clock=(lambda:now) if now else None)
            if args.format=='json': print(json.dumps(result,ensure_ascii=True,indent=2))
            else:
                print(result['status']+' — limited declared scope; global safety remains UNKNOWN.')
                print(json.dumps({'plan_sha256':result.get('plan_sha256'),'reasons':result.get('reasons',[])},ensure_ascii=True))
            return 0 if result['status']=='VERIFIED_WITHIN_DECLARED_SCOPE' else 4
        if args.command in {"prepare-scope", "retire-preparation"}:
            saved = load_document(reader.read_plan_document(args.path))
            if not isinstance(saved,dict): raise ValueError('INVALID_PREPARATION_DOCUMENT')
            directory = saved.get('state_directory','/var/lib/webpatch') if args.command=='prepare-scope' else args.state_directory
            controller = service_controller if service_controller is not None else (LocalServiceControl(directory) if native else None)
            if controller is None: raise ValueError('SERVICE_CONTROL_CAPABILITY_REQUIRED')
            if args.command=='prepare-scope':
                capability = probe if probe is not None else (LocalApplicationProbe() if native else None)
                if capability is None: raise ValueError('APPLICATION_PROBE_CAPABILITY_REQUIRED')
                audit = journal if journal is not None else (AuditJournal(controller.state_dir/'operations.jsonl') if native else None)
                if audit is None: raise ValueError('AUDIT_CAPABILITY_REQUIRED')
                result = execute_preparation(saved,confirmation_sha256=args.confirm_sha256,system=reader,
                    controller=controller,probe=capability,journal=audit,
                    clock=(lambda:now) if now else None)
            else:
                if digest(saved)!=args.confirm_sha256: raise ValueError('EXACT_RECEIPT_CONFIRMATION_REQUIRED')
                with controller.locked():
                    payload = controller.store.verify(saved)
                    if payload.get('kind') not in {'controlled_startup','owned_configuration_materialization'}:
                        raise ValueError('PREPARATION_RECEIPT_KIND_INVALID')
                    if payload.get('scope_sha256') != environment(Collector(reader)).scope_sha256:
                        raise ValueError('PREPARATION_RECEIPT_SCOPE_MISMATCH')
                    controller.retire_overrides(payload)
                    result = {'status':'OWNED_RUNTIME_OVERRIDE_RETIRED','active_snapshots_retained':True,
                              'future_starts':'canonical service configuration','executable':False}
            print(json.dumps(result,ensure_ascii=True,indent=2))
            return 4 if result.get('status') in {'BLOCKED','PARTIAL'} else 0
        report = scan_node(reader,now=now) if args.command=='scan-node' else scan(reader, now=now,
                      package_cache=getattr(args, "package_cache", "/var/cache/apt/archives"))
        if args.command=='repair-plan':
            controller=service_controller if service_controller is not None else (LocalServiceControl(args.state_directory) if native else None)
            capability=probe if probe is not None else (LocalApplicationProbe() if native else None)
            solver=simulator if simulator is not None else (LocalAptSimulator() if native else None)
            if controller is None or capability is None or solver is None: raise ValueError('REPAIR_REVIEW_CAPABILITIES_REQUIRED')
            review=build_repair_review(report,system=reader,simulator=solver,controller=controller,probe=capability,
                startup_receipt=load_document(reader.read_plan_document(args.prepared_receipt)),source_cohort=args.source_cohort,
                package_cache=args.package_cache,budget_seconds=args.budget_seconds,now=now)
            print(json.dumps(review.document(),ensure_ascii=True,indent=2))
            return 4
        if args.command=='rebuild-plan':
            result=rebuild_advice(report,image_reference=args.image,now=now)
            print(json.dumps(result,ensure_ascii=True,indent=2))
            return 4
        if args.command == 'verify-preparation':
            saved=load_document(reader.read_plan_document(args.path))
            if digest(saved)!=args.expect_sha256: raise ValueError('PREPARED_RECEIPT_DIGEST_MISMATCH')
            controller=service_controller if service_controller is not None else (LocalServiceControl(args.state_directory) if native else None)
            capability=probe if probe is not None else (LocalApplicationProbe() if native else None)
            if controller is None or capability is None: raise ValueError('PREPARED_VERIFICATION_CAPABILITIES_REQUIRED')
            result=verify_prepared_scope(saved,report,system=reader,controller=controller,probe=capability,now=now)
            print(json.dumps(result,ensure_ascii=True,indent=2))
            return 0 if result['status']=='VERIFIED_CURRENT_PREPARED_SCOPE' else 4
        if args.command == "prepare-plan":
            result = preparation_plan(report,system=reader,services=args.services,
                probes=load_document(reader.read_plan_document(args.probes)),package_cache=args.package_cache,
                state_dir=args.state_directory,now=now)
            print(json.dumps(result,ensure_ascii=True,indent=2))
            return 4
        if args.command == "audit-consumers":
            print(json.dumps(census(report, system=reader, package_ids=args.target_package_ids, now=now), ensure_ascii=True, indent=2))
            return 4
        if args.command == "probe-application":
            capability = probe if probe is not None else (LocalApplicationProbe() if native else None)
            if capability is None:
                raise ValueError("APPLICATION_PROBE_CAPABILITY_REQUIRED")
            result = collect_application_evidence(report, system=reader, probe=capability,
                        url=args.url, script_path=args.script, service=args.service, now=now)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 4
        if args.command in {"deployment-manifest", "verify-deployment"}:
            timestamp = now or datetime.now(timezone.utc)
            document = (create_manifest(report, timestamp) if args.command == "deployment-manifest" else
                        reconcile(load_document(reader.read_plan_document(args.path)), report, timestamp, args.expect_sha256))
            print(json.dumps(document, ensure_ascii=True, indent=2))
            return 4  # matching observations never authorize repair
        backend = simulator if simulator is not None else (LocalAptSimulator() if native else None)
        saved = load_document(reader.read_plan_document(args.path)) if args.command == "verify-plan" else None
        if args.command == "verify-plan" and (not isinstance(saved, dict) or not isinstance(saved.get("scope", {}), dict)):
            raise ValueError("INVALID_PLAN_DOCUMENT")
        requested = saved.get("scope", {}).get("requested_package_ids") if isinstance(saved, dict) else getattr(args, "target_package_ids", None)
        components = isinstance(saved,dict) and saved.get('target_policy')=='EXPLICIT_SOURCE_COMPONENTS'
        if getattr(args,'source_cohort',None):
            if not re.fullmatch(r'php[0-9]+\.[0-9]+',args.source_cohort): raise ValueError('INVALID_PHP_SOURCE_COHORT')
            requested = [p.id for p in report.inventory.packages if p.source_name==args.source_cohort]
            components = True
        result = plan(report, system=reader, simulator=backend, now=now, target_package_ids=requested,
                      include_components=components) if args.command in {"plan", "verify-plan"} else report
        if args.command in {"review-maintenance", "review-execution"}:
            proposal = plan(report, system=reader, simulator=backend, now=now, target_package_ids=requested,include_components=components)
            review = inspect_maintenance(report, proposal, system=reader, package_cache=args.package_cache, now=now)
            if args.command=='review-execution':
                review={'plan':asdict(proposal),'maintenance':review,'execution_inputs':audit_execution_inputs(review,system=reader)}
            print(json.dumps(review, ensure_ascii=True, indent=2))
            return 4
        if args.command == "verify-plan":
            verification = {"status": "BLOCKED", "executable": False,
                            "drift": verify_document(saved, result, now or datetime.now(timezone.utc)),
                            "current_plan_sha256": result.plan_sha256,
                            "blockers": result.blockers}
            print(json.dumps(verification, ensure_ascii=True, indent=2))
            return 4
    except (OSError, ValueError, KeyError, ProbeError) as exc:
        print(f"ERROR: operation incomplete ({type(exc).__name__}); safety is UNKNOWN.", file=sys.stderr)
        return 3
    if getattr(args, "format", "text") == "json":
        print(json.dumps(asdict(result), ensure_ascii=True, indent=2))
    elif args.command == "plan":
        print(f"BLOCKED — repair disabled; APT dry-run: {result.apt_simulation}.")
        print(f"Plan: {result.plan_sha256}; expires: {result.expires_at}")
        print(f"Review: {result.review_status}; execution admission: {result.admission_status}")
        print(json.dumps({"scope": asdict(result.scope)}, ensure_ascii=True))
        for change in result.changes:
            print(json.dumps(asdict(change), ensure_ascii=True))
        for gate in result.gates:
            print(json.dumps(asdict(gate), ensure_ascii=True))
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
