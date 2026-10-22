"""Entity coverage and target selection must not hide other package consumers."""
from dataclasses import asdict
import json

import pytest

from conftest import FakeSystem, NOW, CASES
from test_runtime import runtime_fixture, report
from test_planning import setup_plan
from webpatch.coverage import ref, runtime_id
from webpatch.planning import plan, verify_document
from webpatch.service import scan
from webpatch.system import ProbeError


def test_shared_package_processes_remain_visible_when_target_selected():
    fake = runtime_fixture()
    fake.dirs['/proc'].append('43')
    for mapping in (fake.reads, fake.links, fake.identities, fake.fingerprints, fake.dirs):
        for path, value in list(mapping.items()):
            if path.startswith('/proc/42/'):
                mapping[path.replace('/42/', '/43/')] = value
    result = report(fake)
    package = result.inventory.packages[0].id
    review = plan(result, now=NOW, target_package_ids=[package])
    impact = review.scope.impacts[0]
    assert len(impact.runtime_ids) == 2
    assert set(impact.runtime_ids) == set(review.scope.observed_runtime_ids)
    assert impact.services == ('php8.1-fpm.service',)
    assert impact.completeness == 'UNKNOWN'
    assert review.executable is False and review.status == 'BLOCKED'
    assert any(c.status == 'VERIFIED' and c.requirement == 'local_runtime_association' for c in review.coverage)
    assert all(c.blocks_repair for c in review.coverage if c.status != 'VERIFIED')


def test_authenticated_disk_file_and_runtime_coverage_are_distinct():
    _, result, _ = setup_plan()
    checks = result.inventory.coverage
    assert any(c.requirement == 'installed_package_files' and c.status == 'VERIFIED' for c in checks)
    assert any(c.requirement == 'package_runtime_coverage' and c.status == 'UNKNOWN' for c in checks)
    ids = {e.id for e in result.evidence}
    assert all(set(c.evidence_ids) <= ids for c in checks)
    assert len({c.id for c in checks}) == len(checks)


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_all_environment_fixtures_have_explicit_incomplete_scope(case):
    result = scan(FakeSystem(case), now=NOW)
    scope = result.inventory.scan_scope
    assert scope.completeness == 'UNKNOWN'
    assert set(scope.package_ids) == {p.id for p in result.inventory.packages}
    assert result.safe is False
    assert any(c.requirement == 'discovery_completeness' and c.blocks_repair for c in result.inventory.coverage)
    assert all(c.reason and c.next_step for c in result.inventory.coverage)


def test_permission_failure_is_linked_to_runtime_and_failed_evidence():
    fake = runtime_fixture()
    fake.fingerprints['/proc/42/exe'] = ProbeError('PermissionError')
    result = report(fake)
    check = next(c for c in result.inventory.coverage if c.requirement == 'read_coverage')
    assert ref('runtime', runtime_id(result.inventory, result.inventory.runtimes[0])) in check.subjects
    evidence = {e.id: e for e in result.evidence}
    assert evidence[check.evidence_ids[0]].outcome == 'PermissionError'
    assert check.status == 'UNKNOWN' and check.blocks_repair


def test_foreign_and_custom_installation_are_not_local_verified_coverage():
    fake = runtime_fixture()
    fake.links['/proc/42/ns/pid'] = 'pid:[2]'
    fake.dirs['/opt/php'] = ['8.4']
    result = report(fake)
    assert any(c.status == 'UNSUPPORTED' and ref('installation', '/opt/php/8.4') in c.subjects for c in result.inventory.coverage)
    review = plan(result, now=NOW)
    assert review.scope.unresolved_runtime_ids == review.scope.observed_runtime_ids
    assert all(not i.runtime_ids for i in review.scope.impacts)


def test_skipped_adapter_is_not_checked_and_old_plan_requires_rescan():
    result = scan(FakeSystem({}), now=NOW, adapters=())
    assert sum(c.status == 'NOT_CHECKED' for c in result.inventory.coverage) == 3
    current = plan(result, now=NOW)
    assert verify_document({'schema_version': 2}, current, NOW) == ('PLAN_SCHEMA_RESCAN_REQUIRED',)
    assert current.scope.requested_package_ids == () and not current.executable


def test_selected_scope_roundtrips_and_unknown_target_is_blocked(capsys):
    from webpatch.cli import main
    fake, result, simulator = setup_plan()
    saved = plan(result, system=fake, simulator=simulator, now=NOW,
                 target_package_ids=['php8.1-fpm:amd64'])
    fake.reads['/plan.json'] = json.dumps(asdict(saved))
    assert main(['verify-plan', '/plan.json'], system=fake, simulator=simulator, now=NOW) == 4
    assert json.loads(capsys.readouterr().out)['drift'] == []
    unknown = plan(result, now=NOW, target_package_ids=['php8.9-fpm:amd64'])
    assert 'TARGET_NOT_IN_SCAN:php8.9-fpm:amd64' in unknown.blockers
    assert unknown.scope.observed_runtime_ids == saved.scope.observed_runtime_ids
