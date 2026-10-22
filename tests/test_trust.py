from copy import deepcopy
from datetime import timedelta

import pytest

from conftest import FakeSystem, NOW, CASES
from webpatch.service import scan
from webpatch.system import CommandResult, ProbeError, LocalSystem, PolicyError
from webpatch.trust import UBUNTU_SIGNER, verified_release, signature_command


RELEASE = "/var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_jammy-security_InRelease"
INDEX = "/var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_jammy-security_main_binary-amd64_Packages.lz4"
DEB = "/var/cache/apt/archives/php8.1-fpm_8.1.2-1ubuntu2.28_amd64.deb"
EXECUTABLE = "/usr/sbin/php-fpm8.1"


def trust_fixture():
    fake = FakeSystem(CASES[1])
    fake.reads["/etc/apt/sources.list"] = "deb https://archive.ubuntu.com/ubuntu jammy-security main"
    fake.dirs["/var/lib/apt/lists"] = [RELEASE.rsplit("/", 1)[1], INDEX.rsplit("/", 1)[1]]
    fake.reads[RELEASE] = ("-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\nOrigin: Ubuntu\nLabel: Ubuntu\nSuite: jammy-security\nCodename: jammy\nDate: Thu, 22 Oct 2026 00:00:00 UTC\nValid-Until: Thu, 29 Oct 2026 00:00:00 UTC\nSHA256:\n " + "a" * 64 + " 123 main/binary-amd64/Packages\n-----BEGIN PGP SIGNATURE-----\nfixture-only\n")
    fake.commands[signature_command(RELEASE)] = CommandResult(0, "[GNUPG:] VALIDSIG " + UBUNTU_SIGNER + " fixture\n")
    control = {"Package": "php8.1-fpm", "Version": "8.1.2-1ubuntu2.28", "Architecture": "amd64", "Source": "php8.1"}
    fake.indexes[INDEX] = {"sha256": "a" * 64, "size": 123, "packages": [dict(control, SHA256="b" * 64, Size="456", Filename="pool/main/p/php8.1/php8.1-fpm_8.1.2-1ubuntu2.28_amd64.deb")]}
    fake.dirs["/var/cache/apt/archives"] = [DEB.rsplit("/", 1)[1]]
    fake.fingerprints[DEB] = {"sha256": "b" * 64, "size": 456, "device": 1, "inode": 3}
    fake.archives[DEB] = {"control": control, "files": {EXECUTABLE: "c" * 64}, "archive_sha256": "b"*64}
    fake.fingerprints[EXECUTABLE] = {"sha256": "c" * 64, "size": 1234, "device": 1, "inode": 4}
    return fake


def test_verified_chain_is_distinct_from_runtime_safety():
    result = scan(trust_fixture(), now=NOW)
    assert result.package_trust['status'] == 'VERIFIED_INDEX_CHAIN'
    assert result.package_trust['installed'][0]['status'] == 'AUTHENTICATED_RUNTIME_FILES'
    assert result.safe is False and result.assessments[0].runtime_status == 'UNKNOWN'


@pytest.mark.parametrize("mutation", ["bad-signature", "unknown-signer", "expired-key", "wrong-origin", "wrong-suite", "old-date", "future-date", "expired-release", "hash", "size", "missing-index", "missing-release"])
def test_broken_signed_chain_is_unknown(mutation):
    fake = trust_fixture()
    if mutation == "bad-signature": fake.commands[signature_command(RELEASE)] = CommandResult(1, "[GNUPG:] BADSIG x")
    if mutation == "unknown-signer": fake.commands[signature_command(RELEASE)] = CommandResult(0, "[GNUPG:] VALIDSIG " + "0" * 40 + " fixture")
    if mutation == "expired-key": fake.commands[signature_command(RELEASE)] = CommandResult(0, "[GNUPG:] EXPKEYSIG x\n[GNUPG:] VALIDSIG " + UBUNTU_SIGNER + " fixture")
    if mutation == "wrong-origin": fake.reads[RELEASE] = fake.reads[RELEASE].replace("Origin: Ubuntu", "Origin: Forged")
    if mutation == "wrong-suite": fake.reads[RELEASE] = fake.reads[RELEASE].replace("Suite: jammy-security", "Suite: noble-security")
    if mutation == "old-date": fake.reads[RELEASE] = fake.reads[RELEASE].replace("Date: Thu, 22", "Date: Wed, 14")
    if mutation == "future-date": fake.reads[RELEASE] = fake.reads[RELEASE].replace("Date: Thu, 22", "Date: Fri, 23")
    if mutation == "expired-release": fake.reads[RELEASE] = fake.reads[RELEASE].replace("Valid-Until: Thu, 29", "Valid-Until: Thu, 22")
    if mutation == "hash": fake.indexes[INDEX]['sha256'] = 'd' * 64
    if mutation == "size": fake.indexes[INDEX]['size'] = 124
    if mutation == "missing-index": fake.dirs['/var/lib/apt/lists'] = []
    if mutation == "missing-release": fake.reads[RELEASE] = ProbeError('PermissionError')
    result = scan(fake, now=NOW).package_trust
    assert result['status'] == 'UNKNOWN'
    assert result['installed'][0]['status'] == 'UNKNOWN'


@pytest.mark.parametrize("mutation", ["archive-bytes", "archive-size", "control", "source", "installed-file", "missing-cache", "unreadable-file", "conflicting-index"])
def test_version_match_cannot_authenticate_installed_bytes(mutation):
    fake = trust_fixture()
    if mutation == 'archive-bytes': fake.fingerprints[DEB]['sha256'] = 'd' * 64
    if mutation == 'archive-size': fake.fingerprints[DEB]['size'] += 1
    if mutation == 'control': fake.archives[DEB]['control']['Architecture'] = 'arm64'
    if mutation == 'source': fake.archives[DEB]['control']['Source'] = 'fake-source'
    if mutation == 'installed-file': fake.fingerprints[EXECUTABLE]['sha256'] = 'd' * 64
    if mutation == 'missing-cache': fake.dirs['/var/cache/apt/archives'] = []
    if mutation == 'unreadable-file': fake.fingerprints[EXECUTABLE] = ProbeError('PermissionError')
    if mutation == 'conflicting-index':
        row = deepcopy(fake.indexes[INDEX]['packages'][0]); row['SHA256'] = 'd' * 64
        fake.indexes[INDEX]['packages'].append(row)
    assert scan(fake, now=NOW).package_trust['installed'][0]['status'] == 'UNKNOWN'


def test_release_swap_during_gpgv_is_rejected():
    fake = trust_fixture()
    run = fake.run
    def swap(argv):
        result = run(argv)
        if argv == signature_command(RELEASE): fake.reads[RELEASE] += '\n'
        return result
    fake.run = swap
    assert 'RELEASE_CHANGED_DURING_VERIFICATION' in scan(fake, now=NOW).package_trust['blockers']


@pytest.mark.parametrize('argv', [
    ('/usr/bin/gpgv', '--keyring', '/tmp/evil', RELEASE),
    ('/usr/bin/dpkg-deb', '--extract', DEB),
    ('/usr/lib/apt/apt-helper', 'download-file', 'https://example.com'),
    ('/usr/bin/dpkg-deb', '--fsys-tarfile', '/var/cache/../secret.deb'),
])
def test_crypto_command_boundary(argv):
    with pytest.raises(PolicyError): LocalSystem().run(argv)
