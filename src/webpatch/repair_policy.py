"""Evidence-bound, explicitly scoped repair review. No mutations in this module.

Global discovery limitations remain visible. A finite package operation is
reviewable only with independent evidence about its exact files and consumers.
"""
from dataclasses import asdict,dataclass,replace
from datetime import datetime,timezone
import hashlib
from importlib.resources import files
import json
import re

from .consumers import census
from .coverage import check,ref,runtime_id
from .execution_inputs import audit_execution_inputs
from .maintenance import inspect_maintenance
from .models import PackageTarget,PackageImpact,PlanScope,ReviewGate,Plan
from .planning import plan,digest
from .prepared_verification import verify_prepared_scope
from .system import Collector,DPKG_QUERY,SAFE_PATH,VERSION
from .rules import DpkgComparator


@dataclass(frozen=True)
class RepairReview:
    proposal: Plan
    contract_json: str
    evidence_json: str

    def document(self):
        return {'schema_version':1,'kind':'managed_package_repair_review','plan':asdict(self.proposal),
                'contract':json.loads(self.contract_json),'evidence':json.loads(self.evidence_json)}


def policy_digest():
    root=files('webpatch')
    names=('repair_policy.py','package_control.py','transaction.py','prepared_verification.py',
           'execution_inputs.py','maintenance.py','preparation.py','service_control.py','system.py','planning.py','trust.py')
    return digest({name:hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest() for name in names})


def path_overrides(inspection,system):
    collector=Collector(system,evidence_prefix='o'); blockers=[]; unrelated=[]
    paths={p for a in inspection['archives'] if 'candidate' in a['roles'] for p in a['payload_paths']}
    for path,kind in (('/var/lib/dpkg/diversions','diversion'),('/var/lib/dpkg/statoverride','statoverride')):
        raw,_=collector.probe('read_text',path)
        if raw is None:
            if collector.evidence[-1].outcome!='FileNotFoundError': blockers.append('REPAIR_PACKAGE_OVERRIDE_UNREADABLE:'+path)
            continue
        rows=raw.splitlines()
        if kind=='diversion':
            if len(rows)%3: blockers.append('REPAIR_DIVERSION_FORMAT_UNKNOWN'); continue
            entries=[(rows[i],rows[i+1]) for i in range(0,len(rows),3)]
        else:
            entries=[]
            for line in rows:
                parts=line.split()
                if len(parts)!=4 or not re.fullmatch(r'[0-7]{3,4}',parts[2]):
                    blockers.append('REPAIR_STATOVERRIDE_FORMAT_UNKNOWN'); continue
                entries.append((parts[3],))
        for entry in entries:
            if any(not SAFE_PATH.fullmatch(p) or '..' in p.split('/') for p in entry):
                blockers.append('REPAIR_PACKAGE_OVERRIDE_PATH_UNKNOWN'); continue
            if any(a==b or a.startswith(b.rstrip('/')+'/') for a in paths for b in entry):
                blockers.append('REPAIR_TARGET_PATH_OVERRIDE:'+entry[0])
            else: unrelated.append({'kind':kind,'paths':entry,'disposition':'OUTSIDE_CHANGED_PACKAGE_PAYLOAD'})
    return {'status':'PASS' if not blockers else 'BLOCKED','blockers':sorted(set(blockers)),
            'unrelated':unrelated,'evidence':[asdict(e) for e in collector.evidence]}


