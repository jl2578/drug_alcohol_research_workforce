"""Deterministic funding and award-frame adapters over released table rows."""
from decimal import Decimal
import json

from dashboard_common import canonical_json, source_row


COUNTS = "DEP3/other_rq3/reach_content/data/NA38_T4_D_observed_counts.csv"
COVERAGE = "DEP3/other_rq3/reach_content/data/NA39_T4_D_observed_coverage.csv"
CONTENT = (
    "DEP3_observed_content",
    "DEP3/other_rq3/reach_content/data/NA40_T4_D_award_possible_sensitivity.csv",
    "DEP3/other_rq3/reach_content/data/NA41_T4_D_PI_component_profiles.csv",
)
SCENARIO = ["extension_years", "match_definition", "mechanism_group", "completion_period"]
CONTENT_KEY = ["connection_definition", "ownership", "degree_target", "outcome", "category"]
CONTENT_BASE_KEY = CONTENT_KEY[:-1]
CONNECTION_CROSSWALK = {
    "combined_clear": "primary_combined",
    "PI_only": "PI_component",
    "combined_clear_or_possible": "award_possible_sensitivity",
}
CAPTURE_MEASURES = {
    "search_capture": ("candidate_frame_work_n", "linked_work_N", "search_capture_percent"),
    "included_of_linked": ("included_work_n", "linked_work_N", "included_of_linked_percent"),
    "included_of_retrieved": ("included_work_n", "candidate_frame_work_n", "included_of_retrieved_percent"),
    "included_of_assessable_retrieved": ("included_work_n", "assessable_candidate_work_n", "included_of_assessable_retrieved_percent"),
    "nonretrieval_share_of_noninclusion": ("not_retrieved_work_n", None, "nonretrieval_share_of_noninclusion_percent"),
}


def _integer(value):
    return None if value in (None, "") else int(value)


def _native(table, source, keys, integer_fields=()):
    """Keep source tokens; source keys remain strings even when numeric-looking."""
    row = {k: (v if v != "" else None) for k, v in source.items()}
    for field in integer_fields:
        if field in source and field not in keys:
            row[field] = _integer(source[field])
    if "interval_status" in row:
        row["source_interval_status"] = row.pop("interval_status")
    row.update(source_row(table, source, keys))
    return row


def _structured(value):
    if value in (None, ""):
        return None
    return canonical_json(json.loads(value, parse_float=str, parse_int=int))


def _point(row, token, denominator=None, needs_base=False):
    """Unavailable ratios never silently use a different base or become zero."""
    reason = None
    if needs_base and denominator is None:
        reason = "unavailable_denominator"
    elif needs_base and denominator == 0:
        reason = "zero_denominator"
    elif needs_base and denominator < 0:
        raise ValueError("Negative scientific denominator")
    elif token in (None, ""):
        reason = "not_provided_in_released_source"
    elif not Decimal(token).is_finite():
        raise ValueError("Nonfinite saved scientific value")
    row.update(value=None if reason else token,
               support_status="supported", value_status="unavailable" if reason else "available",
               unavailable_reason=reason)


def _no_interval(row, reason, status="not_computed"):
    row.update(lower=None, upper=None, interval_status=status,
               interval_unavailable_reason=reason)


def _index(rows, fields):
    result = {}
    for row in rows:
        key = tuple(row[f] for f in fields)
        if key in result:
            raise ValueError(f"Duplicate source join key: {fields}: {key}")
        result[key] = row
    return result


def _ratio_counts(numerator, denominator):
    if numerator is not None and denominator is not None:
        if numerator < 0 or denominator < 0 or numerator > denominator:
            raise ValueError("Count ratio violates 0 <= numerator <= denominator")


