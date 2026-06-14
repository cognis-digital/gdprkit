"""Smoke tests for GDPRKIT. Stdlib only, no network."""
import datetime as dt
import json
import os
import tempfile
import unittest

from gdprkit import (
    TOOL_NAME,
    TOOL_VERSION,
    DSARRequest,
    DSARTracker,
    validate_ropa,
    audit_cookies,
)
from gdprkit.cli import main


class TestMeta(unittest.TestCase):
    def test_tool_metadata(self):
        self.assertEqual(TOOL_NAME, "gdprkit")
        self.assertTrue(TOOL_VERSION)


class TestDSAR(unittest.TestCase):
    def test_overdue_detected(self):
        req = DSARRequest(id="R1", subject="a@x.com", type="access", received="2026-04-10")
        ev = req.evaluate(today=dt.date(2026, 6, 8))
        self.assertEqual(ev["status"], "overdue")
        self.assertEqual(ev["due"], "2026-05-10")
        self.assertLess(ev["days_remaining"], 0)

    def test_extension_extends_deadline(self):
        req = DSARRequest(id="R2", subject="b@x.com", type="erasure", received="2026-05-20", extended=True)
        ev = req.evaluate(today=dt.date(2026, 6, 8))
        self.assertEqual(ev["due"], "2026-07-19")
        self.assertEqual(ev["status"], "open")

    def test_closed_ontime_vs_late(self):
        ontime = DSARRequest(id="R3", subject="c", type="rectification", received="2026-04-01", fulfilled="2026-04-15")
        self.assertEqual(ontime.evaluate()["status"], "closed_ontime")
        late = DSARRequest(id="R4", subject="d", type="access", received="2026-04-01", fulfilled="2026-06-01")
        self.assertEqual(late.evaluate()["status"], "closed_late")

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            DSARRequest(id="R5", subject="e", type="bogus", received="2026-04-01")

    def test_tracker_report_not_compliant_when_overdue(self):
        tracker = DSARTracker.from_records([
            {"id": "R1", "subject": "a", "type": "access", "received": "2026-04-10"},
        ])
        rep = tracker.report(today=dt.date(2026, 6, 8))
        self.assertFalse(rep["compliant"])
        self.assertEqual(rep["overdue"], 1)


class TestROPA(unittest.TestCase):
    def test_flags_missing_and_special(self):
        res = validate_ropa([
            {"name": "", "purpose": "", "lawful_basis": "contract", "categories": ["health"], "retention": ""},
        ])
        self.assertFalse(res["compliant"])
        act = res["activities"][0]
        joined = " ".join(act["issues"])
        self.assertIn("name", joined)
        self.assertIn("special-category", joined)

    def test_invalid_lawful_basis(self):
        res = validate_ropa([
            {"name": "X", "purpose": "p", "lawful_basis": "vibes", "categories": ["c"], "retention": "1y"},
        ])
        self.assertFalse(res["activities"][0]["valid"])

    def test_valid_entry(self):
        res = validate_ropa([
            {"name": "Billing", "purpose": "pay", "lawful_basis": "contract", "categories": ["customers"], "retention": "7y"},
        ])
        self.assertTrue(res["compliant"])


class TestCookies(unittest.TestCase):
    def test_consent_before_set(self):
        res = audit_cookies([
            {"name": "_ga", "category": "analytics", "consent_before_set": False, "third_party": True, "provider": "Google"},
        ])
        self.assertFalse(res["compliant"])
        self.assertIn("before consent", " ".join(res["cookies"][0]["issues"]))

    def test_essential_exempt(self):
        res = audit_cookies([
            {"name": "sessionid", "category": "strictly_necessary", "consent_before_set": False, "expiry_days": 1},
        ])
        self.assertTrue(res["compliant"])

    def test_long_expiry_flagged(self):
        res = audit_cookies([
            {"name": "_ga", "category": "analytics", "consent_before_set": True, "expiry_days": 730, "provider": "g", "third_party": True},
        ])
        self.assertIn("13-month", " ".join(res["cookies"][0]["issues"]))


