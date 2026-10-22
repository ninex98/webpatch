from dataclasses import asdict

import pytest

from conftest import FakeSystem, NOW
from webpatch.service import scan
from webpatch.sources import KEYRING, parse_sources, official_source


def configured(deb822=False):
    fake = FakeSystem({})
    if deb822:
        fake.dirs["/etc/apt/sources.list.d"] = ["ubuntu.sources"]
        fake.reads["/etc/apt/sources.list.d/ubuntu.sources"] = f"Types: deb\nURIs: https://archive.ubuntu.com/ubuntu\nSuites: jammy jammy-security jammy-updates\nComponents: main universe\nSigned-By: {KEYRING}\n"
    else:
        fake.reads["/etc/apt/sources.list"] = f"deb [signed-by={KEYRING}] https://archive.ubuntu.com/ubuntu jammy-security main universe\n"
    return fake


@pytest.mark.parametrize("deb822", [True, False])
def test_source_policy_never_authenticates_package(deb822):
    result = scan(configured(deb822), now=NOW)
    assert result.apt_sources['status'] == "POLICY_CHECKED_NOT_AUTHENTICATED"
    assert result.apt_sources['blockers'] == ()
    assert not result.safe


@pytest.mark.parametrize("value", [
    "deb [trusted=yes] http://archive.ubuntu.com/ubuntu jammy-security main",
    "deb [check-valid-until=no] http://archive.ubuntu.com/ubuntu jammy-security main",
    "deb [signed-by=/tmp/forged.gpg] http://archive.ubuntu.com/ubuntu jammy-security main",
    "deb http://ppa.launchpad.net/example/php/ubuntu jammy main",
    "deb mirror+file:/etc/apt/apt-mirrors.txt jammy-security main",
    "deb http://archive.ubuntu.com/ubuntu noble-security main",
    "deb http://archive.ubuntu.com.evil.example/ubuntu jammy-security main",
    "deb http://archive.ubuntu.com/ubuntu jammy-backports main",
    "garbage source",
])
def test_source_anomalies_block(value):
    fake = configured()
    fake.reads["/etc/apt/sources.list"] = value
    assert scan(fake, now=NOW).apt_sources['status'] == 'UNKNOWN'


@pytest.mark.parametrize("text", [
    "Types: deb\nTypes: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: jammy-security\nComponents: main",
    "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: jammy-security\nComponents: main\nTrusted: yes",
    "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\nComponents: main",
])
def test_deb822_rejects_duplicates_and_bypass_options(text):
    with pytest.raises(ValueError):
        parse_sources(text, "ubuntu.sources")


@pytest.mark.parametrize("path,text,blocker", [
    ("/etc/apt/preferences", "Package: *\nPin: release a=noble\nPin-Priority: 1001", "APT_PIN_REQUIRES_REVIEW"),
    ("/etc/apt/apt.conf", 'DPkg::Post-Invoke { "echo fixture"; };', "APT_HOOKS_REQUIRE_REVIEW"),
    ("/etc/apt/apt.conf", 'Dir::State::status "/tmp/status";', "APT_CONFIGURATION_OVERRIDE_REQUIRES_REVIEW"),
    ("/etc/apt/apt.conf", '#include "/tmp/other";', "APT_CONFIGURATION_OVERRIDE_REQUIRES_REVIEW"),
])
def test_pin_hook_and_path_override_require_review(path, text, blocker):
    fake = configured()
    fake.reads[path] = text
    assert blocker in scan(fake, now=NOW).apt_sources['blockers']


def test_repository_credentials_are_not_in_report():
    fake = configured()
    fake.reads["/etc/apt/sources.list"] = "deb https://user:very-secret@archive.ubuntu.com/ubuntu jammy-security main"
    assert "very-secret" not in str(asdict(scan(fake, now=NOW)))


def test_hold_in_non_php_dependency_is_actionable():
    from webpatch.system import DPKG_QUERY, CommandResult
    fake = configured()
    fake.commands[DPKG_QUERY] = CommandResult(0, "libc6\t2.35\tamd64\tglibc\t2.35\thold ok installed\n")
    assert "HELD_PACKAGES_REQUIRE_REVIEW" in scan(fake, now=NOW).apt_sources['blockers']