def build(ctx):
    """Return flat scientific records; the common builder supplies row IDs/files."""
    output = {}
    source = "DEP3_observed_reach"
    rows = []
    for src in ctx.tables[source]:
        row = _native(source, src, ["result_id"], ["numerator", "denominator"])
        row.update(source_unit=src["unit"], unit="percent", base_unit=src["unit"],
                   probability=src["estimate_probability"] or None,
                   source_base_status=src["denominator_status"])
        _ratio_counts(row["numerator"], row["denominator"])
        _point(row, src["estimate_percent"], row["denominator"], True)
        _no_interval(row, "observed_description_no_interval")
        rows.append(row)
    output["funding_reach"] = {"rows": rows, "filter_fields": ["ownership", "population", "connection_definition", "institute"]}

    coverage = _index(ctx.tables[COVERAGE], CONTENT_BASE_KEY)
    labels = _index(ctx.tables["DEP2_T16_category_labels"], ["outcome", "category"])
    rows = []
    for src in ctx.tables[COUNTS]:
        base = coverage[tuple(src[k] for k in CONTENT_BASE_KEY)]
        if src["connected_n"] != base["eligible_connected_n"] or src["remaining_n"] != base["eligible_remaining_n"]:
            raise ValueError("Content counts and coverage bases disagree")
        label = labels[(src["outcome"], src["category"])]
        for connection in ("connected", "remaining"):
            row = _native(COUNTS, src, CONTENT_KEY,
                          [k for k in src if k.endswith("_n")] + ["category_order", "multi_response"])
            row.update(connection_status=connection, unit="percent", base_unit="outcome-eligible distinct works",
                       probability=src[f"{connection}_probability"] or None,
                       numerator=_integer(src[f"{connection}_category_n"]), denominator=_integer(src[f"{connection}_n"]),
                       category_label=label["display_label"], category_definition=label["definition"],
                       population_before_eligibility=_integer(base["population_n_before_outcome_eligibility"]),
                       eligible_total_n=_integer(base["eligible_total_n"]),
                       coverage_source_table_id=COVERAGE,
                       coverage_source_key=source_row(COVERAGE, base, CONTENT_BASE_KEY)["source_key"],
                       label_source_table_id="DEP2_T16_category_labels",
                       label_source_key=source_row("DEP2_T16_category_labels", label, ["outcome", "category"])["source_key"])
            for key, value in base.items():
                if key.endswith("_json"):
                    row[key] = _structured(value)
                elif key.endswith("_n"):
                    row[key] = _integer(value)
            _ratio_counts(row["numerator"], row["denominator"])
            _point(row, src[f"{connection}_percent"], row["denominator"], True)
            _no_interval(row, "observed_description_no_interval")
            rows.append(row)
    output["funding_content_profiles"] = {
        "rows": rows, "filter_fields": CONTENT_KEY + ["connection_status"],
        "metadata": {"reach_to_content_connection_definition": CONNECTION_CROSSWALK},
    }

    rows = []
    for source in CONTENT:
        for src in ctx.tables[source]:
            if src["metric"] != "content_pp_difference":
                continue
            if src["unit"] != "percentage_points":
                raise ValueError("Observed content contrast has unexpected scale")
            row = _native(source, src, ["target_id"], ["registered_family_size"])
            row.update(source_numerator=src["numerator"],
                       source_denominator=src["denominator"],
                       numerator=_structured(src["numerator"]), denominator=_structured(src["denominator"]),
                       counts=_structured(src["numerator"]), bases=_structured(src["denominator"]),
                       base_role=src["denominator_role"], population=src["reference_population"],
                       probability_difference=src["estimate_probability_or_difference"] or None,
                       direction=src["difference_orientation"], source_status=src["point_status"],
                       source_unavailable_reason=src["unavailable_reason"] or None,
                       source_interval_reason=src["interval_reason"])
            row["source_category_counts_all_groups_json"] = src["category_counts_all_groups_json"]
            row["category_counts_all_groups_json"] = _structured(src["category_counts_all_groups_json"])
            # A difference of differences has four subgroup counts, not one
            # numerator. Its saved estimate remains available independently.
            for field in ("numerator", "counts"):
                row[field + "_status"] = "available" if row[field] is not None else "not_applicable"
                row[field + "_reason"] = None if row[field] is not None else "no_single_numerator_for_difference_of_differences; subgroup counts retained in category_counts_all_groups_json"
            for field in ("denominator", "bases"):
                row[field + "_status"] = "available" if row[field] is not None else "unavailable"
                row[field + "_reason"] = None if row[field] is not None else "not_provided_in_released_source"
            row["category_counts_all_groups_json_status"] = "available" if row["category_counts_all_groups_json"] is not None else "not_applicable"
            row["category_counts_all_groups_json_reason"] = None if row["category_counts_all_groups_json"] is not None else "two_group_contrast_counts_retained_in_numerator"
            _point(row, src["estimate_percent_or_pp"])
            if src["point_status"] != "complete":
                row.update(value=None, value_status="unavailable",
                           unavailable_reason=src["unavailable_reason"] or "not_provided_in_released_source")
            _no_interval(row, "observed_corpus_description_no_inference", "not_applicable")
            rows.append(row)
    output["funding_content_contrasts"] = {
        "rows": rows,
        "filter_fields": ["connection_definition", "ownership", "degree_target", "outcome", "category"],
    }

    source = "DEP3_count_primary_reference"
    fit_registry = _index(ctx.tables["DEP3_count_fit_registry"], ["fit_id"])
    rows = []
    for src in ctx.tables[source]:
        row = _native(source, src, ["result_id"], ["cluster_count"])
        row.update(unit="rate_ratio", log_value=src["log_rate_ratio"],
                   numerator=None, denominator=None,
                   numerator_status="not_applicable", denominator_status="not_applicable",
                   numerator_reason="model_rate_contrast_has_no_empirical_count_numerator",
                   denominator_reason="model_rate_contrast_has_no_empirical_count_denominator",
                   lower_pointwise=src["pointwise95_lower"] or None, upper_pointwise=src["pointwise95_upper"] or None,
                   lower_familywise=src["familywise95_lower"] or None, upper_familywise=src["familywise95_upper"] or None,
                   support_clusters=_integer(src["cluster_count"]),
                   family_adjusted_pvalue=src["bonferroni_family3_pvalue"],
                   funding_contrast="1_to_4_annualized_funded_application_ids_per_FY")
        _point(row, src["rate_ratio"])
        if row["value"] is not None and Decimal(row["value"]) <= 0:
            raise ValueError("Nonpositive rate ratio")
        row.update(lower=row["lower_pointwise"], upper=row["upper_pointwise"],
                   interval_status="available" if row["lower_pointwise"] is not None and row["upper_pointwise"] is not None else "unavailable",
                   interval_unavailable_reason=None if row["lower_pointwise"] is not None and row["upper_pointwise"] is not None else "not_provided_in_released_source")
        for family in ("pointwise", "familywise"):
            lo, hi = row[f"lower_{family}"], row[f"upper_{family}"]
            if lo is not None and hi is not None and row["value"] is not None:
                if not Decimal("0") < Decimal(lo) <= Decimal(row["value"]) <= Decimal(hi):
                    raise ValueError("Invalid saved rate-ratio interval")
        if src["degree_target"] == "Masters minus research doctorate":
            fit_ids = [src["ownership"] + "__common__" + degree for degree in ("doctorate", "masters")]
        else:
            degree = {"Masters": "masters", "Research doctorate": "doctorate"}[src["degree_target"]]
            fit_ids = [src["ownership"] + "__main__" + degree]
        supports = []
        for fit_id in fit_ids:
            support = fit_registry[(fit_id,)]
            if int(support["expected_clusters"]) != row["support_clusters"]:
                raise ValueError("Target support does not match its prescribed fit route")
            supports.append({**support, "expected_cells": int(support["expected_cells"]),
                             "expected_clusters": int(support["expected_clusters"])})
        row.update(fit_ids=canonical_json(fit_ids), fit_support=canonical_json(supports),
                   fit_registry_source_table_id="DEP3_count_fit_registry")
        rows.append(row)
    output["institutional_count_associations"] = {
        "rows": rows, "filter_fields": ["ownership", "degree_target"],
        "metadata": {"virtual_filters": {"interval_family": {
            "values": ["pointwise", "familywise"], "default": "pointwise",
            "description": "Select saved bounds for the same result; point and retained population do not change.",
            "bindings": {"pointwise": {"lower": "lower_pointwise", "upper": "upper_pointwise"},
                         "familywise": {"lower": "lower_familywise", "upper": "upper_familywise"}},
        }}, "default_interval_family": "pointwise"},
    }

    source = "DEP3_investigator_equal_pi_summary"
    measures = {"funded_mean": "mean_funded_works_per_year", "unfunded_mean": "mean_unfunded_works_per_year",
                "paired_difference": "mean_paired_difference_works_per_year"}
    rows = []
    integer_fields = ["PIs", "institutions", "PI_years", "funded_years", "unfunded_years",
                      "funded_qualifying_PI_work_participations", "unfunded_qualifying_PI_work_participations",
                      "increased_PIs", "equal_PIs", "decreased_PIs", "zero_qualifying_years", "zero_all_topic_years",
                      "internal_no_clear_appearance_years", "unknown_historical_ownership_PI_years", "preceding_funding_window_FY"]
    for src in ctx.tables[source]:
        for measure, field in measures.items():
            row = _native(source, src, ["ownership", "degree_group"], integer_fields)
            row.update(measure=measure, source_unit=src["unit"], unit="qualifying_PI_work_participations_per_year",
                       support_PIs=int(src["PIs"]), support_institutions=int(src["institutions"]),
                       denominator=int(src["PIs"]), denominator_unit="PIs", denominator_role="equal_PI_averaging_base",
                       numerator=None, numerator_status="not_applicable",
                       numerator_reason="mean_of_PI_specific_rates_has_no_single_count_numerator",
                       preceding_window=int(src["preceding_funding_window_FY"]),
                       completion_year_excluded=src["completion_FY_excluded"], source_inference=src["inference"])
            _point(row, src[field])
            _no_interval(row, "finite_panel_description_no_inference")
            rows.append(row)
    output["within_pi_participation"] = {"rows": rows, "filter_fields": ["ownership", "degree_group", "measure"]}

    source = "DEP1_coverage_by_mechanism_period_scenario"
    rows = []
    for src in ctx.tables[source]:
        row = _native(source, src, SCENARIO + ["disposition"], ["n", "N"])
        row.update(numerator=row["n"], denominator=row["N"], unit="percent", base_unit=src["counting_unit"])
        _ratio_counts(row["numerator"], row["denominator"])
        _point(row, src["percent"], row["denominator"], True)
        _no_interval(row, "not_provided_for_disposition")
        rows.append(row)
    output["award_frame_disposition"] = {"rows": rows, "filter_fields": SCENARIO + ["disposition"]}

    source = "DEP1_search_capture_by_period_and_scenario"
    rows = []
    for src in ctx.tables[source]:
        for measure, (num_field, base_field, value_field) in CAPTURE_MEASURES.items():
            row = _native(source, src, SCENARIO, [k for k in src if k.endswith(("_n", "_N"))])
            base = _integer(src[base_field]) if base_field else int(src["linked_work_N"]) - int(src["included_work_n"])
            row.update(measure=measure, numerator=_integer(src[num_field]), denominator=base,
                       unit="percent", base_unit="distinct works",
                       interval_type="Wilson95" if measure == "search_capture" else "not_provided_descriptive",
                       numerator_definition=num_field,
                       denominator_definition=base_field or "linked_work_N - included_work_n")
            _ratio_counts(row["numerator"], base)
            _point(row, src[value_field], base, True)
            if base == 0:
                _no_interval(row, "zero_denominator", "unavailable")
            elif measure == "search_capture":
                lo, hi = src["search_capture_wilson95_lower"], src["search_capture_wilson95_upper"]
                row.update(lower=lo or None, upper=hi or None,
                           interval_status="available" if lo and hi else "unavailable",
                           interval_unavailable_reason=None if lo and hi else "not_provided_in_released_source")
                if lo and hi and row["value"] is not None:
                    if not Decimal(lo) <= Decimal(row["value"]) <= Decimal(hi):
                        raise ValueError("Capture interval fails to contain its point")
            else:
                _no_interval(row, "not_supplied_for_measure")
            rows.append(row)
    output["award_search_capture"] = {"rows": rows, "filter_fields": SCENARIO + ["measure"]}
    return output
