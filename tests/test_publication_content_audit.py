# SPDX-License-Identifier: MIT
"""Independent all-row publication audit of generated content artifacts.

Read the persisted browser shards, then compare to released source records.
Expected calculations use Fraction and Decimal rather than adapter helpers.
No adapter, build routine, source edit or network access is used.
"""
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dashboard_common import load_context

DATASETS = (
    "population_composition", "content_observed", "content_observed_difference",
    "content_fitted", "content_fitted_contrasts", "content_temporal_changes",
    "institution_profiles", "institution_benchmark",
)
T20 = "DEP2_T20_degree_field_composition"
COUNTS = "DEP2_group_period_category_counts"
T2 = "DEP2_T2_group_support"
T3 = "DEP2_T3_profiles_and_periods"
PAIR = ("DEP2_T4_C3_pairwise", "DEP2_T5_C5_pairwise", "DEP2_T6_C4_pairwise", "DEP2_T7_C8_pairwise")
TEMP = ("DEP2_T8_temporal_changes", "DEP2_T9_continuing_changes")
T10, T12, T13, T14, T16 = (
    "DEP2_T10_institution_profiles", "DEP2_T12_institution_support",
    "DEP2_T13_group_period_coverage", "DEP2_T14_institution_period_coverage",
    "DEP2_T16_category_labels",
)
COUNT_KEY = ("outcome", "population", "group_id", "period", "category")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fraction_decimal(value):
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        return Decimal(value.numerator) / Decimal(value.denominator)


