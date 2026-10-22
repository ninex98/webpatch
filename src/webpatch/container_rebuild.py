"""Image rebuild advice. No Docker daemon, build, push or rollout capability."""
from dataclasses import asdict
from datetime import datetime, timezone
import re

from .gates import evidence_deadline
from .planning import digest

IMAGE = re.compile(r'[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}\Z')


def rebuild_advice(report, *, image_reference, now=None):
    now=now or datetime.now(timezone.utc)
    if (not isinstance(image_reference,str) or not IMAGE.fullmatch(image_reference)
            or '//' in image_reference or '..' in image_reference.split('@')[0].split('/')):
        raise ValueError('IMMUTABLE_IMAGE_REFERENCE_REQUIRED')
    blockers=[]
    if report.inventory.environment.scope!='container': blockers.append('CONTAINER_LOCAL_SCAN_REQUIRED')
    if not report.inventory.environment.scope_sha256: blockers.append('CONTAINER_SCOPE_UNKNOWN')
    deadline=evidence_deadline(report,now)
    if not datetime.fromisoformat(report.observed_at)<=now<deadline:
        blockers.append('CONTAINER_RULE_OR_SCAN_EVIDENCE_EXPIRED')
    engines={p.id:p for p in report.inventory.packages if p.sapi in {'fpm','apache2','cli','cgi'}}
    constraints=[]
    for ident,package in sorted(engines.items()):
        rows=[a for a in report.assessments if a.package_id==ident]
        if not rows or any(a.version_status=='UNKNOWN' or not a.fixed_version for a in rows):
            blockers.append('CONTAINER_VENDOR_BOUNDARY_UNKNOWN:'+ident)
        constraints.append({'package_id':ident,'source_package':package.source_name,
            'observed_binary_version':package.version,'observed_source_version':package.source_version,
            'comparison':'dpkg source-version comparison; never upstream SemVer for distro backports',
            'requirements':[{'cve':a.cve,'minimum_source_version':a.fixed_version,
                             'version_status':a.version_status,'references':list(a.references)} for a in rows]})
    if not constraints: blockers.append('CONTAINER_NO_COVERED_ENGINE_IS_NOT_ABSENCE_PROOF')
    for hint in report.inventory.runtime_hints:
        if hint.pid is None and hint.path and not hint.path.startswith('/etc/php/'):
            blockers.append('CONTAINER_CUSTOM_INSTALLATION_REQUIRES_SEPARATE_BUILD_RECIPE:'+hint.path)
    stages=[
        {'id':'identify-build','action':'Locate the Dockerfile/build definition and application revision for the declared image digest.',
         'acceptance':'Verify registry signature/provenance and actual deployment image digest; the scan cannot authenticate caller-declared image identity.'},
        {'id':'rebuild','action':'Rebuild the same supported distribution/PHP branch from reviewed sources with fresh signed indexes and vendor-fixed packages.',
         'acceptance':'Record base image digest, exact resolved package versions, signed archive hashes, build inputs and resulting image digest. Re-evaluate every CVE independently; invalidate stale dependency layers.'},
        {'id':'verify-image','action':'Scan the resulting immutable image in its own namespace and verify package/archive bytes.',
         'acceptance':'All listed vendor constraints must pass with current rules and trusted bytes. A build exit code or package version alone does not verify a running workload.'},
        {'id':'replace-instances','action':'Use the reviewed deployment system to canary and roll out the new image, accounting for every replica, job and shared consumer.',
         'acceptance':'Bind each new instance to the verified image digest and new runtime identity; drain and retire every affected old instance under the approved interruption budget.'},
        {'id':'verify-deployment','action':'Perform the explicitly approved application health requests and verify runtime/image attribution on every declared workload.',
         'acceptance':'Record coverage, routing, health and remaining UNKNOWN results. On failure retain evidence and use the reviewed deployment recovery procedure; never claim automatic APT rollback.'},
    ]
    result={'schema_version':1,'kind':'container_image_rebuild_advice',
        'status':'ADVISORY_READY' if not blockers else 'BLOCKED_ADVICE',
        'scope_sha256':report.inventory.environment.scope_sha256,'scan_sha256':digest(asdict(report)),
        'rule_sha256':report.rule_sha256,'created_at':now.isoformat(),'expires_at':deadline.isoformat(),
        'declared_image_reference':image_reference,'image_identity':'DECLARED_NOT_AUTHENTICATED_BY_LOCAL_SCAN',
        'vendor_constraints':constraints,'stages':stages,'blockers':sorted(set(blockers)),
        'unresolved_scan_coverage':report.inventory.coverage_gaps,
        'automatic_in_place_repair':False,'build_execution':'NOT_RUN','rollout_execution':'NOT_RUN',
        'runtime_safety':'UNKNOWN','safe':False,'executable':False,'advice_sha256':''}
    result['advice_sha256']=digest(result)
    return result
