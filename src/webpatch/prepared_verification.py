"""Consume authenticated startup facts only after fresh local verification."""
from datetime import datetime, timedelta, timezone

from .application import collect_application_evidence
from .coverage import runtime_id
from .planning import digest
from .preparation import implementation_digest, static_inputs, verify_snapshot_views
from .system import ProbeError


def verify_prepared_scope(document, report, *, system, controller, probe, now=None):
    now=now or datetime.now(timezone.utc)
    reasons=[]; views=None; requests=[]; body=None
    try:
        body=controller.store.verify(document)
        if body.get('kind')!='controlled_startup' or body.get('status')!='VERIFIED_CONTROLLED_STARTUP':
            raise ValueError('PREPARED_STARTUP_RECEIPT_REQUIRED')
        start,end=(datetime.fromisoformat(body[k]) for k in ('prepared_at','expires_at'))
        if not start.tzinfo or not end.tzinfo or not start<=now<end or end>start+timedelta(minutes=30):
            raise ValueError('PREPARED_RECEIPT_EXPIRED_OR_INVALID')
        if body.get('implementation_sha256')!=implementation_digest() or body.get('rule_sha256')!=report.rule_sha256:
            raise ValueError('PREPARED_IMPLEMENTATION_OR_RULE_DRIFT')
        if body['scope_sha256']!=report.inventory.environment.scope_sha256:
            raise ValueError('PREPARED_SCOPE_DRIFT')
        if body['static_inputs_sha256']!=digest(static_inputs(report)):
            raise ValueError('PREPARED_STATIC_INPUT_DRIFT')
        runtimes=[r for r in report.inventory.runtimes if r.service in body['services']]
        identities=sorted(runtime_id(report.inventory,r) for r in runtimes)
        if not identities or identities!=body['runtime_ids'] or any(r.association!='VERIFIED_LOCAL_ASSOCIATION' for r in runtimes):
            raise ValueError('PREPARED_RUNTIME_SET_DRIFT')
        if not body['probes'] or {p['service'] for p in body['probes']}!=set(body['services']):
            raise ValueError('PREPARED_REQUEST_SET_INCOMPLETE')
        controller.verify_loaded_definitions(body,system)
        views=verify_snapshot_views(report,body['snapshots'],system)
        if views['status']!='VERIFIED_READONLY_RUNTIME_VIEWS':
            reasons.extend(views['blockers'])
            raise ValueError('PREPARED_CONFIGURATION_VIEW_DRIFT')
        for target in body['probes']:
            current=collect_application_evidence(report,system=system,probe=probe,url=target['url'],script_path=target['script'],
                                                 service=target['service'],now=now)
            requests.append(current)
            if current['status']!='VERIFIED_PROCESS_RESPONSE':
                raise ValueError('PREPARED_FRESH_REQUEST_FAILED')
            runtime=next(r for r in runtimes if r.pid==current['peer_pid'])
            if target['pool_listener'] is not None and target['pool_listener'] not in {e.path for e in runtime.endpoints}:
                raise ValueError('PREPARED_REQUEST_POOL_CHANGED')
            if target['configuration']!=current['configuration']:
                raise ValueError('PREPARED_EFFECTIVE_SETTINGS_CHANGED')
    except (ValueError,KeyError,TypeError,StopIteration,OSError,ProbeError) as exc:
        reason=str(exc)
        reasons.append(reason if reason.startswith(('PREPARED_','RECEIPT_','SERVICE_')) else 'PREPARED_VERIFICATION_INPUT_INVALID')
    result={'schema_version':1,'status':'VERIFIED_CURRENT_PREPARED_SCOPE' if not reasons else 'BLOCKED',
            'scope_sha256':report.inventory.environment.scope_sha256,'startup_receipt_sha256':digest(document),
            'observed_at':now.isoformat(),'expires_at':min([now+timedelta(minutes=5),
                *([datetime.fromisoformat(body['expires_at'])] if body and not reasons else []),
                *[datetime.fromisoformat(p['expires_at']) for p in requests]]).isoformat(),
            'views':views,'requests':requests,'blockers':sorted(set(reasons)),
            'claim':'Current authenticated startup, read-only input views and explicitly declared requests only.',
            'executable':False,'verification_sha256':''}
    result['verification_sha256']=digest(result)
    return result
