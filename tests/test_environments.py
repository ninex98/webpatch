from dataclasses import asdict
from datetime import datetime
import json

from webpatch.cli import main
from webpatch.planning import plan
from webpatch.service import scan

from conftest import NOW


def test_environment_decisions_and_no_false_safe(server):
    case, system = server
    now = datetime.fromisoformat(case["now"]) if "now" in case else NOW
    report = scan(system, now=now)
    assert [a.version_status for a in report.assessments[::2]] == case["expect"]
    assert [a.version_status for a in report.assessments[1::2]] == case["expect"]
    assert report.safe is False
    assert all(a.runtime_status == "UNKNOWN" for a in report.assessments)
    assert report.overall == ("POTENTIALLY_AFFECTED" if "BELOW_VENDOR_FIX" in case["expect"] else "UNKNOWN")
    assert all(h.verification == "UNKNOWN" for h in report.inventory.runtime_hints)
    assert "RUNNING_IMAGES_AND_WEB_ROUTES_UNVERIFIED" in report.inventory.coverage_gaps
    if "gap" in case:
        assert case["gap"] in report.inventory.coverage_gaps
    if "scope" in case:
        assert report.inventory.environment.scope == case["scope"]
    hints = [h for h in report.inventory.runtime_hints if h.pid is not None]
    if "hint_scope" in case:
        assert hints[0].scope == case["hint_scope"]
    if case.get("deleted"):
        assert hints[0].deleted
    for path in case.get("paths", []):
        assert path in [h.path for h in report.inventory.runtime_hints]
    evidence_ids = {e.id for e in report.evidence}
    assert all(set(a.evidence_ids) <= evidence_ids for a in report.assessments)
    assert all(set(h.evidence_ids) <= evidence_ids for h in report.inventory.runtime_hints)
    assert len(evidence_ids) == len(report.evidence)
    proposal = plan(report)
    assert proposal.status == "BLOCKED"
    assert proposal.executable is False
    assert proposal.apt_simulation == "NOT_RUN"
    assert proposal.actions == ()
    assert "APT_DRY_RUN_NOT_PERFORMED" in proposal.blockers
    assert len(proposal.report_sha256) == 64
    # Actual API contract serializes without a bespoke encoder.
    assert json.loads(json.dumps(asdict(report)))["safe"] is False


def test_cli_contract_and_exit_codes(server, capsys):
    case, system = server
    now = datetime.fromisoformat(case["now"]) if "now" in case else NOW
    rc = main(["scan", "--format", "json"], system=system, now=now)
    data = json.loads(capsys.readouterr().out)
    assert rc == (1 if "BELOW_VENDOR_FIX" in case["expect"] else 2)
    assert data["schema_version"] == 1
    assert data["safe"] is False
    assert main(["plan", "--dry-run", "--format", "json"], system=system, now=now) == 4
    assert json.loads(capsys.readouterr().out)["executable"] is False
    before = len(system.calls)
    assert main(["apply"], system=system, now=now) == 4
    assert len(system.calls) == before  # no I/O at all on disabled executor
