from copy import deepcopy
from dataclasses import replace

import pytest

from conftest import NOW
from test_trust import trust_fixture,RELEASE,INDEX,DEB,EXECUTABLE
from webpatch.archive_policy import DEBIAN_KEYS,DEBIAN_KEYRING
from webpatch.service import scan
from webpatch.sources import Source,official_source,parse_sources
from webpatch.system import CommandResult,DPKG_QUERY,validate_command,PolicyError,ProbeError
from webpatch.trust import signature_command,valid_primary_signers


def fixture(codename='bookworm'):
    release,branch,version=('12','8.2','8.2.35-1~deb12u1') if codename=='bookworm' else ('13','8.4','8.4.27-1~deb13u1')
    fake=trust_fixture()
    fake.reads['/etc/os-release']=f'ID=debian\nVERSION_ID={release}\nVERSION_CODENAME={codename}\n'
    fake.reads[f'/etc/php/{branch}/fpm/php-fpm.conf']=ProbeError('FileNotFoundError')
    fake.reads[f'/etc/php/{branch}/fpm/php.ini']=ProbeError('FileNotFoundError')
    fake.dirs[f'/etc/php/{branch}/fpm/conf.d']=ProbeError('FileNotFoundError')
    fake.reads['/etc/apt/sources.list']=f'deb [signed-by={DEBIAN_KEYRING}] https://deb.debian.org/debian-security {codename}-security main\n'
    new_release=f'/var/lib/apt/lists/deb.debian.org_debian-security_dists_{codename}-security_InRelease'
    new_index=new_release.removesuffix('_InRelease')+'_main_binary-amd64_Packages.lz4'
    raw=fake.reads.pop(RELEASE).replace('Origin: Ubuntu','Origin: Debian').replace('Label: Ubuntu','Label: Debian-Security')
    raw=raw.replace('Suite: jammy-security','Suite: '+DEBIAN_KEYS[codename]['suite']+'-security').replace('Codename: jammy','Codename: '+codename+'-security')
    fake.reads[new_release]=raw; fake.indexes[new_index]=fake.indexes.pop(INDEX)
    record=fake.indexes[new_index]['packages'][0]
    record.update(Package='php'+branch+'-fpm',Version=version,Source='php'+branch,Filename=f'pool/main/p/php{branch}/php{branch}-fpm_{version}_amd64.deb')
    fake.dirs['/var/lib/apt/lists']=[new_release.rsplit('/',1)[1],new_index.rsplit('/',1)[1]]
    archive=fake.archives.pop(DEB)
    archive['control'].update(Package='php'+branch+'-fpm',Version=version,Source='php'+branch)
    image='/usr/sbin/php-fpm'+branch
    archive['files']={image:'c'*64}; fake.fingerprints[image]=fake.fingerprints[EXECUTABLE].copy()
    new_deb='/var/cache/apt/archives/'+f'php{branch}-fpm_{version}_amd64.deb'
    fake.archives[new_deb]=archive; fake.fingerprints[new_deb]=fake.fingerprints.pop(DEB)
    fake.dirs['/var/cache/apt/archives']=[new_deb.rsplit('/',1)[1]]
    fake.commands[DPKG_QUERY]=CommandResult(0,f'php{branch}-fpm\t{version}\tamd64\tphp{branch}\t{version}\tinstall ok installed\n')
    fake.commands[('/usr/bin/dpkg','--compare-versions',version,'ge',version)]=CommandResult(0)
    primary=DEBIAN_KEYS[codename]['security']
    fake.commands[signature_command(new_release,'debian')]=CommandResult(0,f'[GNUPG:] VALIDSIG {"A"*40} 2026-10-22 1792627200 0 4 0 1 10 01 {primary}\n')
    return fake,new_release


@pytest.mark.parametrize('codename',['bookworm','trixie'])
def test_debian_security_primary_key_and_release_identity_are_independent(codename):
    fake,path=fixture(codename); report=scan(fake,now=NOW)
    assert report.apt_sources['status']=='POLICY_CHECKED_NOT_AUTHENTICATED'
    assert report.package_trust['status']=='VERIFIED_INDEX_CHAIN',report.package_trust['blockers']
    assert report.package_trust['installed'][0]['status']=='AUTHENTICATED_RUNTIME_FILES'
    assert {c['signer'] for c in report.package_trust['candidates']}=={DEBIAN_KEYS[codename]['security']}
    assert not report.safe


@pytest.mark.parametrize('mutation',['wrong-key-role','wrong-codename','wrong-label','testing-suite','missing-expiry','expired','tampered'])
def test_debian_scope_key_and_freshness_fail_closed(mutation):
    fake,path=fixture(); command=signature_command(path,'debian')
    if mutation=='wrong-key-role': fake.commands[command]=replace(fake.commands[command],stdout=fake.commands[command].stdout.replace(DEBIAN_KEYS['bookworm']['security'],DEBIAN_KEYS['bookworm']['archive']))
    if mutation=='wrong-codename': fake.reads[path]=fake.reads[path].replace('Codename: bookworm-security','Codename: trixie-security')
    if mutation=='wrong-label': fake.reads[path]=fake.reads[path].replace('Label: Debian-Security','Label: Debian')
    if mutation=='testing-suite': fake.reads[path]=fake.reads[path].replace('Suite: oldstable-security','Suite: testing')
    if mutation=='missing-expiry': fake.reads[path]='\n'.join(l for l in fake.reads[path].splitlines() if not l.startswith('Valid-Until:'))+'\n'
    if mutation=='expired': fake.reads[path]=fake.reads[path].replace('Valid-Until: Thu, 29','Valid-Until: Thu, 22')
    if mutation=='tampered': fake.commands[command]=CommandResult(1,'[GNUPG:] BADSIG fixture')
    report=scan(fake,now=NOW)
    assert report.package_trust['status']=='UNKNOWN' and not report.safe


@pytest.mark.parametrize('uri,suite,key',[
    ('https://deb.debian.org.evil.invalid/debian-security','bookworm-security',DEBIAN_KEYRING),
    ('https://deb.debian.org/debian','stable',DEBIAN_KEYRING),
    ('https://security.debian.org/debian-security','trixie-security',DEBIAN_KEYRING),
    ('https://deb.debian.org/debian-security','bookworm-security','/tmp/key.gpg')])
def test_debian_source_aliases_mixed_releases_and_unreviewed_keys_are_rejected(uri,suite,key):
    assert not official_source(Source(uri,suite,('main',),key,'fixture.sources'),'bookworm','debian')


def test_debian_keyring_command_is_fixed_and_parser_uses_the_vendor_default():
    row=parse_sources('deb https://deb.debian.org/debian bookworm main','debian.list',DEBIAN_KEYRING)[0]
    assert row.signed_by==DEBIAN_KEYRING and official_source(row,'bookworm','debian')
    command=signature_command('/var/lib/apt/lists/deb.debian.org_debian_dists_bookworm_InRelease','debian')
    validate_command(command)
    with pytest.raises(PolicyError): validate_command((*command[:3],'/tmp/unreviewed.gpg',command[-1]))
