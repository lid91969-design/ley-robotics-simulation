import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from csv_quality import inspect_inputs, main, render_html, typed_value_ok

ROOT = Path(__file__).resolve().parent


class CsvQualityTests(unittest.TestCase):
    def test_clean_fixture_bom_quoted_commas_newlines_and_text_ids(self):
        source = ROOT / "fixtures" / "good.csv"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.csv"
            path.write_bytes(b"\xef\xbb\xbf" + source.read_bytes())
            report = inspect_inputs([path])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["records_checked"], 2)
        first, second = report["records"]
        self.assertEqual(first["values"]["record_id"], "0001")
        self.assertEqual(first["values"]["notes"], "Synthetic fixture, no real sensor")
        self.assertEqual(second["values"]["reading"], "1.02e2")
        self.assertIn('\nline 2; <script>alert("synthetic")</script> & text', second["values"]["notes"])
        self.assertEqual(second["line_end"], 4)

    def test_all_five_categories_and_cross_file_duplicate(self):
        report = inspect_inputs([ROOT / "fixtures/good.csv", ROOT / "fixtures/faulty.csv"])
        self.assertEqual(report["records_checked"], 5)
        self.assertEqual(report["finding_count"], 9)
        self.assertFalse(report["input_errors"])
        self.assertEqual(report["rule_counts"], dict(missing_required_columns=1, blank_required_cells=2,
            duplicate_record_id=1, invalid_typed_values=4, unexpected_columns=1))
        duplicate = next(item for item in report["findings"] if item["category"] == "duplicate_record_id")
        self.assertEqual(duplicate["value"], "0002")
        self.assertEqual(duplicate["first_occurrence"]["file_index"], 1)
        self.assertEqual(duplicate["first_occurrence"]["record_number"], 2)
        for value in ("NaN", "Infinity", "1_000", " 1", "1,2", "１２"):
            with self.subTest(value=value):
                self.assertFalse(typed_value_ok("reading", value))
        self.assertFalse(typed_value_ok("observed_on", "20260112"))

    def test_html_escaping_preserves_quoted_raw_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["record_id", "observed_on", "sensor_id", "reading", "unit", "notes", "<script>header</script>"])
                writer.writerow(["0007", "2026-01-01", "SYNTHETIC", "0.100", "m", '<script>alert("x")</script>,\n& tail', "fixture"])
            report = inspect_inputs([path])
            page = render_html(report)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;header&lt;/script&gt;", page)
        self.assertIn("&lt;script&gt;alert", page)
        self.assertIn("&amp; tail", page)
        self.assertEqual(report["records"][0]["values"]["reading"], "0.100")

    def test_cli_outputs_source_protection_and_incomplete_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_bytes((ROOT / "fixtures/good.csv").read_bytes())
            before = source.read_bytes()
            output_json, output_html = root / "results.json", root / "report.html"
            with redirect_stdout(io.StringIO()):
                result = main(["--synthetic", str(source), "--json", str(output_json), "--html", str(output_html)])
            self.assertEqual(result, 0)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(json.loads(output_json.read_text(encoding="utf-8"))["status"], "pass")
            self.assertIn("SYNTHETIC DATA", output_html.read_text(encoding="utf-8"))
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main(["--synthetic", str(source), "--json", str(source), "--html", str(output_html)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual(source.read_bytes(), before)
            bad = root / "wrong-width.csv"
            bad.write_text("record_id,observed_on,sensor_id,reading,unit\n0001,2026-01-01,SYNTHETIC,1\n", encoding="utf-8")
            incomplete = inspect_inputs([bad])
            self.assertEqual(incomplete["status"], "input_error")
            self.assertEqual(incomplete["records_checked"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
