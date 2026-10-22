from copy import deepcopy
from datetime import timedelta
import json
import subprocess
import sys

import pytest

from webpatch.cli import main
from webpatch.discovery import discover
from webpatch.rules import RuleEngine
from webpatch.service import scan
from webpatch.system import (Collector, CommandResult, DPKG_QUERY, LocalSystem,
                             PolicyError, ProbeError)
from conftest import CASES, FakeSystem, NOW


@pytest.mark.parametrize("argv", [
    ("apt-get", "update"), ("/usr/bin/apt-get", "-s", "install", "php8.1-fpm"),
    ("/usr/bin/dpkg", "--install", "file.deb"), ("php", "-v"),
    ("systemctl", "restart", "apache2"), ("/bin/sh", "-c", "true"),
    ("/usr/bin/dpkg-query", "-W"),
    ("/usr/bin/dpkg", "--compare-versions", "--help", "ge", "1"),
    ("/usr/bin/dpkg", "--compare-versions", "1;touch /tmp/x", "ge", "1"),
    ("/usr/bin/dpkg", "--compare-versions", "", "ge", "1"),
])
def test_command_boundary_rejects_even_simulation_in_phase_one(argv, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Command reached OS"))
    with pytest.raises(PolicyError):
        LocalSystem().run(argv)


def test_fixed_command_environment_and_missing_executable(monkeypatch):
    def missing(argv, **kwargs):
        assert argv == DPKG_QUERY
        assert kwargs["shell"] is False
        assert kwargs["cwd"] == "/"
        assert kwargs["env"]["LC_ALL"] == "C"
        assert "DPKG_ROOT" not in kwargs["env"]
        assert "LD_PRELOAD" not in kwargs["env"]
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "Popen", missing)
    with pytest.raises(ProbeError, match="FileNotFoundError"):
        LocalSystem().run(DPKG_QUERY)


@pytest.mark.parametrize("code,limit,timeout,expected", [
    ("print('fixture-output')", 4096, 5, None),
    ("print('x' * 8192)", 1024, 5, "COMMAND_OUTPUT_LIMIT"),
    ("import time; time.sleep(10)", 4096, 0.1, "COMMAND_TIMEOUT"),
])
def test_command_io_limits_with_harmless_child(monkeypatch, code, limit, timeout, expected):
    # A Python child emits fixture bytes only. No actual dpkg or host inspection.
    popen = subprocess.Popen
    def fixture_child(argv, **kwargs):
        assert argv == DPKG_QUERY
        return popen([sys.executable, "-B", "-c", code], **kwargs)
    monkeypatch.setattr(subprocess, "Popen", fixture_child)
    monkeypatch.setattr("webpatch.system.MAX_COMMAND_BYTES", limit)
    monkeypatch.setattr("webpatch.system.COMMAND_TIMEOUT_SECONDS", timeout)
    if expected:
        with pytest.raises(ProbeError, match=expected):
            LocalSystem().run(DPKG_QUERY)
    else:
        assert LocalSystem().run(DPKG_QUERY).stdout == "fixture-output\n"


def test_file_limits_and_decode_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("webpatch.system.MAX_FILE_BYTES", 8)
    path = tmp_path / "fixture"
    path.write_bytes(b"a" * 9)
    with pytest.raises(ProbeError, match="FILE_SIZE_LIMIT"):
        LocalSystem().read_text(str(path))
    path.write_bytes(b"\xff")
    with pytest.raises(ProbeError, match="UnicodeDecodeError"):
        LocalSystem().read_text(str(path))
    path.write_text("fixture")
    assert LocalSystem().read_text(str(path)) == "fixture"
    assert LocalSystem().listdir(str(tmp_path)) == ["fixture"]
    link = tmp_path / "link"
    link.symlink_to(path)
    assert LocalSystem().readlink(str(link)) == str(path)
    monkeypatch.setattr("webpatch.system.MAX_DIRECTORY_ENTRIES", 1)
    with pytest.raises(ProbeError, match="DIRECTORY_ENTRY_LIMIT"):
        LocalSystem().listdir(str(tmp_path))


def test_process_limit_marks_incomplete(monkeypatch):
    fake = FakeSystem({"processes": [{"pid": 1, "comm": "init"}, {"pid": 2, "comm": "php-fpm"}]})
    monkeypatch.setattr("webpatch.discovery.MAX_PROCESSES", 1)
    assert "PROCESS_LIMIT_REACHED" in scan(fake, now=NOW).inventory.coverage_gaps


def test_comparator_returncode_one_is_not_command_failure():
    fake = FakeSystem(CASES[0])
    report = scan(fake, now=NOW)
    assert report.assessments[0].version_status == "BELOW_VENDOR_FIX"
    assert any(e.outcome == "EXIT_1" for e in report.evidence)


