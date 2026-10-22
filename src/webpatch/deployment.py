"""Reconcile an explicit deployment inventory with local observations.

Matching observations are a useful prerequisite, never proof that a declaration
is exhaustive. This module has no I/O, probe, approval or execution capability.
"""
from dataclasses import asdict
from datetime import datetime
import hashlib
import json

from .coverage import relation_ref, runtime_id
from .gates import evidence_deadline
from .planning import stable_bindings

SCHEMA = 1
MAX_ENTITIES = 16384


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in {'evidence_id', 'evidence_ids'}}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    return value


def observations(report):
    inventory = report.inventory
    rows = []
    for package in inventory.packages:
        rows.append({'kind': 'package', 'id': package.id, 'facts': stable(asdict(package))})
    for runtime in inventory.runtimes:
        rows.append({'kind': 'runtime', 'id': runtime_id(inventory, runtime), 'facts': stable(asdict(runtime))})
    for service in sorted({r.service for r in inventory.runtimes if r.service}):
        rows.append({'kind': 'service', 'id': service,
                     'facts': {'runtime_ids': sorted(runtime_id(inventory, r) for r in inventory.runtimes if r.service == service)}})
    for relation in inventory.config_relations:
        entity = relation_ref(relation)
        rows.append({'kind': entity.kind, 'id': entity.id, 'facts': stable(asdict(relation))})
    for hint in inventory.runtime_hints:
        if hint.pid is None and hint.path:
            rows.append({'kind': 'installation', 'id': hint.path, 'facts': stable(asdict(hint))})
    # Keep distinct IDs; duplicate package/config entries must not be silently collapsed.
    keys = [(r['kind'], r['id']) for r in rows]
    if len(keys) != len(set(keys)) or len(rows) > MAX_ENTITIES:
        raise ValueError('DEPLOYMENT_AMBIGUOUS_OR_TOO_LARGE')
    return sorted(rows, key=lambda r: (r['kind'], r['id']))


def create_manifest(report, now):
    if not now.tzinfo or datetime.fromisoformat(report.observed_at) > now:
        raise ValueError('DEPLOYMENT_CLOCK_INVALID')
    document = {'schema_version': SCHEMA, 'kind': 'observed_deployment',
                'scope_sha256': report.inventory.environment.scope_sha256,
                'rule_sha256': report.rule_sha256, 'created_at': now.isoformat(),
                'expires_at': evidence_deadline(report, now).isoformat(),
                'entities': observations(report),
                'inputs_sha256': digest([asdict(b) for b in stable_bindings(report)]),
                'completeness': 'UNPROVEN', 'authorization': 'NONE', 'manifest_sha256': ''}
    document['manifest_sha256'] = digest(document)
    return document


def reconcile(document, report, now, expected_sha256=None):
    """Recompute facts, not trust caller supplied completeness or safety claims."""
    reasons, missing, unexpected, changed = [], [], [], []
    known_hash = None
    try:
        if not isinstance(document, dict) or set(document) != {
                'schema_version', 'kind', 'scope_sha256', 'rule_sha256', 'created_at', 'expires_at',
                'entities', 'inputs_sha256', 'completeness', 'authorization', 'manifest_sha256'}:
            raise ValueError('DEPLOYMENT_SCHEMA_INVALID')
        if (type(document['schema_version']) is not int or document['schema_version'] != SCHEMA
                or document['kind'] != 'observed_deployment' or document['completeness'] != 'UNPROVEN'
                or document['authorization'] != 'NONE'):
            raise ValueError('DEPLOYMENT_CLAIM_INVALID')
        known_hash = document['manifest_sha256']
        if not isinstance(known_hash, str) or len(known_hash) != 64 or digest(dict(document, manifest_sha256='')) != known_hash:
            reasons.append('DEPLOYMENT_DIGEST_MISMATCH')
        if expected_sha256 is not None and known_hash != expected_sha256:
            reasons.append('DEPLOYMENT_REVIEWED_DIGEST_MISMATCH')
        created, expires = (datetime.fromisoformat(document[k]) for k in ('created_at', 'expires_at'))
        if not created.tzinfo or not expires.tzinfo or not created <= now < expires:
            reasons.append('DEPLOYMENT_EXPIRED_OR_CLOCK_REVERSED')
        if expires > evidence_deadline(report, created):
            reasons.append('DEPLOYMENT_VALIDITY_EXCEEDS_EVIDENCE')
        if not document['scope_sha256'] or document['scope_sha256'] != report.inventory.environment.scope_sha256:
            reasons.append('DEPLOYMENT_SCOPE_MISMATCH')
        if document['rule_sha256'] != report.rule_sha256:
            reasons.append('DEPLOYMENT_RULES_CHANGED')
        if document['inputs_sha256'] != digest([asdict(b) for b in stable_bindings(report)]):
            reasons.append('DEPLOYMENT_INPUTS_CHANGED')
        entities = document['entities']
        if not isinstance(entities, list) or len(entities) > MAX_ENTITIES:
            raise ValueError('DEPLOYMENT_ENTITIES_INVALID')
        expected = {}
        for entity in entities:
            if (not isinstance(entity, dict) or set(entity) != {'kind', 'id', 'facts'}
                    or entity['kind'] not in {'package', 'runtime', 'service', 'pool', 'route', 'installation'}
                    or not isinstance(entity['id'], str) or not isinstance(entity['facts'], dict)):
                raise ValueError('DEPLOYMENT_ENTITY_INVALID')
            key = (entity['kind'], entity['id'])
            if key in expected:
                raise ValueError('DEPLOYMENT_DUPLICATE_ENTITY')
            expected[key] = entity['facts']
        actual = {(e['kind'], e['id']): e['facts'] for e in observations(report)}
        missing = [{'kind': k[0], 'id': k[1]} for k in sorted(expected.keys() - actual.keys())]
        unexpected = [{'kind': k[0], 'id': k[1]} for k in sorted(actual.keys() - expected.keys())]
        changed = [{'kind': k[0], 'id': k[1]} for k in sorted(expected.keys() & actual.keys()) if expected[k] != actual[k]]
        if missing: reasons.append('DEPLOYMENT_EXPECTED_ENTITIES_MISSING')
        if unexpected: reasons.append('DEPLOYMENT_UNDECLARED_ENTITIES')
        if changed: reasons.append('DEPLOYMENT_ENTITY_FACTS_CHANGED')
        if not actual:
            reasons.append('DEPLOYMENT_EMPTY_IS_NOT_COVERAGE')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        reasons.append(str(exc) if isinstance(exc, ValueError) and str(exc).startswith('DEPLOYMENT_') else 'DEPLOYMENT_DOCUMENT_INVALID')
    return {'schema_version': SCHEMA, 'status': 'MATCHED_OBSERVATIONS' if not reasons else 'BLOCKED',
            'manifest_sha256': known_hash, 'scope_sha256': report.inventory.environment.scope_sha256,
            'missing': missing, 'unexpected': unexpected, 'changed': changed,
            'blockers': sorted(set(reasons)), 'completeness': 'UNPROVEN', 'executable': False,
            'remaining_requirements': ['Independent consumer completeness evidence', 'Loaded configuration and request attribution',
                                       'Maintenance review and explicit plan-hash authorization']}
