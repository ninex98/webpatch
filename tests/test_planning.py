from dataclasses import FrozenInstanceError, replace, asdict
from datetime import timedelta
from pathlib import Path
import json
import subprocess
import sys

import pytest

from conftest import NOW
from test_trust import trust_fixture, INDEX
from webpatch.apt import SimulationResult, simulation_command, LocalAptSimulator
from webpatch.planning import plan, validate_plan, parse_simulation, dependency_blockers, verify_document
from webpatch.models import PackageChange, PackageTarget
from webpatch.service import scan
from webpatch.system import CommandResult, ProbeError, Collector, DPKG_QUERY


NO_CHANGE = "Reading package lists...\n0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n"
UPGRADE = "1 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\nInst php8.1-fpm [8.1.2-1ubuntu2.27] (8.1.2-1ubuntu2.28 Ubuntu:22.04/jammy-security [amd64])\nConf php8.1-fpm (8.1.2-1ubuntu2.28 Ubuntu:22.04/jammy-security [amd64])\n"


class FakeSimulator:
    def __init__(self, stdout=NO_CHANGE, rc=0, stderr="", callback=None):
        self.result = CommandResult(rc, stdout, stderr)
        self.calls = []
        self.callback = callback

    def simulate(self, targets):
        self.calls.append(targets)
        if self.callback: self.callback()
        return SimulationResult(simulation_command(targets), self.result, True)


def setup_plan():
    fake = trust_fixture()
    fake.reads['/proc/locks'] = ''
    for path in ('/var/lib/dpkg/lock', '/var/lib/dpkg/lock-frontend', '/var/lib/apt/lists/lock', '/var/cache/apt/archives/lock'):
        fake.identities[path] = ProbeError('FileNotFoundError')
    return fake, scan(fake, now=NOW), FakeSimulator()


def test_successful_simulation_is_immutable_and_still_not_executable():
    fake, report, simulator = setup_plan()
    result = plan(report, system=fake, simulator=simulator, now=NOW)
    assert result.apt_simulation == 'PASS'
    assert result.status == 'BLOCKED' and not result.executable
    assert result.targets[0].version == '8.1.2-1ubuntu2.28'
    assert result.changes == ()
    assert result.expires_at == (NOW + timedelta(minutes=30)).isoformat()
    assert len(result.plan_sha256) == 64 and result.simulation_sha256
    assert any(e.operation == 'apt_simulation' for e in result.evidence)
    with pytest.raises(FrozenInstanceError): result.targets[0].version = '0'
    assert validate_plan(result, scan(fake, now=NOW), system=fake, simulator=simulator, now=NOW) == ()


@pytest.mark.parametrize('mutation', ['package', 'sources', 'rule', 'scope', 'index'])
def test_plan_binding_detects_state_drift(mutation):
    fake, report, simulator = setup_plan()
    saved = plan(report, system=fake, simulator=simulator, now=NOW)
    if mutation == 'package':
        result = fake.commands[DPKG_QUERY]
        fake.commands[DPKG_QUERY] = replace(result, stdout=result.stdout + 'libc6\t2.35\tamd64\tglibc\t2.35\tinstall ok installed\n')
    if mutation == 'sources': fake.reads['/etc/apt/sources.list'] += '\n# changed'
    if mutation == 'scope': fake.reads['/proc/sys/kernel/random/boot_id'] = 'rebooted'
    if mutation == 'index': fake.indexes[INDEX]['sha256'] = 'e' * 64
    current = scan(fake, now=NOW)
    if mutation == 'rule': current = replace(current, rule_sha256='f' * 64)
    assert 'PLAN_INPUT_STATE_DRIFT' in validate_plan(saved, current, system=fake, simulator=simulator, now=NOW)


def test_state_change_during_simulation_and_before_simulation():
    fake, report, simulator = setup_plan()
    simulator.callback = lambda: fake.reads.update({'/etc/apt/sources.list': '# changed'})
    result = plan(report, system=fake, simulator=simulator, now=NOW)
    assert 'STATE_DRIFT_DURING_SIMULATION' in result.blockers
    simulator.calls.clear()
    result = plan(report, system=fake, simulator=simulator, now=NOW)
    assert 'STATE_DRIFT_BEFORE_SIMULATION' in result.blockers and simulator.calls == []


def test_expiry_tampering_and_solver_drift():
    fake, report, simulator = setup_plan()
    saved = plan(report, system=fake, simulator=simulator, now=NOW)
    assert 'PLAN_EXPIRED_OR_CLOCK_REVERSED' in validate_plan(saved, report, system=fake, simulator=simulator, now=NOW + timedelta(minutes=30))
    assert 'PLAN_DIGEST_MISMATCH' in validate_plan(replace(saved, executable=True), report, system=fake, simulator=simulator, now=NOW)
    simulator.result = CommandResult(100, '', 'resolver failed')
    assert 'PLAN_SIMULATION_DRIFT' in validate_plan(saved, report, system=fake, simulator=simulator, now=NOW)


