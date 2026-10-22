from dataclasses import asdict, replace
from datetime import timedelta
import json

import pytest

from conftest import NOW
from test_planning import setup_plan, FakeSimulator
from test_trust import RELEASE
from webpatch.planning import plan, verify_document, validate_plan, digest
from webpatch.service import scan
from webpatch.system import ProbeError, LocalSystem, MAX_FILE_BYTES, MAX_PLAN_BYTES


def gate(proposal, category):
    return next(g for g in proposal.gates if g.category == category)


def test_positive_diagnostic_review_has_individually_passing_gates_but_no_admission():
    fake, report, simulator = setup_plan()
    proposal = plan(report, system=fake, simulator=simulator, now=NOW)
    assert proposal.review_status == 'READY_FOR_REVIEW'
    assert proposal.admission_status == 'BLOCKED' and proposal.executable is False
    for category in ('vendor_rules', 'target_identity', 'archive_chain', 'source_policy', 'target_selection',
                     'dependency_changes', 'pin_hold_dpkg', 'package_manager_locks', 'evidence_freshness', 'input_stability'):
        assert gate(proposal, category).status == 'PASS', (category, gate(proposal, category))
    assert gate(proposal, 'installation_equivalence').status == 'UNKNOWN'
    assert gate(proposal, 'maintainer_scripts_conffiles').status == 'NOT_RUN'
    assert gate(proposal, 'service_interruption').status == 'UNKNOWN'
    assert all('GATE:' + g.id in proposal.blockers for g in proposal.gates if g.status != 'PASS')
    evidence = [*proposal.scan_evidence, *proposal.evidence]
    assert len({e.id for e in evidence}) == len(evidence)
    assert all(set(g.evidence_ids) <= {e.id for e in evidence} for g in proposal.gates)
    assert all(g.reason and g.required_action for g in proposal.gates)


@pytest.mark.parametrize('remaining', [0, 1, 600])
def test_index_expiry_bounds_saved_plan_even_when_rules_are_still_valid(remaining):
    fake, _, simulator = setup_plan()
    expiry = NOW + timedelta(seconds=remaining)
    fake.reads[RELEASE] = fake.reads[RELEASE].replace('Thu, 29 Oct 2026 00:00:00 UTC', expiry.strftime('%a, %d %b %Y %H:%M:%S UTC'))
    report = scan(fake, now=NOW)
    proposal = plan(report, system=fake, simulator=simulator, now=NOW)
    if remaining:
        assert proposal.expires_at == expiry.isoformat()
        assert 'PLAN_EXPIRED_OR_CLOCK_REVERSED' in validate_plan(proposal, report, system=fake, simulator=simulator, now=expiry)
    else:
        assert proposal.review_status == 'INCOMPLETE'
        assert gate(proposal, 'archive_chain').status != 'PASS'


def test_stale_scan_and_reverse_clock_never_gain_fresh_plan_validity():
    fake, report, simulator = setup_plan()
    later = NOW + timedelta(minutes=31)
    proposal = plan(report, system=fake, simulator=simulator, now=later)
    assert proposal.expires_at == (NOW + timedelta(minutes=30)).isoformat()
    assert gate(proposal, 'evidence_freshness').status == 'BLOCKED'
    earlier = plan(report, system=fake, simulator=simulator, now=NOW - timedelta(seconds=1))
    assert gate(earlier, 'evidence_freshness').status == 'BLOCKED'


@pytest.mark.parametrize('mutation', ['pin', 'hold', 'hook', 'override', 'lock', 'dependency'])
def test_specific_gate_conflicts_have_evidence_and_resolution(mutation):
    from webpatch.system import DPKG_QUERY, CommandResult
    fake, _, simulator = setup_plan()
    expected = 'pin_hold_dpkg'
    if mutation == 'pin': fake.reads['/etc/apt/preferences'] = 'Package: *\nPin: release a=noble\nPin-Priority: 1001'
    if mutation == 'hold': fake.commands[DPKG_QUERY] = replace(fake.commands[DPKG_QUERY], stdout=fake.commands[DPKG_QUERY].stdout + 'libc6\t2.35\tamd64\tglibc\t2.35\thold ok installed\n')
    if mutation == 'hook':
        fake.reads['/etc/apt/apt.conf'] = 'DPkg::Pre-Invoke {"fixture";};'
        expected = 'apt_special_configuration'
    if mutation == 'override':
        fake.reads['/etc/apt/apt.conf'] = 'Dir::State::status "/tmp/other";'
        expected = 'apt_special_configuration'
    if mutation == 'lock':
        fake.identities['/var/lib/dpkg/lock'] = {'device': 1, 'inode': 99}
        fake.reads['/proc/locks'] = '1: POSIX ADVISORY WRITE 123 00:01:99 0 EOF\n'
        expected = 'package_manager_locks'
    if mutation == 'dependency':
        simulator.result = CommandResult(0, '0 upgraded, 0 newly installed, 1 to remove and 0 not upgraded.\nRemv libc6 [2.35]\n')
        expected = 'dependency_changes'
    proposal = plan(scan(fake, now=NOW), system=fake, simulator=simulator, now=NOW)
    assert gate(proposal, expected).status == 'BLOCKED'
    assert gate(proposal, expected).evidence_ids
    assert not proposal.executable


def test_rehashed_extended_expiry_and_saved_actions_are_rejected():
    fake, report, simulator = setup_plan()
    current = plan(report, system=fake, simulator=simulator, now=NOW)
    saved = json.loads(json.dumps(asdict(current)))
    saved['expires_at'] = (NOW + timedelta(hours=2)).isoformat()
    saved['plan_sha256'] = digest(dict(saved, plan_sha256=''))
    assert 'PLAN_VALIDITY_EXCEEDS_EVIDENCE' in verify_document(saved, current, NOW)
    saved['actions'] = ['anything']
    saved['plan_sha256'] = digest(dict(saved, plan_sha256=''))
    assert 'INVALID_PLAN_DOCUMENT' in verify_document(saved, current, NOW)


def test_rehashed_gate_decisions_are_recomputed_and_rejected():
    fake, report, simulator = setup_plan()
    current = plan(report, system=fake, simulator=simulator, now=NOW)
    saved = json.loads(json.dumps(asdict(current)))
    next(g for g in saved['gates'] if g['category'] == 'installation_equivalence')['status'] = 'PASS'
    saved['plan_sha256'] = digest(dict(saved, plan_sha256=''))
    assert 'PLAN_GATE_DRIFT' in verify_document(saved, current, NOW)


def test_plan_document_limit_is_separate_from_configuration_limit(tmp_path):
    reader = LocalSystem()
    path = tmp_path / 'plan.json'
    path.write_text(' ' * (MAX_FILE_BYTES + 1))
    with pytest.raises(ProbeError, match='FILE_SIZE_LIMIT'): reader.read_text(str(path))
    assert len(reader.read_plan_document(str(path))) == MAX_FILE_BYTES + 1
    path.write_text(' ' * (MAX_PLAN_BYTES + 1))
    with pytest.raises(ProbeError, match='FILE_SIZE_LIMIT'): reader.read_plan_document(str(path))
