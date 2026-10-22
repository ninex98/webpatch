"""Typed managed-repair transaction bridge. Public apply is not enabled here."""
from dataclasses import asdict,fields
from datetime import datetime,timedelta,timezone
import json
import time
from typing import get_args

from . import models
from .application import collect_application_evidence
from .consumers import census
from .coverage import runtime_id
from .implementation import implementation_sha256
from .package_control import ApprovedArchive,PackageOperation
from .planning import digest,check_bindings
from .preparation import verify_snapshot_views
from .repair_policy import build_repair_review
from .service import scan
from .system import ProbeError,Collector
from .transaction import StepResult,execute


def decode_plan(raw):
    """Decode data into known dataclasses; no dynamic class/argv dispatch."""
    def obj(cls,value,converters=None):
        if not isinstance(value,dict) or set(value)!={f.name for f in fields(cls)}:
            raise ValueError('REPAIR_PLAN_SCHEMA_INVALID')
        values=dict(value)
        for name,convert in (converters or {}).items(): values[name]=convert(values[name])
        for field in fields(cls):
            if field.name in (converters or {}): continue
            allowed=get_args(field.type) or (field.type,)
            if not any(type(values[field.name]) is expected for expected in allowed):
                raise ValueError('REPAIR_PLAN_FIELD_TYPE_INVALID')
        return cls(**values)
    def seq(convert):
        def decode(value):
            if not isinstance(value,list): raise ValueError('REPAIR_PLAN_SEQUENCE_INVALID')
            return tuple(convert(item) for item in value)
        return decode
    def string(value):
        if not isinstance(value,str): raise ValueError('REPAIR_PLAN_STRING_INVALID')
        return value
    strings=seq(string)
    refs=seq(lambda x:obj(models.EntityRef,x))
    impacts=seq(lambda x:obj(models.PackageImpact,x,{k:strings for k in ('runtime_ids','services','coverage_ids')}))
    scope=lambda x:obj(models.PlanScope,x,{**{k:strings for k in ('requested_package_ids','affected_package_ids','observed_runtime_ids','unresolved_runtime_ids')},'impacts':impacts})
    converters={k:strings for k in ('blockers','recommendations','actions','services','interruptions')}
    converters.update(targets=seq(lambda x:obj(models.PackageTarget,x)),changes=seq(lambda x:obj(models.PackageChange,x)),
        bindings=seq(lambda x:obj(models.InputBinding,x)),evidence=seq(lambda x:obj(models.Evidence,x)),
        scan_evidence=seq(lambda x:obj(models.Evidence,x)),scope=scope,
        coverage=seq(lambda x:obj(models.CoverageCheck,x,{'subjects':refs,'evidence_ids':strings})),
        gates=seq(lambda x:obj(models.ReviewGate,x,{'subjects':refs,'evidence_ids':strings})))
    result=obj(models.Plan,raw,converters)
    if json.loads(json.dumps(asdict(result)))!=raw: raise ValueError('REPAIR_PLAN_NONCANONICAL')
    return result


def review_semantics(proposal,contract):
    values=asdict(proposal)
    for key in ('plan_sha256','report_sha256','created_at','expires_at','evidence','scan_evidence','review_evidence_sha256'):
        values.pop(key)
    for gate in values['gates']:
        gate.pop('evidence_ids')
        if gate['category']=='evidence_freshness': gate['reason']='FRESH_WITHIN_CURRENT_EVIDENCE_DEADLINE'
    return {'plan':values,'contract':digest(contract)}