def trigger_control_review(report,proposal,maintenance,inputs,*,system,package_cache,now):
    """Authenticate existing handler packages; never execute their scripts here."""
    names=set(inputs['triggers']['package_names'])
    # The reviewed PHP helper can activate configuration-directory triggers for
    # every member of the selected source cohort. Candidate declarations remain
    # in the exact review; any additional pending package is rejected by dpkg I/O.
    names.update(a['info_basename'] for a in maintenance['archives'] if 'triggers' in a['control_files'])
    collector=Collector(system,evidence_prefix='h'); query,_=collector.probe('run',DPKG_QUERY)
    rows=[line.split('\t') for line in query.stdout.splitlines()] if query and not query.returncode and not query.stderr else []
    targets=[]; blockers=[]
    for name in sorted(names):
        matches=[r for r in rows if len(r)==6 and name in {r[0],r[0].split(':')[0]+':'+r[2]} and r[5]=='install ok installed']
        if len(matches)!=1:
            blockers.append('REPAIR_TRIGGER_PACKAGE_STATE_UNKNOWN:'+name); continue
        row=matches[0]
        candidates=[c for c in (report.package_trust or {}).get('candidates',[]) if
                    (c['name'],c['architecture'],c['version'],c['source_name'],c['source_version'])
                    ==(row[0].split(':')[0],row[2],row[1],row[3],row[4])]
        hashes={c['sha256'] for c in candidates}
        if len(hashes)!=1:
            blockers.append('REPAIR_TRIGGER_ARCHIVE_ORIGIN_UNKNOWN:'+name); continue
        targets.append(PackageTarget(row[0].split(':')[0],row[2],row[1],row[1],next(iter(hashes))))
    review=replace(proposal,targets=tuple(targets),changes=(),plan_sha256='')
    review=replace(review,plan_sha256=digest(asdict(review)))
    inspected=inspect_maintenance(report,review,system=system,package_cache=package_cache,now=now) if targets else None
    audit=audit_execution_inputs(inspected,system=system) if inspected else None
    if inspected and inspected['status']!='READY_FOR_MAINTENANCE_REVIEW': blockers.extend(inspected['blockers'])
    if audit and audit['status']!='READY_FOR_EXECUTION_POLICY_REVIEW': blockers.extend(audit['blockers'])
    handler_files=[]
    for archive in (inspected or {}).get('archives',[]):
        for path,expected in archive['execution_files'].items():
            actual,ident=collector.probe('fingerprint',path)
            passed=actual and actual.get('sha256')==expected and actual.get('uid')==0 and not actual.get('mode',0)&0o022
            handler_files.append({'path':path,'expected_sha256':expected,'evidence_id':ident,'status':'VERIFIED_PACKAGE_FILE' if passed else 'UNKNOWN'})
            if not passed: blockers.append('REPAIR_TRIGGER_EXECUTION_FILE_UNVERIFIED:'+path)
    return {'status':'PASS' if not blockers else 'BLOCKED','names':sorted(names),'maintenance':inspected,
            'inputs':audit,'execution_files':handler_files,'blockers':sorted(set(blockers)),'evidence':[asdict(e) for e in collector.evidence]}


def predependency_state(inspection,proposal,system):
    collector=Collector(system,evidence_prefix='z'); query,_=collector.probe('run',DPKG_QUERY)
    rows=[line.split('\t') for line in query.stdout.splitlines()] if query and not query.returncode and not query.stderr else []
    changes={c.name for c in proposal.changes}; blockers=[]; checks=[]
    for archive in inspection['archives']:
        if 'candidate' not in archive['roles']: continue
        for clause in (archive.get('pre_depends') or '').split(','):
            if not clause.strip(): continue
            match=re.fullmatch(r'\s*([a-z0-9][a-z0-9+.-]*)(?:\s+\(>=\s+([^\s()]+)\))?\s*',clause)
            if not match:
                blockers.append('REPAIR_PREDEPENDENCY_EXPRESSION_UNSUPPORTED:'+archive['package_id']); continue
            name,minimum=match.groups()
            if minimum and not VERSION.fullmatch(minimum):
                blockers.append('REPAIR_PREDEPENDENCY_EXPRESSION_UNSUPPORTED:'+archive['package_id']); continue
            installed=[r for r in rows if len(r)==6 and r[0].split(':')[0]==name and r[5]=='install ok installed']
            passed=(len(installed)==1 and name not in changes)
            if passed and minimum:
                passed=DpkgComparator(collector).at_least(installed[0][1],minimum)[0] is True
            checks.append({'name':name,'minimum_version':minimum,'installed_version':installed[0][1] if len(installed)==1 else None,
                           'status':'ALREADY_CONFIGURED_AND_UNCHANGED' if passed else 'UNKNOWN'})
            if not passed: blockers.append('REPAIR_PREDEPENDENCY_NOT_STABLY_CONFIGURED:'+name)
    return {'status':'PASS' if not blockers else 'BLOCKED','checks':checks,'blockers':sorted(set(blockers)),
            'evidence':[asdict(e) for e in collector.evidence]}


