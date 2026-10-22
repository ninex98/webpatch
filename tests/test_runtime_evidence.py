from dataclasses import replace

import pytest

from conftest import NOW
from test_runtime import runtime_fixture
from test_trust import trust_fixture, EXECUTABLE
from webpatch.service import scan
from webpatch.system import CommandResult, ProbeError, DPKG_QUERY, Collector
from webpatch.planning import check_bindings, stable_bindings


def connected_fixture():
    fake = runtime_fixture()
    root = '/etc/php/8.1/fpm'
    fake.reads[root + '/php-fpm.conf'] = 'include=/etc/php/8.1/fpm/pool.d/*.conf\n'
    fake.dirs[root + '/pool.d'] = ['www.conf', 'jobs.conf']
    fake.reads[root + '/pool.d/www.conf'] = '[www]\nlisten=/run/php/php8.1-fpm.sock\n'
    fake.reads[root + '/pool.d/jobs.conf'] = '[jobs]\nlisten=/run/php/jobs.sock\n'
    fake.reads['/etc/nginx/nginx.conf'] = 'http {\nfastcgi_pass unix:/run/php/php8.1-fpm.sock;\nfastcgi_pass unix:/run/php/jobs.sock;\n}\n'
    fake.links['/proc/42/fd/9'] = 'socket:[1235]'
    fake.dirs['/proc/42/fd'].append('9')
    fake.reads['/proc/42/net/unix'] += '001: 00000002 00000000 00010000 0001 01 1235 /run/php/jobs.sock\n'
    return fake


def test_pool_socket_and_route_candidates_are_distinct_from_loaded_and_request_proof():
    result = scan(connected_fixture(), now=NOW)
    runtime = result.inventory.runtimes[0]
    assert len(runtime.endpoints) == 2
    assert len([c for c in result.inventory.coverage if c.requirement == 'configured_runtime_link' and c.status == 'OBSERVED']) == 4
    assert all(c.status == 'UNKNOWN' for c in result.inventory.coverage if c.requirement == 'loaded_configuration')
    assert all(c.status == 'NOT_CHECKED' for c in result.inventory.coverage if c.requirement == 'request_attribution')
    assert not result.safe


@pytest.mark.parametrize('failure', ['foreign-network', 'fd-permission', 'table-permission', 'not-listening', 'not-owned', 'fd-change'])
def test_unix_listener_failures_cannot_form_verified_edges(failure):
    fake = connected_fixture()
    if failure == 'foreign-network': fake.links['/proc/42/ns/net'] = 'net:[2]'
    if failure == 'fd-permission': fake.dirs['/proc/42/fd'] = ProbeError('PermissionError')
    if failure == 'table-permission': fake.reads['/proc/42/net/unix'] = ProbeError('PermissionError')
    if failure == 'not-listening': fake.reads['/proc/42/net/unix'] = fake.reads['/proc/42/net/unix'].replace('00010000', '00000000')
    if failure == 'not-owned': fake.links.update({'/proc/42/fd/8': '/dev/null', '/proc/42/fd/9': '/dev/null'})
    if failure == 'fd-change':
        read, count = fake.readlink, 0
        def changing(path):
            nonlocal count
            result = read(path)
            if path == '/proc/42/fd/8':
                count += 1
                if count > 1: return 'socket:[9999]'
            return result
        fake.readlink = changing
    result = scan(fake, now=NOW)
    assert not result.inventory.runtimes[0].endpoints
    assert all(c.status != 'VERIFIED' for c in result.inventory.coverage if c.requirement == 'process_unix_listener')


def test_authenticated_runtime_file_links_only_matching_bytes():
    fake = connected_fixture()
    trust = trust_fixture()
    for attr in ('reads', 'dirs', 'commands', 'fingerprints', 'archives', 'indexes'):
        target = getattr(fake, attr)
        for path, value in getattr(trust, attr).items():
            if path not in target or (isinstance(path, str) and path.startswith(('/etc/apt/', '/var/'))):
                target[path] = value
    fake.fingerprints[EXECUTABLE] = trust.fingerprints[EXECUTABLE]
    fake.fingerprints['/proc/42/exe'] = trust.fingerprints[EXECUTABLE]
    result = scan(fake, now=NOW)
    identities = [c for c in result.inventory.coverage if c.requirement == 'runtime_file_identity']
    assert identities and all(c.status == 'VERIFIED' for c in identities)
    fake.fingerprints['/proc/42/exe'] = dict(fake.fingerprints[EXECUTABLE], inode=900)
    result = scan(fake, now=NOW)
    assert all(c.status == 'UNKNOWN' for c in result.inventory.coverage if c.requirement == 'runtime_file_identity')


