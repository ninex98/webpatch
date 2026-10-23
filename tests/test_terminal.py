from dataclasses import replace
import io
import json

import pytest

from conftest import CASES, FakeSystem, NOW
from webpatch.cli import main
from webpatch.service import scan
from webpatch.terminal import Terminal, render_scan, width


def output(report, **options):
    stream = io.StringIO()
    render_scan(report, Terminal(stream=stream, **options))
    return stream.getvalue()


def test_empty_inventory_is_short_actionable_and_never_safe():
    text = output(scan(FakeSystem({}), now=NOW), lang='en', columns=88)
    assert 'UNKNOWN' in text and 'No PHP packages or runtime hints were found' in text
    assert 'No package repair is available' in text
    assert 'webpatch scan --details' in text
    assert len(text.splitlines()) < 32
    assert '{"' not in text and 'adapter_limit:' not in text


def test_json_output_and_exit_codes_do_not_depend_on_presentation(capsys):
    fake = FakeSystem(CASES[0])
    expected = scan(FakeSystem(CASES[0]), now=NOW)
    code = main(['scan', '--format', 'json', '--lang', 'zh', '--color', 'always'], system=fake, now=NOW)
    text = capsys.readouterr().out
    assert '\x1b' not in text
    actual = json.loads(text)
    assert actual['overall'] == expected.overall and actual['safe'] is False
    assert code == (1 if expected.overall == 'POTENTIALLY_AFFECTED' else 2)


def test_affected_packages_show_versions_and_group_duplicate_cves():
    report = scan(FakeSystem(CASES[0]), now=NOW)
    assert any(a.version_status == 'BELOW_VENDOR_FIX' for a in report.assessments)
    text = output(report, lang='en')
    assert 'potentially affected' in text and 'Vendor fix:' in text
    assert 'CVE-' in text and 'webpatch plan' in text
    assert text.count('[UPDATE NEEDED]') == len({a.package_id for a in report.assessments if a.version_status == 'BELOW_VENDOR_FIX'})


def test_details_retain_unknown_custom_gaps_and_subjects(capsys):
    fake = FakeSystem({})
    assert main(['scan', '--details'], system=fake, now=NOW) == 2
    text = capsys.readouterr().out
    assert 'discovery_completeness' in text and 'Next:' in text
    assert '{"' not in text


@pytest.mark.parametrize('lang', ['en', 'zh'])
@pytest.mark.parametrize('columns', [24, 42, 80])
def test_narrow_terminal_and_control_injection(lang, columns):
    report = scan(FakeSystem({}), now=NOW)
    report.inventory.environment = replace(report.inventory.environment, os_id='evil\x1b[31m\u202e')
    text = output(report, lang=lang, columns=columns)
    assert '\x1b' not in text and '\u202e' not in text
    assert all(width(line) <= columns for line in text.splitlines())


def test_automatic_color_respects_tty_and_no_color(monkeypatch):
    stream = io.StringIO()
    assert not Terminal(stream=stream).color
    monkeypatch.setattr(stream, 'isatty', lambda: True)
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert Terminal(stream=stream).color
    monkeypatch.setenv('NO_COLOR', '')
    assert not Terminal(stream=stream).color


def test_locale_and_expired_rules_are_visible(monkeypatch):
    monkeypatch.setenv('LC_ALL', 'zh_CN.UTF-8')
    report = scan(FakeSystem({}), now=NOW.replace(year=2027))
    text = output(report)
    assert '未发现 PHP' in text and '规则已过期' in text
    assert 'UNKNOWN' in text


def test_plan_is_readonly_without_requiring_dry_run_flag(capsys):
    assert main(['plan'], system=FakeSystem(CASES[0]), now=NOW) == 4
    text = capsys.readouterr().out
    assert 'BLOCKED' in text and 'NOT_RUN' in text and '{"' not in text
