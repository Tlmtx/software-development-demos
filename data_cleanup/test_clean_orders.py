import csv
from pathlib import Path
import tempfile
import unittest
from clean_orders import clean, FIELDS, spreadsheet_safe


class CleanupTests(unittest.TestCase):
    def run_rows(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(FIELDS)
                writer.writerows(rows)
            return clean([path])

    def test_duplicate_and_conflict_are_distinguished(self):
        row = ["A1", "2026-10-01", "North", "P1", "2", "0.10"]
        records, issues, summary = self.run_rows([row, row, row[:-1] + ["0.20"]])
        self.assertEqual(len(records), 1)
        self.assertEqual(summary["duplicates_removed"], 1)
        self.assertEqual(summary["rejected_rows"], 1)
        self.assertEqual(summary["total_amount"], "0.20")
        self.assertIn("Conflicting", issues[1]["reason"])

    def test_invalid_values_are_excluded(self):
        records, issues, summary = self.run_rows([
            ["", "2026-10-01", "North", "P1", "1", "2.00"],
            ["A2", "2026-02-30", "North", "P1", "1", "2.00"],
            ["A3", "2026-10-01", "North", "P1", "0", "2.00"],
            ["A4", "2026-10-01", "North", "P1", "1", "NaN"],
            ["A5", "2026-10-01", "North", "P1", "1", "2.005"],
        ])
        self.assertEqual(records, [])
        self.assertEqual(summary["rejected_rows"], 5)
        self.assertEqual(len(issues), 5)

    def test_zero_price_and_decimal_arithmetic(self):
        records, _, summary = self.run_rows([
            ["A1", "2026-10-01", "North", "P1", "3", "0.10"],
            ["A2", "2026-10-01", "North", "P2", "1", "0"],
        ])
        self.assertEqual(len(records), 2)
        self.assertEqual(summary["total_amount"], "0.30")

    def test_formula_like_text_is_neutralized_for_csv(self):
        for value in ("=1+1", "+cmd", "-cmd", " @SUM(A1)"):
            self.assertTrue(spreadsheet_safe(value).startswith("'"))
        self.assertEqual(spreadsheet_safe("SKU-001"), "SKU-001")


if __name__ == "__main__":
    unittest.main(verbosity=2)
