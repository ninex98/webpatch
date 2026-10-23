from dataclasses import replace

import pytest

from conftest import NOW
from test_debian_trust import fixture
from test_planning import FakeSimulator
from webpatch.planning import plan,choose_targets
from webpatch.preparation import configuration_roots
from webpatch.profiles import php_source_profile
from webpatch.service import scan
from webpatch.system import ProbeError,CommandResult,Collector


@pytest.mark.parametrize('codename,branch',[('bookworm','8.2'),('trixie','8.4')])
def test_debian_profiles_select_exact_branch_and_independent_vendor_simulation(codename,branch):
    fake,_=fixture(codename)
    fake.reads['/proc/locks']=''
    for path in ('/var/lib/dpkg/lock','/var/lib/dpkg/lock-frontend','/var/lib/apt/lists/lock','/var/cache/apt/archives/lock'):
        fake.identities[path]=ProbeError('FileNotFoundError')
    report=scan(fake,now=NOW)
    assert php_source_profile(report.inventory.environment)=='php'+branch
    assert configuration_roots(report,'php'+branch+'-fpm.service')==(f'/etc/php/{branch}/fpm',)
    result=plan(report,system=fake,simulator=FakeSimulator(),now=NOW)
    assert result.apt_simulation=='PASS'
    assert 'APT_PLANNING_UNSUPPORTED_RELEASE' not in result.blockers
    assert result.admission_status=='BLOCKED' and not result.executable
    with pytest.raises(ValueError): configuration_roots(report,'php9.9-fpm.service')


def test_mixed_distribution_identity_cannot_select_a_service_profile():
    fake,_=fixture();report=scan(fake,now=NOW)
    report.inventory.environment=replace(report.inventory.environment,version_id='13')
    assert php_source_profile(report.inventory.environment) is None
    with pytest.raises(ValueError,match='RELEASE_UNSUPPORTED'): configuration_roots(report,'php8.2-fpm.service')


def test_debian_binary_rebuild_uses_source_version_for_cve_boundary():
    fake,_=fixture();report=scan(fake,now=NOW)
    candidate=report.package_trust['candidates'][0]
    candidate['version']=candidate['source_version']+'+b1'
    fake.commands[('/usr/bin/dpkg','--compare-versions',candidate['version'],'ge',candidate['source_version'])]=CommandResult(0)
    targets,blockers=choose_targets(report,Collector(fake),NOW)
    assert not blockers and targets[0].version.endswith('+b1')
