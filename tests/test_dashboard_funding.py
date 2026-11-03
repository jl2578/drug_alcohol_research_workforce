"""Check scientific interpretation and unavailable-state behavior of adapters."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dashboard_common import canonical_json, load_context
from dashboard_funding import build, CONTENT, COUNTS, SCENARIO


class FundingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.data = build(cls.ctx)

    def test_counts_and_contract_keys(self):
        expected = {"funding_reach": 72, "funding_content_profiles": 1056,
                    "funding_content_contrasts": 792, "institutional_count_associations": 6,
                    "within_pi_participation": 12, "award_frame_disposition": 720,
                    "award_search_capture": 600}
        contracts = {d["id"]: d for d in self.ctx.contract["datasets"]}
        for dataset, count in expected.items():
            with self.subTest(dataset=dataset):
                rows = self.data[dataset]["rows"]
                self.assertEqual(len(rows), count)
                keys = [tuple(r[k] for k in contracts[dataset]["output_key"]) for r in rows]
                self.assertEqual(len(set(keys)), count)
                self.assertTrue(all(not isinstance(v, (dict, list, float)) for r in rows for v in r.values()))

    def test_content_uses_separate_bases_and_original_tokens(self):
        source = {tuple(r[k] for k in ["connection_definition", "ownership", "degree_target", "outcome", "category"]): r
                  for r in self.ctx.tables[COUNTS]}
        for r in self.data["funding_content_profiles"]["rows"]:
            src = source[tuple(r[k] for k in ["connection_definition", "ownership", "degree_target", "outcome", "category"])]
            state = r["connection_status"]
            self.assertEqual(r["denominator"], int(src[state + "_n"]))
            self.assertEqual(r["value"], src[state + "_percent"])
            self.assertEqual(r["interval_status"], "not_computed")
        # Category selection cannot change a row's declared base.
        group = [r for r in self.data["funding_content_profiles"]["rows"]
                 if r["connection_definition"] == "primary_combined" and r["ownership"] == "full"
                 and r["degree_target"] == "Research doctorate" and r["outcome"] == "C8"
                 and r["connection_status"] == "connected"]
        self.assertEqual(len({r["denominator"] for r in group}), 1)
        self.assertGreater(sum(Decimal(r["value"]) for r in group), 100)

    def test_contrasts_keep_compound_bases_without_intervals(self):
        source = {(table, r["target_id"]): r for table in CONTENT for r in self.ctx.tables[table]}
        direct = []
        for r in self.data["funding_content_contrasts"]["rows"]:
            src = source[(r["source_table_id"], r["target_id"])]
            self.assertEqual(json.loads(r["bases"]), json.loads(src["denominator"]))
            self.assertEqual(r["bases"], r["denominator"])
            self.assertEqual(r["counts"], r["numerator"])
            for field in ("numerator", "denominator", "category_counts_all_groups_json"):
                expected = canonical_json(json.loads(src[field], parse_float=str, parse_int=int)) if src[field] else None
                self.assertEqual(r[field], expected)
                self.assertEqual(r["source_" + field], src[field])
            self.assertEqual(r["value"], src["estimate_percent_or_pp"])
            self.assertEqual(r["source_interval_status"], "not_applicable_observed_corpus_description")
            self.assertEqual(r["interval_status"], "not_applicable")
            self.assertIsNone(r["lower"])
            if r["degree_target"] == "Masters minus research doctorate": direct.append(r)
        self.assertEqual(len(direct), 264)
        self.assertTrue(all(isinstance(json.loads(r["bases"]), dict) for r in direct))

    def test_count_contrast_routes_to_common_fits(self):
        ds = self.data["institutional_count_associations"]
        for r in ds["rows"]:
            fit_ids = json.loads(r["fit_ids"])
            if r["degree_target"] == "Masters minus research doctorate":
                self.assertEqual(len(fit_ids), 2)
                self.assertTrue(all("__common__" in x for x in fit_ids))
            else:
                self.assertEqual(len(fit_ids), 1)
                self.assertIn("__main__", fit_ids[0])
            self.assertEqual(r["lower_pointwise"], r["pointwise95_lower"])
            self.assertEqual(r["upper_familywise"], r["familywise95_upper"])
            self.assertIsNone(r["numerator"])
            self.assertIsNone(r["denominator"])
            self.assertEqual(r["denominator_status"], "not_applicable")
        self.assertNotIn("interval_family", ds["filter_fields"])
        self.assertEqual(ds["metadata"]["virtual_filters"]["interval_family"]["values"], ["pointwise", "familywise"])

    def test_pi_means_are_not_recomputed_from_pooled_totals(self):
        saved = {(r["ownership"], r["degree_group"]): r for r in self.ctx.tables["DEP3_investigator_equal_pi_summary"]}
        fields = {"funded_mean": "mean_funded_works_per_year", "unfunded_mean": "mean_unfunded_works_per_year",
                  "paired_difference": "mean_paired_difference_works_per_year"}
        found_distinction = False
        for r in self.data["within_pi_participation"]["rows"]:
            src = saved[(r["ownership"], r["degree_group"])]
            self.assertEqual(r["value"], src[fields[r["measure"]]])
            self.assertEqual(r["denominator"], int(src["PIs"]))
            self.assertEqual(r["denominator_unit"], "PIs")
            self.assertEqual(r["denominator_role"], "equal_PI_averaging_base")
            self.assertIsNone(r["numerator"])
            self.assertEqual(r["numerator_status"], "not_applicable")
            if r["measure"] == "funded_mean":
                pooled = Decimal(src["funded_qualifying_PI_work_participations"]) / Decimal(src["funded_years"])
                found_distinction |= abs(Decimal(r["value"]) - pooled) > Decimal("0.0001")
        self.assertTrue(found_distinction)

    def test_case_sensitive_bases_and_capture_specific_intervals(self):
        for r in self.data["award_frame_disposition"]["rows"]:
            self.assertEqual(r["numerator"], r["n"])
            self.assertEqual(r["denominator"], r["N"])
            self.assertIsNone(r["lower"])
        for r in self.data["award_search_capture"]["rows"]:
            if r["measure"] == "search_capture":
                self.assertEqual(r["interval_type"], "Wilson95")
                self.assertEqual(r["denominator"], r["linked_work_N"])
                self.assertEqual(r["lower"], r["search_capture_wilson95_lower"])
            else:
                self.assertEqual(r["interval_type"], "not_provided_descriptive")
                self.assertIsNone(r["lower"])
                self.assertIsNone(r["upper"])
            if r["measure"] == "nonretrieval_share_of_noninclusion":
                self.assertEqual(r["denominator"], r["linked_work_N"] - r["included_work_n"])

    def test_missing_and_zero_are_distinct(self):
        tables = dict(self.ctx.tables)
        key = "DEP1_search_capture_by_period_and_scenario"
        sample = deepcopy(tables[key][0])
        sample.update(linked_work_N="0", candidate_frame_work_n="0", included_work_n="0",
                      not_retrieved_work_n="0", assessable_candidate_work_n="0")
        tables[key] = [sample]
        changed = SimpleNamespace(tables=tables, contract=self.ctx.contract, scope=self.ctx.scope, repo=self.ctx.repo)
        rows = build(changed)["award_search_capture"]["rows"]
        self.assertTrue(all(r["value"] is None and r["value_status"] == "unavailable" for r in rows))
        self.assertTrue(all(r["unavailable_reason"] == "zero_denominator" for r in rows))
        self.assertTrue(any(r["numerator"] == 0 and r["value_status"] == "available"
                            for r in self.data["award_frame_disposition"]["rows"]))

    def test_input_rows_are_not_mutated(self):
        before = deepcopy(self.ctx.tables["DEP3_observed_reach"])
        build(self.ctx)
        self.assertEqual(self.ctx.tables["DEP3_observed_reach"], before)


if __name__ == "__main__":
    unittest.main()
