import pytest

from conftest import NOW
from test_trust import trust_fixture, DEB
from webpatch.service import scan
from webpatch.system import LocalSystem, ProbeError, PolicyError, validate_command, definition_command


def test_parsed_bytes_must_match_signed_archive_even_if_path_fingerprints_match():
    fake = trust_fixture()
    fake.archives[DEB]['archive_sha256'] = 'f'*64
    result = scan(fake, now=NOW)
    assert result.package_trust['installed'][0]['status'] == 'UNKNOWN'
    assert any(e.operation=='package_archive' and e.outcome=='ARCHIVE_SNAPSHOT_SHA256_MISMATCH' for e in result.evidence)


def test_cached_archive_symlink_is_rejected_without_following_target(tmp_path):
    target = tmp_path/'private-fixture'
    target.write_bytes(b'not a package')
    link = tmp_path/'php-fixture.deb'
    link.symlink_to(target)
    with pytest.raises(ProbeError): LocalSystem().archive_fingerprint(str(link))
    assert LocalSystem().fingerprint(str(link))['size'] == 13


@pytest.mark.parametrize('archive_request', ['/tmp/a.deb', ('/tmp/a.deb',None), ('/tmp/a.deb','unverified'), ('/tmp/a.deb','0'*64,'extra')])
def test_archive_parser_requires_explicit_content_digest(archive_request):
    with pytest.raises(ProbeError,match='AUTHENTICATED_ARCHIVE_REQUEST_REQUIRED'):
        LocalSystem().package_archive(archive_request)


def test_service_definition_query_capability_does_not_allow_mutation():
    validate_command(definition_command('php8.1-fpm.service'))
    with pytest.raises(PolicyError): validate_command(('/usr/bin/systemctl','restart','php8.1-fpm.service'))
    with pytest.raises(PolicyError): validate_command(('/usr/bin/dpkg-deb','--ctrl-tarfile','/proc/self/fd/3'))