class ManagedRepairBackend:
    def __init__(self,approved,contract,*,system,simulator,controller,probe,clock,scanner=scan,monotonic=time.monotonic):
        self.approved=approved; self.contract=contract; self.system=system; self.simulator=simulator
        self.controller=controller; self.probe=probe; self.clock=clock; self.scanner=scanner
        self.current=None; self.verification=None; self.operation_started=None
        self.monotonic=monotonic

    def locked(self): return self.controller.locked()

    def revalidate(self,expected):
        current=self.scanner(self.system,now=self.clock(),package_cache=self.contract['package_cache'])
        review=build_repair_review(current,system=self.system,simulator=self.simulator,controller=self.controller,
            probe=self.probe,startup_receipt=self.contract['startup_receipt'],source_cohort=self.contract['source_cohort'],
            package_cache=self.contract['package_cache'],budget_seconds=self.contract['maintenance_budget_seconds'],clock=self.clock)
        if (review.proposal.admission_status!='READY_FOR_CONFIRMATION'
                or review_semantics(expected,self.contract)!=review_semantics(review.proposal,json.loads(review.contract_json))
                or datetime.fromisoformat(expected.expires_at)>datetime.fromisoformat(review.proposal.expires_at)):
            return False
        self.current=review
        return True

    def remaining(self):
        if self.operation_started is None: return self.contract['maintenance_budget_seconds']
        return self.contract['maintenance_budget_seconds']-(self.monotonic()-self.operation_started)

    def install(self,targets):
        if self.current is None: return StepResult(False,False,reason='REPAIR_CURRENT_REVIEW_REQUIRED')
        self.operation_started=self.monotonic()
        changes={(c.name,c.architecture,c.new_version) for c in self.current.proposal.changes}
        archives=[]
        for a in self.contract['maintenance_archives']:
            name,arch=a['package_id'].rsplit(':',1)
            if (name,arch,a['version']) in changes and 'candidate' in a['roles']:
                archives.append(ApprovedArchive(name,arch,a['version'],a['archive_path'],a['archive_sha256']))
        if len(archives)!=len(changes): return StepResult(False,False,reason='REPAIR_EXACT_ARCHIVE_SET_MISMATCH')
        operation=PackageOperation(self.approved.plan_sha256,tuple(archives),tuple(self.contract['trigger_handlers']),
                                   min(600,self.contract['maintenance_budget_seconds']))
        return self.controller.install_operation(operation,self.system)

    def restart(self,service):
        if service not in self.contract['services'] or self.remaining()<=0:
            return StepResult(False,False,reason='REPAIR_SERVICE_OR_BUDGET_INVALID')
        try:
            self.controller.command('restart',service,timeout_seconds=min(60,self.remaining()))
            self.controller.wait_stable(service,timeout_seconds=min(10,self.remaining()))
            return StepResult(self.remaining()>0,True,reason='REPAIR_SERVICE_RESTARTED')
        except (OSError,ValueError,ProbeError) as exc:
            return StepResult(False,True,reason='REPAIR_RESTART_FAILED:'+type(exc).__name__)

    def verify(self,expected):
        reasons=[]; body=self.contract['startup_receipt']['payload']; requests=[]
        report=self.scanner(self.system,now=self.clock(),package_cache=self.contract['package_cache'])
        if report.inventory.environment.scope_sha256!=expected.scope.scan_scope_id: reasons.append('REPAIR_POST_SCOPE_CHANGED')
        if report.rule_sha256!=expected.rule_sha256 or (report.package_trust or {}).get('status')!='VERIFIED_INDEX_CHAIN':
            reasons.append('REPAIR_POST_RULE_OR_INDEX_CHAIN_CHANGED')
        source_errors=[b for b in (report.apt_sources or {}).get('blockers',['SOURCE_POLICY_UNKNOWN']) if b!='DPKG_DIVERSIONS_REQUIRE_REVIEW']
        if source_errors: reasons.append('REPAIR_POST_SOURCE_POLICY_BLOCKED')
        source_bindings=tuple(b for b in self.current.proposal.bindings if b.target.startswith(('/etc/apt/','/var/lib/apt/lists/')))
        if not check_bindings(Collector(self.system),source_bindings): reasons.append('REPAIR_POST_SOURCE_INPUT_DRIFT')
        packages={p.id:p for p in report.inventory.packages}
        identities={p['package_id']:p for p in (report.package_trust or {}).get('installed',[])}
        for target in expected.targets:
            key=target.name+':'+target.architecture; package=packages.get(key)
            if (package is None or package.version!=target.version or package.status!='install ok installed'
                    or identities.get(key,{}).get('status') not in {'AUTHENTICATED_RUNTIME_FILES','AUTHENTICATED_METADATA_ONLY_ARCHIVE'}):
                reasons.append('REPAIR_POST_PACKAGE_IDENTITY_UNKNOWN:'+key)
        engines={p.id for p in report.inventory.packages if p.id in expected.scope.affected_package_ids and p.sapi in {'fpm','apache2','cgi','cli'}}
        assessments=[a for a in report.assessments if a.package_id in engines]
        if not assessments or any(a.version_status!='MEETS_VENDOR_FIX' for a in assessments): reasons.append('REPAIR_POST_VENDOR_BOUNDARY_NOT_MET')
        runtimes=[r for r in report.inventory.runtimes if r.service in expected.services]
        current_ids={runtime_id(report.inventory,r) for r in runtimes}
        if (not current_ids or current_ids&set(body['runtime_ids']) or {r.service for r in runtimes}!=set(expected.services)
                or any(r.association!='VERIFIED_LOCAL_ASSOCIATION' for r in runtimes)):
            reasons.append('REPAIR_POST_RUNTIME_REPLACEMENT_UNVERIFIED')
        self.controller.verify_loaded_definitions(body,self.system)
        views=verify_snapshot_views(report,body['snapshots'],self.system)
        if not body['snapshots'] or not body['probes']: reasons.append('REPAIR_POST_CONFIGURATION_OR_PROBES_MISSING')
        if views['status']!='VERIFIED_READONLY_RUNTIME_VIEWS': reasons.extend(views['blockers'])
        consumers=census(report,system=self.system,package_ids=expected.scope.affected_package_ids,clock=self.clock)
        if consumers['status']!='VERIFIED_ACTIVE_MAPPING_CENSUS': reasons.extend(consumers['blockers'])
        if any(c['service'] not in expected.services for c in consumers['consumers']): reasons.append('REPAIR_POST_UNEXPECTED_CONSUMER')
        for target in body['probes']:
            proof=collect_application_evidence(report,system=self.system,probe=self.probe,url=target['url'],script_path=target['script'],
                service=target['service'],clock=self.clock)
            requests.append(proof)
            if proof['status']!='VERIFIED_PROCESS_RESPONSE': reasons.extend(proof['blockers']); continue
            runtime=next(r for r in runtimes if r.pid==proof['peer_pid'])
            if target['pool_listener'] is not None and target['pool_listener'] not in {e.path for e in runtime.endpoints}:
                reasons.append('REPAIR_POST_REQUEST_POOL_CHANGED')
            # Extension version metadata can legitimately change with signed new
            # engine/module bytes. Frozen input paths and effective settings must
            # remain the reviewed configuration; record new extension metadata.
            if any(target['configuration'][k]!=proof['configuration'][k] for k in ('ini_file','ini_scanned','effective_ini_sha256')):
                reasons.append('REPAIR_POST_EFFECTIVE_CONFIGURATION_CHANGED')
        deadlines=[datetime.fromisoformat(consumers['expires_at']),*[datetime.fromisoformat(p['expires_at']) for p in requests]]
        if self.clock()>=min(deadlines): reasons.append('REPAIR_POST_EVIDENCE_EXPIRED')
        if self.remaining()<=0: reasons.append('REPAIR_MAINTENANCE_BUDGET_EXCEEDED')
        self.verification={'scope_sha256':expected.scope.scan_scope_id,'status':'VERIFIED_WITHIN_DECLARED_SCOPE' if not reasons else 'BLOCKED',
            'report':asdict(report),'views':views,'consumers':consumers,'requests':requests,'blockers':sorted(set(reasons)),'safe':False}
        return StepResult(not reasons,False,digest(self.verification),'REPAIR_POST_VERIFIED' if not reasons else 'REPAIR_POST_VERIFICATION_FAILED')


