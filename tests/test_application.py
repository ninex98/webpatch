from dataclasses import replace
from datetime import timedelta
import hashlib
import json

import pytest

from conftest import NOW
from test_runtime_evidence import connected_fixture
from webpatch.application import (ProbeExchange, probe_source, target_url,
    collect_application_evidence, validate_exchange, LocalApplicationProbe)
from webpatch.service import scan
from webpatch.system import ProbeError
from webpatch.cli import main

URL = 'http://127.0.0.1:18080/webpatch-proof.php'
SCRIPT = '/var/www/html/webpatch-proof.php'
SERVICE = 'php8.1-fpm.service'


def fixture():
    fake = connected_fixture()
    fake.reads['/etc/php/8.1/fpm/php.ini'] = '; fixture config\n'
    fake.dirs['/etc/php/8.1/fpm/conf.d'] = []
    return fake, scan(fake, now=NOW)


class FakeProbe:
    def __init__(self, mutation=None, callback=None):
        self.calls = []
        self.mutation, self.callback = mutation, callback

    def collect(self, url, script_path, challenge, scope):
        self.calls.append((url, script_path))
        source = hashlib.sha256(probe_source()).hexdigest()
        payload = {'protocol': 3, 'challenge': challenge, 'scope': scope, 'pid': 42,
                   'sapi': 'fpm-fcgi', 'script': script_path, 'source_sha256': source,
                   'ini_file': '/etc/php/8.1/fpm/php.ini', 'ini_scanned': [],
                   'effective_ini_sha256': '1' * 64, 'extensions_sha256': '2' * 64,
                   'effective_ini_baseline_sha256':'1'*64,'reviewed_directives':{'memory_hard_limit_percent':{'state':'ABSENT'},'max_multipart_body_parts':{'state':'ABSENT'}},
                   'cached_script': False, 'request_path': '/webpatch-proof.php'}
        if self.mutation == 'nonce': payload['challenge'] = '3' * 64
        if self.mutation == 'scope': payload['scope'] = '3' * 64
        if self.mutation == 'pid': payload['pid'] = 99
        if self.mutation == 'sapi': payload['sapi'] = 'cli'
        if self.mutation == 'script': payload['script'] = '/tmp/untrusted.php'
        if self.mutation == 'cached': payload['cached_script'] = True
        if self.mutation == 'path': payload['request_path'] = '/other.php'
        if self.mutation == 'config': payload['ini_file'] = '/opt/custom/php.ini'
        if self.mutation == 'unobserved': payload['ini_scanned'] = ['/etc/php/8.1/fpm/conf.d/unknown.ini']
        if self.mutation == 'unknown-field': payload['safe'] = True
        if self.mutation == 'old-protocol': payload['protocol']=1
        if self.mutation == 'unknown-directive': payload['reviewed_directives']['memory_hard_limit_percent']={'state':'UNKNOWN'}
        data = json.dumps(payload).encode()
        response = json.dumps({'challenge': challenge, 'payload_sha256': hashlib.sha256(data).hexdigest()}).encode()
        if self.mutation == 'ordinary-response': response = b'{"ok":true,"pid":42}'
        if self.mutation == 'response-digest': response = json.dumps({'challenge':challenge, 'payload_sha256':'f'*64}).encode()
        if self.callback: self.callback()
        return ProbeExchange(data, response, 99 if self.mutation == 'kernel-pid' else 42,
                             33, 33, source if self.mutation != 'source' else 'f' * 64)


def test_explicit_probe_binds_kernel_process_response_without_inventing_loaded_file_proof():
    fake, report = fixture()
    result = collect_application_evidence(report, system=fake, probe=FakeProbe(), url=URL,
                                          script_path=SCRIPT, service=SERVICE, now=NOW)
    assert result['status'] == 'VERIFIED_PROCESS_RESPONSE'
    assert result['peer_pid'] == 42 and result['runtime_id'].endswith(':42:123')
    assert result['configuration_status'] == 'OBSERVED_EFFECTIVE_PHP_SETTINGS'
    assert result['loaded_configuration_file_bytes'] == 'UNKNOWN' and not result['executable']
    assert result['expires_at'] == (NOW + timedelta(minutes=5)).isoformat()
    assert all(e['id'].startswith('a') for e in result['evidence'])


@pytest.mark.parametrize('mutation', ['nonce','scope','pid','sapi','script','cached','path','config','unobserved',
                                     'unknown-field','ordinary-response','response-digest','kernel-pid','source','old-protocol','unknown-directive'])
def test_app_claims_cannot_replace_challenge_kernel_identity_or_input_evidence(mutation):
    fake, report = fixture()
    result = collect_application_evidence(report, system=fake, probe=FakeProbe(mutation), url=URL,
                                          script_path=SCRIPT, service=SERVICE, now=NOW)
    assert result['status'] == 'BLOCKED' and result['blockers'] and not result['executable']


@pytest.mark.parametrize('url', ['https://127.0.0.1:80/x.php','http://example.com:80/x.php',
    'http://127.0.0.1.evil:80/x.php','http://u:p@127.0.0.1:80/x.php','http://127.0.0.1/x.php',
    'http://127.0.0.1:80/x.php?secret=x','http://127.0.0.1:80/../x.php','file:///x.php'])
def test_probe_target_is_strictly_explicit_loopback(url):
    with pytest.raises(ValueError): target_url(url)


def test_process_reuse_and_config_drift_abort_without_successful_receipt():
    fake, report = fixture()
    probe = FakeProbe(callback=lambda: fake.reads.update({'/proc/42/stat': fake.reads['/proc/42/stat'].replace('123', '456')}))
    result = collect_application_evidence(report, system=fake, probe=probe, url=URL, script_path=SCRIPT, service=SERVICE, now=NOW)
    assert 'PROBE_STATE_DRIFT_AFTER_REQUEST' in result['blockers']
    probe.calls.clear()
    result = collect_application_evidence(report, system=fake, probe=probe, url=URL, script_path=SCRIPT, service=SERVICE, now=NOW)
    assert result['status'] == 'BLOCKED' and not probe.calls


def test_expiry_during_collection_and_failed_transport_remain_unknown():
    fake, report = fixture()
    ticks = iter([NOW, NOW + timedelta(minutes=6)])
    result = collect_application_evidence(report, system=fake, probe=FakeProbe(), url=URL,
                    script_path=SCRIPT, service=SERVICE, clock=lambda: next(ticks))
    assert 'PROBE_EXPIRED_DURING_COLLECTION' in result['blockers']
    class FailedProbe:
        def collect(self, *args): raise ProbeError('PROBE_TRANSPORT_FAILED:TimeoutError')
    result = collect_application_evidence(report, system=fake, probe=FailedProbe(), url=URL,
                    script_path=SCRIPT, service=SERVICE, now=NOW)
    assert result['status'] == 'BLOCKED'


def test_scan_never_calls_application_probe_and_template_never_scans(capsys):
    fake, _ = fixture()
    probe = FakeProbe()
    assert main(['scan','--format','json'], system=fake, probe=probe, now=NOW) in {1,2}
    capsys.readouterr()
    assert probe.calls == []
    fake.calls.clear()
    assert main(['probe-template'], system=fake, probe=probe) == 0
    assert capsys.readouterr().out.encode() == probe_source() and not fake.calls
    assert main(['probe-application','--url',URL,'--script',SCRIPT,'--service',SERVICE],
                system=fake, probe=probe, now=NOW) == 4
    assert json.loads(capsys.readouterr().out)['status'] == 'VERIFIED_PROCESS_RESPONSE'
