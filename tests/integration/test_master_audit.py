"""Master audit release-blocking integration tests."""

import io
import unittest
from pathlib import Path

from pead.audits.master import AUDIT_IDS, execute_master_audit
from pead.config.console import ResearchConsole
from pead.phase9.fixtures import machine_audit_reports

ROOT = Path(__file__).parents[2]


class MasterAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.console = ResearchConsole("9-test", stream=io.StringIO())

    def test_all_thirteen_machine_audits_pass(self) -> None:
        report = execute_master_audit(machine_audit_reports(ROOT), console=self.console)
        self.assertEqual(report["audits"], list(AUDIT_IDS))

    def test_every_release_blocking_fixture_returns_nonzero_semantics(self) -> None:
        for audit_id in AUDIT_IDS:
            with self.subTest(audit_id=audit_id):
                reports = machine_audit_reports(ROOT)
                reports[audit_id] = {"status": "fail", "fixture": f"release-block-{audit_id}"}
                with self.assertRaises(ValueError):
                    execute_master_audit(reports, console=self.console)

    def test_missing_audit_fails_closed(self) -> None:
        reports = machine_audit_reports(ROOT)
        reports.pop("traces")
        with self.assertRaises(ValueError):
            execute_master_audit(reports, console=self.console)
        reports = machine_audit_reports(ROOT)
        reports["traces"] = {"status": "pass"}
        with self.assertRaises(ValueError):
            execute_master_audit(reports, console=self.console)


if __name__ == "__main__":
    unittest.main()