@pytest.mark.parametrize('result', [CommandResult(100, '', 'broken'), CommandResult(0, NO_CHANGE, 'W: incomplete'), CommandResult(0, 'unrecognized output')])
def test_simulation_failure_or_unparseable_output_never_passes(result):
    fake, report, simulator = setup_plan()
    simulator.result = result
    assert plan(report, system=fake, simulator=simulator, now=NOW).apt_simulation == 'FAIL'


def test_lock_identity_is_checked_not_file_presence():
    fake, report, simulator = setup_plan()
    fake.identities['/var/lib/dpkg/lock'] = {'device': 1, 'inode': 99}
    assert 'PACKAGE_MANAGER_LOCK_HELD' not in plan(report, system=fake, simulator=simulator, now=NOW).blockers
    fake.reads['/proc/locks'] = '1: POSIX ADVISORY WRITE 123 00:01:99 0 EOF\n'
    assert 'PACKAGE_MANAGER_LOCK_HELD' in plan(report, system=fake, simulator=simulator, now=NOW).blockers


def test_real_format_upgrade_and_full_dependency_changes():
    changes = parse_simulation(UPGRADE)
    assert changes == (PackageChange('UPGRADE', 'php8.1-fpm', 'amd64', '8.1.2-1ubuntu2.27', '8.1.2-1ubuntu2.28'),)
    fake, report, _ = setup_plan()
    target = PackageTarget('php8.1-fpm', 'amd64', '8.1.2-1ubuntu2.27', '8.1.2-1ubuntu2.28', 'b'*64)
    fake.commands[('/usr/bin/dpkg', '--compare-versions', '8.1.2-1ubuntu2.28', 'ge', '8.1.2-1ubuntu2.27')] = CommandResult(0)
    assert dependency_blockers(changes, (target,), report, Collector(fake)) == []
    extra = (*changes, PackageChange('INSTALL', 'evil', 'amd64', None, '1'), PackageChange('REMOVE', 'libc6', 'amd64', '2.35', None))
    blockers = dependency_blockers(extra, (target,), report, Collector(fake))
    assert 'UNAPPROVED_DEPENDENCY_CHANGE:evil' in blockers
    assert 'DEPENDENCY_ORIGIN_UNVERIFIED:evil' in blockers
    assert 'PACKAGE_REMOVAL_REJECTED:libc6' in blockers


@pytest.mark.parametrize('new', ['8.1.2-1ubuntu2.26', '8.3.6-0ubuntu0.24.04.13'])
def test_downgrade_and_cross_branch_solver_changes_rejected(new):
    fake, report, _ = setup_plan()
    fake.commands[('/usr/bin/dpkg', '--compare-versions', new, 'ge', '8.1.2-1ubuntu2.27')] = CommandResult(1 if new.startswith('8.1') else 0)
    target = PackageTarget('php8.1-fpm', 'amd64', '8.1.2-1ubuntu2.27', '8.1.2-1ubuntu2.28', 'b'*64)
    blockers = dependency_blockers((PackageChange('UPGRADE', target.name, target.architecture, target.installed_version, new),), (target,), report, Collector(fake))
    assert 'SIMULATION_TARGET_OR_INSTALLED_VERSION_MISMATCH:php8.1-fpm' in blockers
    assert 'DEPENDENCY_ORIGIN_UNVERIFIED:php8.1-fpm' in blockers


@pytest.mark.parametrize('output', [UPGRADE.replace('1 upgraded', '2 upgraded'), UPGRADE.replace('Conf ', 'Unknown '), UPGRADE + UPGRADE, 'Purg foo\n', UPGRADE.replace('[amd64]', '[arm64]', 1)])
def test_partial_ambiguous_or_changed_solver_output_fails_closed(output):
    with pytest.raises(ValueError): parse_simulation(output)


@pytest.mark.parametrize('targets', [(), ('--allow-unauthenticated',), ('php8.1-fpm:amd64=1;touch /tmp/x',), ('php8.1-fpm:amd64=1', 'php8.1-fpm:amd64=1'), ('php8.1-fpm=1',)])
def test_simulator_only_accepts_pinned_package_identifiers(targets):
    with pytest.raises(ProbeError): simulation_command(targets)


