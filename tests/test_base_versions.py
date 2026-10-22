import pytest

from conftest import FakeSystem,NOW
from webpatch.service import scan


@pytest.mark.parametrize('release,codename,source,version',[
    ('22.04','jammy','php8.1','8.1.2-1ubuntu2'),
    ('24.04','noble','php8.3','8.3.6-0maysync1')])
def test_official_base_versions_are_below_vendor_fix_without_claiming_origin(release,codename,source,version):
    fake=FakeSystem({'os':['ubuntu',release,codename],
        'packages':[[source+'-fpm',version,'amd64',source,version,'install ok installed']]})
    result=scan(fake,now=NOW)
    assert {a.version_status for a in result.assessments}=={'BELOW_VENDOR_FIX'}
    assert result.overall=='POTENTIALLY_AFFECTED' and not result.safe
    assert result.package_trust['installed'][0]['status']=='UNKNOWN'
    assert result.rule_valid_until=='2026-10-29T00:00:00+00:00'


def test_similar_unreviewed_maysync_family_remains_unknown():
    version='8.3.6-0maysync2'
    result=scan(FakeSystem({'os':['ubuntu','24.04','noble'],
        'packages':[['php8.3-fpm',version,'amd64','php8.3',version,'install ok installed']]}),now=NOW)
    assert all(a.version_status=='UNKNOWN' for a in result.assessments)