class TestCLI(unittest.TestCase):
    def _write(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        self.addCleanup(os.remove, path)
        return path

    def test_dsar_cli_nonzero_on_overdue(self):
        path = self._write([
            {"id": "R1", "subject": "a", "type": "access", "received": "2026-04-10"},
        ])
        rc = main(["--format", "json", "dsar", path, "--today", "2026-06-08"])
        self.assertEqual(rc, 1)

    def test_ropa_cli_zero_when_clean(self):
        path = self._write([
            {"name": "Billing", "purpose": "pay", "lawful_basis": "contract", "categories": ["customers"], "retention": "7y"},
        ])
        rc = main(["ropa", path])
        self.assertEqual(rc, 0)

    def test_bad_input_exit_2(self):
        rc = main(["cookies", "/no/such/file.json"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

class TestHardening(unittest.TestCase):
    """Tests for input-validation and error-handling hardening."""

    def _write(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        self.addCleanup(os.remove, path)
        return path

    # ---- core: non-list inputs raise TypeError ----

    def test_dsar_from_records_non_list_raises(self):
        with self.assertRaises(TypeError):
            DSARTracker.from_records("not a list")

    def test_ropa_non_list_raises(self):
        with self.assertRaises(TypeError):
            validate_ropa({"key": "val"})

    def test_cookies_none_raises(self):
        with self.assertRaises(TypeError):
            audit_cookies(None)

    # ---- core: non-dict records raise TypeError ----

    def test_dsar_from_records_non_dict_record_raises(self):
        with self.assertRaises(TypeError):
            DSARTracker.from_records(["not", "dicts"])

    def test_ropa_non_dict_record_raises(self):
        with self.assertRaises(TypeError):
            validate_ropa([42])

    def test_cookies_non_dict_record_raises(self):
        with self.assertRaises(TypeError):
            audit_cookies([None])

    # ---- core: empty DSAR id raises ValueError ----

    def test_dsar_empty_id_raises(self):
        with self.assertRaises(ValueError):
            DSARRequest(id="", subject="a", type="access", received="2026-01-01")

    # ---- CLI: non-dict record in input returns exit 2 ----

    def test_cli_ropa_non_dict_record_exit_2(self):
        path = self._write([42])
        rc = main(["ropa", path])
        self.assertEqual(rc, 2)

    def test_cli_cookies_non_dict_record_exit_2(self):
        path = self._write([None])
        rc = main(["cookies", path])
        self.assertEqual(rc, 2)

    def test_cli_dsar_non_dict_record_exit_2(self):
        path = self._write(["bad"])
        rc = main(["dsar", path])
        self.assertEqual(rc, 2)

    # ---- CLI: malformed --today date returns exit 2 ----

    def test_cli_dsar_bad_today_exit_2(self):
        path = self._write([
            {"id": "R1", "subject": "a", "type": "access", "received": "2026-01-01"},
        ])
        rc = main(["dsar", path, "--today", "not-a-date"])
        self.assertEqual(rc, 2)

    # ---- CLI: malformed JSON input returns exit 2 ----

    def test_cli_malformed_json_exit_2(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            fh.write("{bad json}")
        self.addCleanup(os.remove, path)
        rc = main(["ropa", path])
        self.assertEqual(rc, 2)

    # ---- core: empty collections return compliant=True ----

    def test_empty_dsar_compliant(self):
        rep = DSARTracker.from_records([]).report()
        self.assertTrue(rep["compliant"])
        self.assertEqual(rep["total"], 0)

    def test_empty_ropa_compliant(self):
        res = validate_ropa([])
        self.assertTrue(res["compliant"])
        self.assertEqual(res["total"], 0)

    def test_empty_cookies_compliant(self):
        res = audit_cookies([])
        self.assertTrue(res["compliant"])
        self.assertEqual(res["total"], 0)


if __name__ == "__main__":
    unittest.main()