@pytest.mark.parametrize('failure', [None, 'deleted', 'inode', 'permission', 'unknown-owner', 'changed-maps'])
def test_fpm_extension_mappings_have_individual_identity_and_package_coverage(failure):
    fake = connected_fixture()
    path = '/usr/lib/php/20210902/opcache.so'
    fake.reads['/proc/42/maps'] += f'300-400 r-xp 00000000 00:01 77 {path}\n'
    fake.fingerprints[path] = {'device': 1, 'inode': 77, 'sha256': 'b' * 64}
    query = fake.commands[DPKG_QUERY]
    fake.commands[DPKG_QUERY] = replace(query, stdout=query.stdout + 'php8.1-opcache\t8.1.2-1ubuntu2.28\tamd64\tphp8.1\t8.1.2-1ubuntu2.28\tinstall ok installed\n')
    fake.commands[('/usr/bin/dpkg-query', '-S', path)] = CommandResult(0, f'php8.1-opcache: {path}\n')
    if failure == 'deleted': fake.reads['/proc/42/maps'] = fake.reads['/proc/42/maps'].rstrip() + ' (deleted)\n'
    if failure == 'inode': fake.fingerprints[path]['inode'] = 88
    if failure == 'permission': fake.fingerprints[path] = ProbeError('PermissionError')
    if failure == 'unknown-owner': fake.commands[('/usr/bin/dpkg-query', '-S', path)] = CommandResult(1)
    if failure == 'changed-maps':
        read, count = fake.read_text, 0
        def changing(path):
            nonlocal count
            raw = read(path)
            if path == '/proc/42/maps':
                count += 1
                if count > 1: return raw.replace('00:01 77', '00:01 88')
            return raw
        fake.read_text = changing
    runtime = scan(fake, now=NOW).inventory.runtimes[0]
    assert len(runtime.files) == 2
    assert (runtime.association == 'VERIFIED_LOCAL_ASSOCIATION') is (failure is None)
    if failure is None:
        assert 'php8.1-opcache:amd64' in runtime.package_ids
        assert runtime.files[1].status == 'VERIFIED_LOCAL_FILE'


@pytest.mark.parametrize('mutation', ['configuration', 'mapping', 'namespace', 'socket'])
def test_plan_rechecks_runtime_observations(mutation):
    fake = connected_fixture()
    result = scan(fake, now=NOW)
    bindings = stable_bindings(result)
    assert check_bindings(Collector(fake), bindings, result)
    if mutation == 'configuration': fake.reads['/etc/php/8.1/fpm/pool.d/www.conf'] += '\n; modified'
    if mutation == 'mapping': fake.reads['/proc/42/maps'] += '500-600 r-xp 00000000 00:01 44 /usr/lib/php/20210902/new.so\n'
    if mutation == 'namespace': fake.links['/proc/42/ns/pid'] = 'pid:[9]'
    if mutation == 'socket': fake.reads['/proc/42/net/unix'] = fake.reads['/proc/42/net/unix'].replace('00010000', '00000000')
    assert not check_bindings(Collector(fake), bindings, result)


def test_conditional_apache_handlers_and_config_changes_are_explicit_unknowns():
    fake = runtime_fixture(True)
    fake.reads['/etc/apache2/apache2.conf'] = '<IfModule php_module>\nSetHandler application/x-httpd-php\n</IfModule>\n'
    result = scan(fake, now=NOW)
    relation = result.inventory.config_relations[0]
    assert relation.constraints == ('CONDITIONAL_CONTEXT_UNRESOLVED',)
    assert all(c.status == 'UNKNOWN' for c in result.inventory.coverage if c.requirement == 'configured_runtime_link')
    read, count = fake.read_text, 0
    def changing(path):
        nonlocal count
        raw = read(path)
        if path == '/etc/apache2/apache2.conf':
            count += 1
            if count > 1: return raw + '\n# replaced'
        return raw
    fake.read_text = changing
    result = scan(fake, now=NOW)
    assert 'CONFIG_CHANGED_DURING_SCAN:/etc/apache2/apache2.conf' in result.inventory.coverage_gaps