def read_artifact(dataset):
    manifest = json.loads((REPO / "dashboard/data" / (dataset + ".json")).read_text(encoding="utf-8"))
    rows = []
    for shard in manifest["shards"]:
        raw = (REPO / "dashboard" / shard["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != shard["sha256"]:
            raise AssertionError("Persisted shard checksum mismatch: " + shard["path"])
        part = json.loads(raw)
        for values in part["rows"]:
            if len(values) != len(manifest["columns"]):
                raise AssertionError("Persisted shard width mismatch")
            row = {}
            for index, (field, value) in enumerate(zip(manifest["columns"], values)):
                dictionary = part["dictionaries"].get(str(index))
                row[field] = dictionary[value] if dictionary is not None and value is not None else value
            rows.append(row)
    if len(rows) != manifest["row_count"]:
        raise AssertionError("Persisted manifest row count mismatch")
    return rows


class PublicationContentAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.rows = {dataset: read_artifact(dataset) for dataset in DATASETS}
        cls.sources = {}
        for dataset in DATASETS:
            for source in cls.ctx.contracts[dataset]["primary_sources"]:
                table, keys = source["table_id"], source["key"]
                cls.sources[table] = {tuple(row[k] for k in keys): row for row in cls.ctx.tables[table]}
        cls.labels = {(r["outcome"], r["category"]): r for r in cls.ctx.tables[T16]}
        cls.groups = {(r["outcome"], r["group_id"]): r for r in cls.ctx.tables[T2]}
        cls.support = {(r["outcome"], r["institution_id"]): r for r in cls.ctx.tables[T12]}

    def original(self, row):
        return self.sources[row["source_table_id"]][tuple(json.loads(row["source_key"]))]

    def assert_native(self, actual, source):
        self.assertEqual(None if actual is None else str(actual), source if source != "" else None)

    def assert_labels(self, row):
        original = self.labels[(row["outcome"], row["category"])]
        self.assertEqual(row["category_label"], original["display_label"])
        self.assertEqual(row["category_order"], int(original["category_order"]))
        self.assertEqual(row["category_definition"], original["definition"])

    def assert_saved(self, row, source, point, lower, upper, supported=True):
        expected_support = supported and source["report_supported"] == "1"
        self.assertEqual(row["support_status"], "supported" if expected_support else "unsupported")
        value_available = expected_support and source[point] != ""
        self.assertEqual(row["value"], source[point] if value_available else None)
        self.assertEqual(row["value_status"], "available" if value_available else "unavailable" if not expected_support else "missing")
        bounds_available = value_available and source[lower] != "" and source[upper] != ""
        self.assertEqual(row["lower"], source[lower] if bounds_available else None)
        self.assertEqual(row["upper"], source[upper] if bounds_available else None)
        self.assertEqual(row["interval_status"], "available" if bounds_available else "unavailable")
        self.assertEqual(row["source_lower"], source[lower] or None)
        self.assertEqual(row["source_upper"], source[upper] or None)
        self.assertIsNone(row["numerator"])
        self.assertIsNone(row["denominator"])
        self.assertEqual(row["denominator_status"], "not_applicable")
        if not value_available:
            self.assertTrue(row["unavailable_reason"])
        if not bounds_available:
            self.assertTrue(row["interval_reason"])
        self.assert_labels(row)

    def test_persisted_membership_keys_and_manifest_checksums(self):
        expected = (72, 2528, 34272, 10956, 5280, 7304, 2200, 44)
        for dataset, count in zip(DATASETS, expected):
            rows = self.rows[dataset]
            self.assertEqual(len(rows), count, dataset)
            keys = self.ctx.contracts[dataset]["output_key"]
            ids = []
            for row in rows:
                key = canonical([[field, row[field]] for field in keys])
                expected_id = dataset + ":" + hashlib.sha256(key.encode("utf-8")).hexdigest()
                self.assertEqual(row["row_id"], expected_id)
                ids.append(row["row_id"])
            self.assertEqual(len(ids), len(set(ids)))
            manifest = json.loads((REPO / "dashboard/metadata/datasets" / (dataset + ".json")).read_text(encoding="utf-8"))
            for path, digest in manifest["output_sha256"].items():
                self.assertEqual(hashlib.sha256((REPO / "dashboard" / path).read_bytes()).hexdigest(), digest)

    def test_all_direct_source_cells_preserve_tokens_or_declared_rebindings(self):
        # Exceptions are checked independently below against their designated source.
        rebound = {
            "population_composition": set(), "content_observed": set(),
            "content_fitted": {"category_label", "interval_status"},
            "content_fitted_contrasts": {"category_label", "lower", "upper"},
            "content_temporal_changes": {"category_label", "interval_status"},
            "institution_profiles": {"category_label", "interval_status", "institution_id", "early_eligible_works", "late_eligible_works"},
        }
        for dataset, exceptions in rebound.items():
            encountered = Counter()
            for row in self.rows[dataset]:
                original = self.original(row)
                encountered[row["source_table_id"]] += 1
                for field, value in original.items():
                    if field not in exceptions:
                        self.assertIn(field, row)
                        self.assert_native(row[field], value)
                self.assertEqual(row["source_report_supported"], original.get("report_supported") or None)
            for source in self.ctx.contracts[dataset]["primary_sources"]:
                self.assertEqual(encountered[source["table_id"]], len(self.ctx.tables[source["table_id"]]))

    def test_population_fixed_base_and_saved_shares(self):
        self.assertEqual(sum(r["numerator"] for r in self.rows["population_composition"]), 13227)
        for row in self.rows["population_composition"]:
            source = self.original(row)
            self.assertEqual(row["numerator"], int(source["distinct_works"]))
            self.assertEqual(row["denominator"], 13227)
            self.assertEqual(row["value"], source["share_of_all_works_percent"])
            self.assertEqual(row["value_status"], "available")
            self.assertEqual(row["units"], "percent")

    def test_every_observed_ratio_and_base(self):
        primary = {(r["outcome"], r["group_id"], r["period"]): r for r in self.ctx.tables[T13]}
        for row in self.rows["content_observed"]:
            source = self.original(row)
            n, d = int(source["selected_works"]), int(source["eligible_works"])
            self.assertEqual((row["numerator"], row["denominator"]), (n, d))
            self.assertEqual(Decimal(row["value"]), fraction_decimal(Fraction(100 * n, d)))
            self.assertEqual(row["units"], "percent")
            self.assertEqual(row["support_status"], "supported")
            coverage = json.loads(row["coverage_context"])
            if row["population"] == "primary":
                original = primary[(row["outcome"], row["group_id"], row["period"])]
                for field, value in original.items():
                    self.assert_native(coverage[field], value)
            else:
                self.assertEqual(coverage["eligible_works"], d)
                self.assertEqual(coverage["eligible_institutions"], int(source["eligible_institutions"]))
                self.assertEqual(coverage["population"], "continuing")
            self.assert_labels(row)

    def test_every_observed_difference_exact_rational_and_operand_lineage(self):
        counts = self.sources[COUNTS]
        strata = Counter(tuple(r[k] for k in ("outcome", "population", "period", "category")) for r in self.ctx.tables[COUNTS])
        expected_count = sum(n * (n - 1) for n in strata.values())
        self.assertEqual(len(self.rows["content_observed_difference"]), expected_count)
        for row in self.rows["content_observed_difference"]:
            a, b = counts[tuple(json.loads(row["source_key_a"]))], counts[tuple(json.loads(row["source_key_b"]))]
            self.assertNotEqual(a["group_id"], b["group_id"])
            self.assertEqual(row["group_a"], a["group_id"])
            self.assertEqual(row["group_b"], b["group_id"])
            for field in ("outcome", "population", "period", "category"):
                self.assertEqual(row[field], a[field])
                self.assertEqual(a[field], b[field])
            for suffix, source in (("a", a), ("b", b)):
                self.assertEqual(row["numerator_" + suffix], int(source["selected_works"]))
                self.assertEqual(row["denominator_" + suffix], int(source["eligible_works"]))
                self.assertEqual(row["eligible_institutions_" + suffix], int(source["eligible_institutions"]))
            value = 100 * (Fraction(int(a["selected_works"]), int(a["eligible_works"])) - Fraction(int(b["selected_works"]), int(b["eligible_works"])))
            self.assertEqual(Decimal(row["value"]), fraction_decimal(value))
            self.assertEqual(row["units"], "percentage_points")
            self.assertEqual(row["difference_direction"], "group_a_minus_group_b")
            self.assertEqual(row["interval_status"], "not_computed")
            self.assertIsNone(row["lower"])
            self.assertIsNone(row["upper"])
            self.assert_labels(row)

    def test_every_saved_point_bound_status_and_support_count(self):
        for dataset in ("content_fitted", "content_fitted_contrasts", "content_temporal_changes"):
            for row in self.rows[dataset]:
                source = self.original(row)
                paired = dataset == "content_fitted_contrasts"
                self.assert_saved(row, source, "difference_pp" if paired else "estimate", "lower_95_pp" if paired else "lower", "upper_95_pp" if paired else "upper")
                self.assertEqual(row["units"], "probability" if dataset == "content_fitted" else "percentage_points")
                if paired:
                    self.assertEqual(row["display_direction"], "stored")
                    self.assertEqual(row["a_profile_percent"], source["group_a_profile_pct"])
                    self.assertEqual(row["b_profile_percent"], source["group_b_profile_pct"])
                    continue
                group = self.groups[(row["outcome"], row["group_id"])]
                self.assertEqual(row["degree_group"], group["degree_group"])
                self.assertEqual(row["field_code"], group["field_code"])
                continuing = row["source_table_id"] == TEMP[1]
                prefix = ("shared_" if continuing else "primary_") if row["outcome"] in ("C3", "C5") else ""
                counts = json.loads(row["support_counts_by_outcome"] if dataset == "content_fitted" else row["support_counts_by_outcome_and_source"])
                for field in ("early_eligible_works", "late_eligible_works", "early_institutions", "late_institutions"):
                    token = source.get(prefix + field)
                    self.assertEqual(counts[field], int(token) if token else None)
                if dataset == "content_temporal_changes":
                    self.assertEqual(row["analysis_population"], "continuing" if continuing else "primary")
                    self.assertEqual(row["period_direction"], "2017-2023_minus_2010-2016")

    def test_every_institution_point_join_and_period_context(self):
        coverage = defaultdict(dict)
        for row in self.ctx.tables[T14]:
            coverage[(row["outcome"], row["institution_id"])][row["period"]] = row
        for row in self.rows["institution_profiles"]:
            source = self.original(row)
            support = self.support[(row["outcome"], source["unit_id"])]
            self.assert_saved(row, source, "estimate", "lower", "upper", support["profile_supported"] == "1")
            self.assertEqual(row["institution_id"], source["unit_id"])
            self.assertEqual(row["institution_name"], support["institution_name"])
            self.assertEqual(row["source_embedded_institution_id"], source["institution_id"] or None)
            for field in ("early_eligible_works", "late_eligible_works"):
                self.assertEqual(row[field], int(support[field]))
            context = json.loads(row["coverage"])
            originals = coverage[(row["outcome"], source["unit_id"])]
            self.assertEqual({r["period"] for r in context}, set(originals))
            for record in context:
                for field, value in originals[record["period"]].items():
                    self.assert_native(record[field], value)
        missing = [r for r in self.rows["institution_profiles"] if r["interval_status"] == "unavailable"]
        self.assertEqual(len(missing), 60)
        self.assertTrue(all(r["value_status"] == "available" for r in missing))

    def test_all_fixed50_means_exact_and_membership_invariant(self):
        roster = self.ctx.scope["institution_benchmark"]["cohort"]["institution_ids"]
        digest = hashlib.sha256(("\n".join(sorted(roster)) + "\n").encode("utf-8")).hexdigest()
        points = {(r["outcome"], r["unit_id"], r["category"]): r for r in self.ctx.tables[T10]}
        for row in self.rows["institution_benchmark"]:
            selected = [points[(row["outcome"], institution, row["category"])] for institution in roster]
            exact = sum((Fraction(r["estimate"]) for r in selected), Fraction(0)) / 50
            self.assertEqual(Decimal(row["value"]), fraction_decimal(exact))
            self.assertEqual(row["cohort_n"], 50)
            self.assertEqual(row["valid_member_n"], 50)
            self.assertEqual(row["cohort_hash"], digest)
            self.assertEqual(row["member_weight"], "0.02")
            references = json.loads(row["member_source_rows"])
            self.assertEqual(len(references), 50)
            self.assertEqual({tuple(json.loads(r["source_key"])) for r in references}, {(row["outcome"], i, row["category"]) for i in roster})
            self.assertEqual({r["source_table_id"] for r in references}, {T10})
            self.assertEqual(row["interval_status"], "not_computed")
            self.assertIsNone(row["lower"])
            self.assertIsNone(row["upper"])
            self.assert_labels(row)


if __name__ == "__main__":
    unittest.main()
