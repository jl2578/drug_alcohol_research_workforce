# SPDX-License-Identifier: MIT
"""Scientific-regression checks for released content adapters (stdlib only)."""
import json
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dashboard_common import finalize, load_context
import dashboard_content as adapter


class ContentAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.data = {key: finalize(key, payload, cls.ctx.contracts[key])
                    for key, payload in adapter.build(cls.ctx).items()}

    def test_population_cells_keep_fixed_full_corpus_base_and_zero(self):
        rows = self.data["population_composition"]["rows"]
        self.assertEqual(len(rows), 72)
        self.assertEqual(sum(r["numerator"] for r in rows), 13227)
        self.assertEqual({r["denominator"] for r in rows}, {13227})
        zeros = [r for r in rows if r["numerator"] == 0]
        self.assertTrue(zeros)
        self.assertTrue(all(r["value_status"] == "available" and Decimal(r["value"]) == 0 for r in zeros))

    def test_observed_denominators_and_continuing_coverage(self):
        source = {tuple(r[k] for k in adapter.COUNT_KEY): r for r in self.ctx.tables[adapter.COUNTS]}
        rows = self.data["content_observed"]["rows"]
        self.assertEqual(len(rows), 2528)
        for row in rows:
            original = source[tuple(row[k] for k in adapter.COUNT_KEY)]
            self.assertEqual(row["denominator"], int(original["eligible_works"]))
            self.assertEqual(row["numerator"], int(original["selected_works"]))
            if row["population"] == "continuing":
                self.assertEqual(row["coverage_context_source"], adapter.COUNTS)
                self.assertEqual(json.loads(row["coverage_context"])["population"], "continuing")
        # Keeping only one category must not create a new denominator.
        first = rows[0]
        group = [r for r in rows if all(r[k] == first[k] for k in adapter.COUNT_KEY[:-1])]
        self.assertEqual(len({r["denominator"] for r in group}), 1)

    def test_observed_comparisons_keep_separate_operand_bases_and_reverse(self):
        rows = self.data["content_observed_difference"]["rows"]
        by_key = {tuple(r[k] for k in ("outcome", "population", "period", "group_a", "group_b", "category")): r for r in rows}
        row = next(r for r in rows if r["denominator_a"] != r["denominator_b"] and Decimal(r["value"]) != 0)
        reverse = by_key[(row["outcome"], row["population"], row["period"], row["group_b"], row["group_a"], row["category"])]
        self.assertEqual(Decimal(row["value"]), Decimal(reverse["value"]).copy_negate())
        self.assertEqual(row["denominator_a"], reverse["denominator_b"])
        self.assertEqual(row["source_key_a"], reverse["source_key_b"])
        self.assertEqual(row["interval_status"], "not_computed")
        self.assertIsNone(row["lower"])
        self.assertTrue(all(r["group_a"] != r["group_b"] for r in rows))

    def test_saved_paired_bounds_are_not_generic_blank_columns(self):
        source = {(table, r["estimand_id"]): r for table in adapter.PAIR for r in self.ctx.tables[table]}
        rows = self.data["content_fitted_contrasts"]["rows"]
        self.assertEqual(len(rows), 5280)
        for row in rows:
            original = source[(row["source_table_id"], row["estimand_id"])]
            self.assertEqual(row["value"], original["difference_pp"])
            self.assertEqual(row["lower"], original["lower_95_pp"])
            self.assertEqual(row["upper"], original["upper_95_pp"])
            self.assertEqual(row["units"], "percentage_points")
            self.assertEqual(row["interval_status"], "available")
            self.assertEqual(row["display_direction"], "stored")

    def test_unsupported_targets_and_missing_intervals_are_distinct(self):
        rows = self.data["content_fitted"]["rows"]
        self.assertEqual(len(rows), 10956)
        unsupported = [r for r in rows if r["support_status"] == "unsupported"]
        self.assertEqual(len(unsupported), 8844)
        self.assertTrue(all(r["value"] is None and r["unavailable_reason"] for r in unsupported))
        missing_intervals = [r for r in rows if r["value_status"] == "available" and r["interval_status"] == "unavailable"]
        self.assertEqual(len(missing_intervals), 2)
        self.assertTrue(all(r["value"] is not None and r["lower"] is None for r in missing_intervals))

    def test_temporal_units_population_and_support_layout(self):
        rows = self.data["content_temporal_changes"]["rows"]
        self.assertEqual(len(rows), 7304)
        source = {(table, r["estimand_id"]): r for table in adapter.TEMP for r in self.ctx.tables[table]}
        for row in rows:
            original = source[(row["source_table_id"], row["estimand_id"])]
            self.assertEqual(row["units"], "percentage_points")
            if row["value_status"] == "available":
                self.assertEqual(row["value"], original["estimate"])
            if row["outcome"] in ("C4", "C8") and row["value_status"] == "available":
                counts = json.loads(row["support_counts_by_outcome_and_source"])
                self.assertEqual(counts["early_eligible_works"], int(original["early_eligible_works"]))
            self.assertEqual(row["analysis_population"], "primary" if row["source_table_id"] == adapter.TEMP[0] else "continuing")

    def test_institution_join_preserves_blank_embedded_ids_and_intervals(self):
        rows = self.data["institution_profiles"]["rows"]
        self.assertEqual(len(rows), 2200)
        self.assertEqual(sum(r["source_embedded_institution_id"] is None for r in rows), 1000)
        self.assertEqual(sum(r["interval_status"] == "unavailable" for r in rows), 60)
        self.assertTrue(all(r["institution_id"] == r["unit_id"] and r["value_status"] == "available" for r in rows))
        self.assertTrue(all(len(json.loads(r["coverage"])) == 2 for r in rows))
        self.assertNotIn("period", self.data["institution_profiles"]["filter_fields"])

    def test_benchmark_uses_every_fixed_member_even_without_intervals(self):
        rows = self.data["institution_benchmark"]["rows"]
        self.assertEqual(len(rows), 44)
        reference = {r["institution_id"] for r in self.ctx.tables[adapter.T12]}
        for row in rows:
            self.assertEqual(row["cohort_n"], 50)
            self.assertEqual(row["valid_member_n"], 50)
            self.assertEqual(row["interval_status"], "not_computed")
            refs = json.loads(row["member_source_rows"])
            members = {json.loads(r["source_key"])[1] for r in refs}
            self.assertEqual(members, reference)
        # A real cell containing unavailable profile intervals still has a 50-point mean.
        missing = next(r for r in self.ctx.tables[adapter.T10] if not r["lower"])
        match = next(r for r in rows if r["outcome"] == missing["outcome"] and r["category"] == missing["category"])
        values = [Decimal(r["estimate"]) for r in self.ctx.tables[adapter.T10]
                  if r["outcome"] == match["outcome"] and r["category"] == match["category"]]
        with localcontext() as context:
            context.prec = 34
            context.rounding = ROUND_HALF_EVEN
            expected = sum(values, Decimal(0)) / Decimal(50)
        self.assertEqual(Decimal(match["value"]), expected)

    def test_missing_benchmark_point_does_not_shrink_cohort(self):
        tables = dict(self.ctx.tables)
        removed = tables[adapter.T10][0]
        tables[adapter.T10] = tables[adapter.T10][1:]
        context = SimpleNamespace(**{**vars(self.ctx), "tables": tables})
        labels = adapter._index(context.tables[adapter.T16], ("outcome", "category"))
        rows = adapter._institution_benchmark(context, labels)["rows"]
        affected = next(r for r in rows if r["outcome"] == removed["outcome"] and r["category"] == removed["category"])
        self.assertEqual(affected["cohort_n"], 50)
        self.assertEqual(affected["valid_member_n"], 49)
        self.assertIsNone(affected["value"])
        self.assertEqual(affected["value_status"], "unavailable")
        self.assertIn(removed["unit_id"], json.loads(affected["unavailable_member_ids"]))
        self.assertEqual(len(rows), 44)


if __name__ == "__main__":
    unittest.main()