def test_simulator_uses_empty_hook_config_and_fixed_environment(monkeypatch):
    monkeypatch.setenv('TMPDIR', '/invalid/";hook;')
    original = subprocess.Popen
    observed = []
    def child(command, **kwargs):
        assert command[:2] == ('/usr/bin/apt-get', '--simulate')
        assert '--no-download' in command and '--no-remove' in command
        env = kwargs['env']
        assert set(env) == {'PATH', 'LC_ALL', 'LANG', 'APT_CONFIG', 'DEBIAN_FRONTEND'}
        config = Path(env['APT_CONFIG']).read_text()
        assert 'Dir::Etc::main "/dev/null"' in config and '/parts"' in config
        assert 'DPkg::Pre' not in config
        observed.append(env['APT_CONFIG'])
        return original([sys.executable, '-c', 'print("fixture-only simulation")'], **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', child)
    result = LocalAptSimulator().simulate(('php8.1-fpm:amd64=8.1.2-1ubuntu2.28',))
    assert result.result.stdout == 'fixture-only simulation\n'
    assert not Path(observed[0]).exists()


@pytest.mark.parametrize('code,limit,timeout,error', [
    ("print('x'*65536)", 1024, 5, 'APT_SIMULATION_OUTPUT_LIMIT'),
    ("import time;time.sleep(10)", 1048576, 0.1, 'APT_SIMULATION_TIMEOUT'),
])
def test_simulator_resource_limits(monkeypatch, code, limit, timeout, error):
    original = subprocess.Popen
    monkeypatch.setattr('webpatch.apt.MAX_SIMULATION_BYTES', limit)
    monkeypatch.setattr('webpatch.apt.APT_TIMEOUT_SECONDS', timeout)
    monkeypatch.setattr(subprocess, 'Popen', lambda command, **kw: original([sys.executable, '-c', code], **kw))
    with pytest.raises(ProbeError, match=error):
        LocalAptSimulator().simulate(('php8.1-fpm:amd64=8.1.2-1ubuntu2.28',))


def test_verify_saved_json_and_cli_never_runs_saved_argv(capsys):
    from webpatch.cli import main
    fake, report, simulator = setup_plan()
    saved = plan(report, system=fake, simulator=simulator, now=NOW)
    document = json.loads(json.dumps(asdict(saved)))
    assert verify_document(document, saved, NOW) == ()
    document['actions'] = ['/bin/sh -c malicious-saved-command']
    fake.reads['/reviewed-plan.json'] = json.dumps(document)
    assert main(['verify-plan', '/reviewed-plan.json'], system=fake, simulator=simulator, now=NOW) == 4
    output = json.loads(capsys.readouterr().out)
    assert 'PLAN_DIGEST_MISMATCH' in output['drift'] and not output['executable']
    assert all(not any('malicious' in str(part) for part in call) for call in fake.calls)
    assert verify_document({}, saved, NOW) == ('INVALID_PLAN_DOCUMENT',)


def test_new_runtime_blocks_simulation_before_solver():
    fake, report, simulator = setup_plan()
    fake.dirs['/proc'] = ['99']
    fake.reads['/proc/99/comm'] = 'php-fpm8.1'
    result = plan(report, system=fake, simulator=simulator, now=NOW)
    assert result.apt_simulation == 'NOT_RUN' and not simulator.calls
    assert 'STATE_DRIFT_BEFORE_SIMULATION' in result.blockers


def test_scanner_pid_and_unrelated_process_churn_do_not_invalidate_plan():
    fake, _, simulator = setup_plan()
    fake.dirs['/proc'] = ['41']
    fake.reads['/proc/41/comm'] = 'python3'
    report = scan(fake, now=NOW)
    saved = plan(report, system=fake, simulator=simulator, now=NOW)
    fake.dirs['/proc'] = ['42']
    fake.reads['/proc/42/comm'] = 'python3'
    current = scan(fake, now=NOW)
    assert validate_plan(saved, current, system=fake, simulator=simulator, now=NOW) == ()
    assert all(b.target != '/proc' for b in saved.bindings)


def test_extended_apt_state_and_diversions_are_bound():
    fake, report, simulator = setup_plan()
    saved = plan(report, system=fake, simulator=simulator, now=NOW)
    fake.reads['/var/lib/apt/extended_states'] = 'Package: php8.1-fpm\nAuto-Installed: 1\n'
    fake.reads['/var/lib/dpkg/diversions'] = '/usr/sbin/php-fpm8.1\n/opt/php/custom\nlocal\n'
    current = scan(fake, now=NOW)
    assert 'DPKG_DIVERSIONS_REQUIRE_REVIEW' in current.apt_sources['blockers']
    assert 'PLAN_INPUT_STATE_DRIFT' in validate_plan(saved, current, system=fake, simulator=simulator, now=NOW)