def execute_repair_review(document,*,confirmation_sha256,system,simulator,controller,probe,journal,clock=None,scanner=scan):
    clock=clock or (lambda:datetime.now(timezone.utc))
    try:
        if not isinstance(document,dict) or set(document)!={'schema_version','kind','plan','contract','evidence'}:
            raise ValueError('REPAIR_REVIEW_SCHEMA_INVALID')
        document=json.loads(json.dumps(document))  # isolate the immutable approved data
        if type(document['schema_version']) is not int or document['schema_version']!=1 or document['kind']!='managed_package_repair_review':
            raise ValueError('REPAIR_REVIEW_SCHEMA_INVALID')
        proposal=decode_plan(document['plan']); contract=document['contract']
        if type(proposal.schema_version) is not int or proposal.schema_version!=5 or proposal.status!='READY_FOR_CONFIRMATION' or proposal.executable is not False:
            raise ValueError('REPAIR_REVIEW_NOT_ADMITTED')
        if (proposal.plan_sha256!=confirmation_sha256 or digest(dict(document['plan'],plan_sha256=''))!=proposal.plan_sha256
                or digest(contract)!=proposal.execution_contract_sha256 or digest(document['evidence'])!=proposal.review_evidence_sha256):
            raise ValueError('REPAIR_EXACT_CONFIRMATION_OR_CONTRACT_MISMATCH')
        if (contract['protocol']!='EXACT_OFFICIAL_PHP_COHORT_DPKG_V1'
                or contract['implementation_sha256']!=implementation_sha256()
                or contract['state_directory']!=str(controller.state_dir)):
            raise ValueError('REPAIR_IMPLEMENTATION_OR_STATE_DIRECTORY_CHANGED')
        start,end=datetime.fromisoformat(proposal.created_at),datetime.fromisoformat(proposal.expires_at)
        if not start.tzinfo or not end.tzinfo or not start<=clock()<end or end>start+timedelta(minutes=30):
            raise ValueError('REPAIR_REVIEW_EXPIRED_OR_INVALID')
        backend=ManagedRepairBackend(proposal,contract,system=system,simulator=simulator,controller=controller,probe=probe,clock=clock,scanner=scanner)
        result=execute(proposal,confirmation_sha256=confirmation_sha256,backend=backend,journal=journal,clock=clock)
        result['verification']=backend.verification
        result['safe']=False
        result['owned_preparation_receipt']=contract['startup_receipt']
        return result
    except (ValueError,KeyError,TypeError,OSError,ProbeError):
        return {'status':'BLOCKED','changed':False,'reasons':['REPAIR_REVIEW_INVALID_OR_UNCONFIRMED'],'safe':False}
