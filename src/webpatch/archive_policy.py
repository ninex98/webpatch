"""Reviewed distribution archive boundaries, independent of CVE version rules."""
UBUNTU_KEYRING='/usr/share/keyrings/ubuntu-archive-keyring.gpg'
DEBIAN_KEYRING='/usr/share/keyrings/debian-archive-keyring.gpg'
DEBIAN_KEYRING_PGP='/usr/share/keyrings/debian-archive-keyring.pgp'
UBUNTU_SIGNER='F6ECB3762474EDA9D21B7022871920D1991BC93C'
REVIEWED_AT='2026-10-22T22:49:54+00:00'
REFERENCES=('https://ftp-master.debian.org/keys.html',
            'https://www.debian.org/security/faq',
            'https://lists.debian.org/debian-devel-announce/2023/03/msg00001.html',
            'https://lists.debian.org/debian-devel-announce/2025/04/msg00001.html')
DEBIAN_KEYS={
    'bookworm':{'archive':'B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8',
                'security':'05AB90340C0C5E797F44A8C8254CF3B5AEC0A8F0',
                'release':'4D64FEC119C2029067D6E791F8D2585B8783D481','suite':'oldstable'},
    'trixie':{'archive':'04B54C3CDCA79751B16BC6B5225629DF75B188BD',
              'security':'5E04A1E3223A19A20706E20F9904613D4CCE68C6',
              'release':'41587F7DB8C774BCCF131416762F67A0B2C39DE4','suite':'stable'},
}


def supported_archive(os_id,codename):
    return (os_id=='ubuntu' and codename in {'jammy','noble'}) or (os_id=='debian' and codename in DEBIAN_KEYS)


def archive_keyring(os_id):
    if os_id=='ubuntu': return UBUNTU_KEYRING
    if os_id=='debian': return DEBIAN_KEYRING
    raise ValueError('ARCHIVE_VENDOR_UNSUPPORTED')


def archive_keyrings(os_id):
    return {DEBIAN_KEYRING,DEBIAN_KEYRING_PGP} if os_id=='debian' else {archive_keyring(os_id)}


def release_policy(os_id,codename,suite):
    if not supported_archive(os_id,codename) or suite not in {codename,codename+'-updates',codename+'-security'}:
        raise ValueError('ARCHIVE_SCOPE_UNSUPPORTED')
    if os_id=='ubuntu':
        return {'origin':'Ubuntu','label':'Ubuntu','suite':suite,'codename':codename,
                'signers':{UBUNTU_SIGNER},'valid_until_required':False}
    keys=DEBIAN_KEYS[codename]; suffix=suite[len(codename):]
    security=suffix=='-security'
    return {'origin':'Debian','label':'Debian-Security' if security else 'Debian',
            'suite':keys['suite']+suffix,'codename':suite,
            'signers':{keys['security']} if security else ({keys['archive'],keys['release']} if not suffix else {keys['archive']}),
            'valid_until_required':security or (codename=='trixie' and bool(suffix))}
