from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import pytest

from conftest import NOW, FakeSystem
from test_runtime_evidence import connected_fixture
from webpatch.deployment import create_manifest, reconcile, digest
from webpatch.service import scan
from webpatch.system import DPKG_QUERY, CommandResult
from webpatch.cli import main


def fixture():
    fake = connected_fixture()
    report = scan(fake, now=NOW)
    return fake, report, create_manifest(report, NOW)


def rehash(document):
    document['manifest_sha256'] = digest(dict(document, manifest_sha256=''))
    return document


def test_observed_deployment_has_independent_entities_and_never_grants_completeness():
    _, report, document = fixture()
    assert {'package', 'runtime', 'service', 'pool', 'route'} <= {e['kind'] for e in document['entities']}
    result = reconcile(document, report, NOW, document['manifest_sha256'])
    assert result['status'] == 'MATCHED_OBSERVATIONS' and not result['blockers']
    assert result['completeness'] == 'UNPROVEN' and result['executable'] is False
    assert document['authorization'] == 'NONE'


@pytest.mark.parametrize('mutation,reason', [
    ('scope', 'DEPLOYMENT_SCOPE_MISMATCH'),
    ('rule', 'DEPLOYMENT_RULES_CHANGED'),
    ('package', 'DEPLOYMENT_ENTITY_FACTS_CHANGED'),
    ('configuration', 'DEPLOYMENT_INPUTS_CHANGED'),
    ('new-process', 'DEPLOYMENT_UNDECLARED_ENTITIES'),
    ('missing-process', 'DEPLOYMENT_EXPECTED_ENTITIES_MISSING'),
])
def test_fresh_observations_identify_scope_and_entity_drift(mutation, reason):
    fake, report, document = fixture()
    if mutation == 'scope': report.inventory.environment = replace(report.inventory.environment, scope_sha256='f' * 64)
    if mutation == 'rule': report = replace(report, rule_sha256='f' * 64)
    if mutation == 'package': report.inventory.packages[0] = replace(report.inventory.packages[0], version='changed')
    if mutation == 'configuration':
        fake.reads['/etc/php/8.1/fpm/pool.d/www.conf'] += '\n; changed without restart'
        report = scan(fake, now=NOW)
    if mutation == 'new-process': report.inventory.runtimes.append(replace(report.inventory.runtimes[0], pid=43, start_ticks='456'))
    if mutation == 'missing-process': report.inventory.runtimes.clear()
    result = reconcile(document, report, NOW)
    assert result['status'] == 'BLOCKED' and reason in result['blockers']


def test_rehashed_omission_cannot_hide_shared_package_consumer():
    _, report, document = fixture()
    document['entities'] = [e for e in document['entities'] if e['kind'] != 'runtime']
    result = reconcile(rehash(document), report, NOW)
    assert 'DEPLOYMENT_UNDECLARED_ENTITIES' in result['blockers']
    assert any(e['kind'] == 'runtime' for e in result['unexpected'])


def test_tampering_review_digest_expiry_and_self_declared_completeness_fail_closed():
    _, report, document = fixture()
    original = document['manifest_sha256']
    changed = deepcopy(document)
    changed['created_at'] = (NOW - timedelta(seconds=1)).isoformat()
    assert 'DEPLOYMENT_DIGEST_MISMATCH' in reconcile(changed, report, NOW)['blockers']
    rehash(changed)
    assert 'DEPLOYMENT_REVIEWED_DIGEST_MISMATCH' in reconcile(changed, report, NOW, original)['blockers']
    assert 'DEPLOYMENT_EXPIRED_OR_CLOCK_REVERSED' in reconcile(document, report, NOW + timedelta(minutes=30))['blockers']
    changed['expires_at'] = (NOW + timedelta(days=1)).isoformat()
    assert 'DEPLOYMENT_VALIDITY_EXCEEDS_EVIDENCE' in reconcile(rehash(changed), report, NOW)['blockers']
    changed['completeness'] = 'COMPLETE'
    assert 'DEPLOYMENT_CLAIM_INVALID' in reconcile(rehash(changed), report, NOW)['blockers']


@pytest.mark.parametrize('bad', [None, [], {}, {'schema_version': True}, {'entities': 'bad'}])
def test_invalid_document_is_a_blocked_result(bad):
    _, report, _ = fixture()
    assert reconcile(bad, report, NOW)['status'] == 'BLOCKED'


def test_duplicate_entities_and_unknown_fields_do_not_get_silently_ignored():
    _, report, document = fixture()
    document['entities'].append(document['entities'][0])
    assert 'DEPLOYMENT_DUPLICATE_ENTITY' in reconcile(rehash(document), report, NOW)['blockers']
    document['approved'] = True
    assert 'DEPLOYMENT_SCHEMA_INVALID' in reconcile(rehash(document), report, NOW)['blockers']


def test_empty_or_unidentified_scope_is_not_matched_coverage():
    report = scan(FakeSystem({}), now=NOW)
    document = create_manifest(report, NOW)
    assert 'DEPLOYMENT_EMPTY_IS_NOT_COVERAGE' in reconcile(document, report, NOW)['blockers']
    report.inventory.environment = replace(report.inventory.environment, scope_sha256=None)
    document = create_manifest(report, NOW)
    assert 'DEPLOYMENT_SCOPE_MISMATCH' in reconcile(document, report, NOW)['blockers']


def test_evidence_labels_and_unrelated_process_churn_do_not_change_manifest_facts():
    fake, report, document = fixture()
    fake.dirs['/proc'].append('99')
    fake.reads['/proc/99/comm'] = 'python3'
    current = scan(fake, now=NOW)
    assert reconcile(document, current, NOW)['status'] == 'MATCHED_OBSERVATIONS'


def test_cli_only_scans_and_reconciles_without_simulation_or_execution(capsys):
    from test_planning import FakeSimulator
    fake, _, _ = fixture()
    simulator = FakeSimulator()
    assert main(['deployment-manifest'], system=fake, simulator=simulator, now=NOW) == 4
    document = json.loads(capsys.readouterr().out)
    fake.reads['/deployment.json'] = json.dumps(document)
    assert main(['verify-deployment', '/deployment.json', '--expect-sha256', document['manifest_sha256']],
                system=fake, simulator=simulator, now=NOW) == 4
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'MATCHED_OBSERVATIONS' and not result['executable']
    assert simulator.calls == []