def test_cve_rules_are_independent():
    data = deepcopy(RuleEngine().data)
    data["rules"][0]["fixes"]["CVE-2026-109619"] = "8.1.2-1ubuntu2.29"
    fake = FakeSystem(CASES[1])
    fake.commands[("/usr/bin/dpkg", "--compare-versions", "8.1.2-1ubuntu2.28", "ge",
                   "8.1.2-1ubuntu2.29")] = CommandResult(1)
    report = scan(fake, now=NOW, rules=RuleEngine(json.dumps(data).encode()))
    assert [a.version_status for a in report.assessments] == ["MEETS_VENDOR_FIX", "BELOW_VENDOR_FIX"]


def test_rule_expiry_has_exact_boundary():
    rules = RuleEngine()
    before = scan(FakeSystem(CASES[1]), now=rules.expires - timedelta(microseconds=1))
    after = scan(FakeSystem(CASES[1]), now=rules.expires)
    assert before.assessments[0].version_status == "MEETS_VENDOR_FIX"
    assert after.assessments[0].version_status == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["duplicate", "schema", "fix", "date"])
def test_invalid_rule_bundle_fails_closed(mutation):
    data = deepcopy(RuleEngine().data)
    if mutation == "duplicate":
        data["rules"].append(data["rules"][0])
    elif mutation == "schema":
        data["schema_version"] = 999
    elif mutation == "fix":
        data["rules"][0]["fixes"]["CVE-2026-109618"] = ""
    else:
        data["valid_until"] = "2020-01-01T00:00:00"
    with pytest.raises(ValueError):
        RuleEngine(json.dumps(data).encode())


def test_custom_adapter_can_supply_inventory_without_changing_rules():
    class InventoryOnlyAdapter:
        name = "example-runtime"
        def supports(self, environment):
            return True
        def discover(self, collector, inventory):
            inventory.coverage_gaps.append("EXAMPLE_UNSUPPORTED_RUNTIME")
    inventory = discover(Collector(FakeSystem({})), (InventoryOnlyAdapter(),))
    assert inventory.adapters == ["example-runtime"]
    assert "EXAMPLE_UNSUPPORTED_RUNTIME" in inventory.coverage_gaps


def test_rule_provider_does_not_require_php_rule_storage():
    class DifferentRuntimeRules:
        revision = "test-only-runtime-provider"
        sha256 = "0" * 64
        reviewed = NOW - timedelta(days=1)
        expires = NOW + timedelta(days=1)
        def assess(self, inventory, comparator, now):
            assert now == NOW
            return []
    report = scan(FakeSystem({}), now=NOW, rules=DifferentRuntimeRules(), adapters=())
    assert report.rule_revision == "test-only-runtime-provider"
    assert report.overall == "UNKNOWN"
    assert report.safe is False


def test_fixture_has_no_implicit_io_fallback():
    with pytest.raises(AssertionError, match="Undeclared"):
        FakeSystem({}).read_text("/unplanned-path")


def test_cli_default_and_advisory_text(capsys):
    assert main([], system=FakeSystem({}), now=NOW) == 2
    assert "UNKNOWN" in capsys.readouterr().out
    assert main(["plan", "--dry-run"], system=FakeSystem(CASES[0]), now=NOW) == 4
    assert "NOT_RUN" in capsys.readouterr().out


def test_cli_has_no_yes_or_shell_escape(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["apply", "--yes"], system=FakeSystem({}), now=NOW)
    assert exc.value.code == 2


def test_cli_rule_load_failure_is_not_safe(monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise ValueError("invalid rule bundle")
    monkeypatch.setattr("webpatch.cli.scan", broken)
    assert main(["scan"], system=FakeSystem({}), now=NOW) == 3
    assert "safety is UNKNOWN" in capsys.readouterr().err


def test_renamed_or_replaced_binary_never_gets_runtime_verdict():
    report = scan(FakeSystem(CASES[1]), now=NOW)
    # No provenance claim even when a local package imitates an official version.
    assert report.inventory.packages[0].provenance == "UNVERIFIED_LOCAL_METADATA"
    assert report.safe is False
    assert report.assessments[0].runtime_status == "UNKNOWN"


def test_architecture_qualifier_mismatch_is_unknown():
    case = deepcopy(CASES[1])
    case["packages"][0][0] = "php8.1-fpm:arm64"
    report = scan(FakeSystem(case), now=NOW)
    assert report.assessments[0].version_status == "UNKNOWN"


def test_text_output_escapes_untrusted_terminal_sequences(capsys):
    fake = FakeSystem({})
    fake.reads["/etc/os-release"] = 'ID="evil\x1b[31m"\nVERSION_ID="x"\n'
    assert main([], system=fake, now=NOW) == 2
    assert "\x1b" not in capsys.readouterr().out