def build_repair_review(report,*,system,simulator,controller,probe,startup_receipt,source_cohort,
                        package_cache,budget_seconds,now=None):
    now=now or datetime.now(timezone.utc)
    if not re.fullmatch(r'php[0-9]+\.[0-9]+',source_cohort): raise ValueError('REPAIR_SOURCE_COHORT_INVALID')
    if type(budget_seconds) is not int or not 60<=budget_seconds<=1800: raise ValueError('REPAIR_MAINTENANCE_BUDGET_INVALID')
    selected={p.id for p in report.inventory.packages if p.source_name==source_cohort}
    diagnostic=plan(report,system=system,simulator=simulator,now=now,target_package_ids=sorted(selected),include_components=True)
    startup=verify_prepared_scope(startup_receipt,report,system=system,controller=controller,probe=probe,now=now)
    # The authenticated payload is consumed only if its fresh verification passed.
    body=startup_receipt.get('payload',{}) if startup['status']=='VERIFIED_CURRENT_PREPARED_SCOPE' else {}
    maintenance=inspect_maintenance(report,diagnostic,system=system,package_cache=package_cache,now=now)
    inputs=audit_execution_inputs(maintenance,system=system)
    consumers=census(report,system=system,package_ids=sorted(selected),now=now) if selected else None
    overrides=path_overrides(maintenance,system)
    triggers=trigger_control_review(report,diagnostic,maintenance,inputs,system=system,package_cache=package_cache,now=now)
    predeps=predependency_state(maintenance,diagnostic,system)
    blockers=[]; gates=[]; scope=(ref('scope',report.inventory.environment.scope_sha256 or 'unknown'),)
    def gate(category,passed,reason,errors=()):
        status='PASS' if passed else 'BLOCKED'
        if not passed: blockers.extend(errors or ('REPAIR_REQUIREMENT_NOT_MET:'+category,))
        gates.append(ReviewGate(digest(['managed-repair',category]),category,status,scope,(),reason,
                               'Resolve the named evidence failure and generate a new exact review.'))
    env=report.inventory.environment
    branch={'jammy':'php8.1','noble':'php8.3'}.get(env.codename)
    gate('supported_environment',env.os_id=='ubuntu' and env.scope!='container' and branch==source_cohort
         and bool(selected) and all(p.architecture in {'amd64','all'} for p in report.inventory.packages if p.id in selected),
         'Initial managed policy: official Ubuntu jammy/noble amd64, one complete PHP source cohort; no container in-place repair.')
    for category in ('vendor_rules','target_selection','archive_chain','target_identity','dependency_changes',
                     'input_stability','evidence_freshness','diagnostic_simulation','package_manager_locks'):
        item=next(g for g in diagnostic.gates if g.category==category)
        gate(category,item.status=='PASS',item.reason)
    source_errors=[b for b in (report.apt_sources or {}).get('blockers',['SOURCE_POLICY_UNKNOWN'])
                   if b!='DPKG_DIVERSIONS_REQUIRE_REVIEW']
    gate('source_policy',not source_errors,'Official sources and a plain package-manager configuration are required.',source_errors)
    gate('pin_hold_dpkg',not source_errors and overrides['status']=='PASS','No holds/incomplete state or target payload diversion/statoverride.',overrides['blockers'])
    gate('apt_special_configuration',not source_errors,'Special APT hooks/options remain blocking in the initial managed profile.',source_errors)
    identities={r['package_id']:r for r in (report.package_trust or {}).get('installed',[])}
    identity_ok=selected and all(identities.get(p,{}).get('status') in {'AUTHENTICATED_RUNTIME_FILES','AUTHENTICATED_METADATA_ONLY_ARCHIVE'} for p in selected)
    gate('installed_target_identity',bool(identity_ok),'Every selected installed archive/file set has positive identity evidence.')
    gate('maintainer_scripts_conffiles',maintenance['status']=='READY_FOR_MAINTENANCE_REVIEW' and inputs['status']=='READY_FOR_EXECUTION_POLICY_REVIEW'
         and triggers['status']=='PASS' and predeps['status']=='PASS',
         'Exact old/new scripts, unchanged conffiles, disk control files and allowed trigger handlers are presented for hash confirmation; pre-dependencies must already be configured and unchanged.',
         maintenance['blockers']+inputs['blockers']+triggers['blockers']+predeps['blockers'])
    services=tuple(body.get('services',[])); consumed=(consumers or {}).get('consumers',[])
    covered=(consumers and consumers['status']=='VERIFIED_ACTIVE_MAPPING_CENSUS' and bool(services)
             and {c['service'] for c in consumed}==set(services)
             and all(c['runtime_id'] in body['runtime_ids'] for c in consumed))
    custom=any(h.pid is None and h.path and not h.path.startswith('/etc/php/') for h in report.inventory.runtime_hints)
    gate('consumer_completeness',bool(covered) and not custom,
         'All visible active consumers of the exact selected package files belong to the verified prepared services. Idle/future code and other images are not declared runtime-safe.',
         (consumers or {}).get('blockers',[]))
    gate('loaded_configuration',startup['status']=='VERIFIED_CURRENT_PREPARED_SCOPE','Signed startup, current read-only namespace views and implementation bindings verified.',startup['blockers'])
    gate('request_attribution',startup['status']=='VERIFIED_CURRENT_PREPARED_SCOPE','Every declared pool/request has a fresh kernel-bound collector response; arbitrary application routes are outside this claim.',startup['blockers'])
    gate('installation_equivalence',diagnostic.apt_simulation=='PASS' and inputs['status']=='READY_FOR_EXECUTION_POLICY_REVIEW',
         'APT solves the exact dependency set; bounded direct dpkg executes only that set. This is an explicit reviewed strategy, not a claim that APT hooks run.')
    gate('service_interruption',bool(services),'Exact services and a finite interruption budget are in the confirmation contract; no rollback is promised.')
    gate('execution_authorization',True,'No authorization yet. The transaction requires explicit confirmation of this exact plan hash.')
    files_coverage=check('managed_package_operation','VERIFIED' if not blockers else 'UNKNOWN',scope,(),
        'Finite package-file/active-consumer operation only. Global scan UNKNOWNs remain in the attached diagnostic evidence.',
        'Review all remaining blockers and exact maintenance effects.',blocks=bool(blockers))
    consumer_id=lambda c:c['runtime_id'] or f"{env.scope_sha256}:{c['pid']}:{c['start_ticks']}"
    impacts=tuple(PackageImpact(p,tuple(sorted(consumer_id(c) for c in consumed if p in c['package_ids'])),
        tuple(sorted({c['service'] for c in consumed if p in c['package_ids'] and c['service']})),(files_coverage.id,),
        'VERIFIED_WITHIN_DECLARED_SCOPE' if not blockers else 'UNKNOWN') for p in sorted(selected))
    operation_scope=PlanScope(env.scope_sha256 or 'unknown',tuple(sorted(selected)),tuple(sorted(selected)),
        tuple(sorted(consumer_id(c) for c in consumed)),
        tuple(sorted(consumer_id(c) for c in consumed if c['status']!='ACCOUNTED_ACTIVE_CONSUMER')),impacts)
    def controls(review):
        return [{k:a[k] for k in ('package_id','version','roles','archive_sha256','archive_path','control_files','conffiles','payload_configuration','execution_files','info_basename')}
                for a in (review or {}).get('archives',[])]
    contract={'schema_version':1,'protocol':'EXACT_OFFICIAL_PHP_COHORT_DPKG_V1','implementation_sha256':policy_digest(),
        'source_cohort':source_cohort,'package_cache':package_cache,'state_directory':str(controller.state_dir),
        'startup_receipt':startup_receipt,'maintenance_budget_seconds':budget_seconds,'services':services,
        'targets':[asdict(t) for t in diagnostic.targets],'changes':[asdict(c) for c in diagnostic.changes],
        'maintenance_archives':controls(maintenance),'trigger_archives':controls(triggers['maintenance']),
        'trigger_handlers':triggers['names'],'path_overrides':overrides,'predependencies':predeps,
        'input_bindings':[{k:e[k] for k in ('operation','target','outcome','sha256')} for e in inputs['evidence']],
        'strategy':['Stage authenticated exact archives in a root-private directory',
            'Hold the frontend lock; dpkg retains its backend lock; no downloads/removals/downgrades',
            'Temporarily suppress policy-rc.d service autostart; run reviewed unpack/configure and only approved pending triggers',
            'Restart all declared affected services and verify new process identities, immutable configuration views and explicit collector health',
            'Report PARTIAL/RESTART_REQUIRED on failure and retain private logs; no automatic rollback'],
        'runtime_claim':'Selected managed package files and currently verified consumers only; no claim about history, arbitrary routes or other images.'}
    deadlines=[datetime.fromisoformat(diagnostic.expires_at),datetime.fromisoformat(startup['expires_at'])]
    if consumers: deadlines.append(datetime.fromisoformat(consumers['expires_at']))
    proposal=replace(diagnostic,schema_version=5,status='BLOCKED' if blockers else ('READY_FOR_CONFIRMATION' if diagnostic.changes else 'NO_PACKAGE_CHANGES'),
        executable=False,blockers=tuple(sorted(set(blockers))),services=services,
        scope=operation_scope,coverage=(files_coverage,),gates=tuple(gates),
        expires_at=min(deadlines).isoformat(),target_policy='MANAGED_SOURCE_COHORT',
        admission_status='READY_FOR_CONFIRMATION' if not blockers and diagnostic.changes else 'BLOCKED',
        execution_contract_sha256=digest(contract),plan_sha256='')
    proposal=replace(proposal,plan_sha256=digest(asdict(proposal)))
    evidence={'diagnostic_plan':asdict(diagnostic),'startup':startup,'maintenance':maintenance,'execution_inputs':inputs,
              'consumers':consumers,'trigger_review':triggers,'global_scan_coverage_gaps':report.inventory.coverage_gaps}
    return RepairReview(proposal,json.dumps(contract,sort_keys=True),json.dumps(evidence,sort_keys=True))
