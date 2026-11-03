# SPDX-License-Identifier: MIT
"""Deterministic adapters for the eight content and institution datasets.

All inputs are released tables supplied by dashboard_common.load_context().
This module never edits source files or fits models.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib

from dashboard_common import canonical_json, decimal_ratio, source_row


T20 = "DEP2_T20_degree_field_composition"
COUNTS = "DEP2_group_period_category_counts"
T2 = "DEP2_T2_group_support"
T3 = "DEP2_T3_profiles_and_periods"
PAIR = ("DEP2_T4_C3_pairwise", "DEP2_T5_C5_pairwise", "DEP2_T6_C4_pairwise", "DEP2_T7_C8_pairwise")
TEMP = ("DEP2_T8_temporal_changes", "DEP2_T9_continuing_changes")
T10 = "DEP2_T10_institution_profiles"
T12 = "DEP2_T12_institution_support"
T13 = "DEP2_T13_group_period_coverage"
T14 = "DEP2_T14_institution_period_coverage"
T16 = "DEP2_T16_category_labels"
COUNT_KEY = ("outcome", "population", "group_id", "period", "category")
PROFILE_KEY = ("outcome", "unit_id", "category")

_COUNT_NAMES = {
    "distinct_works", "denominator_distinct_works", "selected_works", "eligible_works",
    "eligible_institutions", "category_universe", "category_order", "pair_order",
    "attempted_replicates", "successful_replicates", "display_order", "eligible_coded",
    "coded_unknown_predictors", "known_inapplicable", "undetermined", "missing_content",
    "operationally_incomplete", "invalid_coding", "total_in_scope_works",
}
_COUNT_ENDINGS = (
    "_eligible_works", "_eligible_institutions", "_total_in_scope_works",
    "_institutions", "_distinct_works", "_eligible_n", "_coded_unknown_predictors",
    "_known_inapplicable", "_undetermined", "_missing_content", "_operationally_incomplete",
    "_invalid_coding", "_coded", "_works", "_works_per_repeat_or_late_period",
)


def _copy(row):
    """Preserve decimal tokens and categorical IDs; type only declared count fields."""
    result = {}
    for field, value in row.items():
        if value in ("", None):
            result[field] = None
        elif field in _COUNT_NAMES or field.endswith(_COUNT_ENDINGS):
            result[field] = int(value)
        else:
            result[field] = value
    return result


def _base(table, row, key):
    result = _copy(row)
    result.update(source_row(table, row, list(key)))
    result["source_record_status"] = row.get("status") or None
    result["source_reported_status"] = row.get("source_status") or None
    result["source_report_supported"] = row.get("report_supported") or None
    result["source_interval_status"] = row.get("interval_status") or row.get("status") or row.get("source_status") or None
    result["source_unavailable_reason"] = row.get("unavailable_reason") or None
    return result


def _finite(value):
    if value in (None, ""):
        return False
    try:
        return Decimal(value).is_finite()
    except (InvalidOperation, ValueError):
        return False


def _point(result, value, units, supported=True, reason=None):
    result["support_status"] = "supported" if supported else "unsupported"
    available = supported and _finite(value)
    if available and units == "probability" and not 0 <= Decimal(value) <= 1:
        raise ValueError("Supported fitted probability outside [0,1]")
    result["value"] = value if available else None
    result["units"] = units
    result["value_status"] = "available" if available else ("unavailable" if not supported else "missing")
    result["unavailable_reason"] = None if available else (reason or ("unsupported_source_target" if not supported else "not_provided_in_released_source"))
    return available


def _no_interval(result, reason="not_provided_descriptive"):
    result.update(lower=None, upper=None, interval_status="not_computed", interval_reason=reason)


def _saved_interval(result, row, lower="lower", upper="upper"):
    result["source_lower"] = row.get(lower) or None
    result["source_upper"] = row.get(upper) or None
    available = result["value_status"] == "available" and _finite(row.get(lower)) and _finite(row.get(upper))
    if available:
        if Decimal(row[lower]) > Decimal(row[upper]):
            raise ValueError("Saved interval endpoints reversed")
        result.update(lower=row[lower], upper=row[upper], interval_status="available", interval_reason=None)
    else:
        result.update(lower=None, upper=None, interval_status="unavailable",
                      interval_reason=row.get("unavailable_reason") or row.get("failure_reason") or result.get("source_interval_status") or "not_provided_in_released_source")


def _no_empirical_base(result):
    result.update(numerator=None, denominator=None, denominator_status="not_applicable",
                  denominator_reason="fitted_or_derived_target_has_no_empirical_work_denominator")


def _index(rows, fields):
    index = {}
    for row in rows:
        key = tuple(row[f] for f in fields)
        if key in index:
            raise ValueError(f"Non-unique join on {fields}: {key}")
        index[key] = row
    return index


def _labels(result, row, labels):
    label = labels[(row["outcome"], row["category"])]
    result.update(category_label=label["display_label"], category_order=int(label["category_order"]),
                  category_definition=label["definition"])


def _group_context(result, row, groups):
    group_id = row.get("group_id") or row["unit_id"]
    group = groups[(row["outcome"], group_id)]
    result.update(group_id=group_id, degree_group=group["degree_group"], field_code=group["field_code"], field_label=group["field_label"])
    result["group_support_context"] = canonical_json(_copy(group))


def _support_counts(row, continuing=False):
    prefix = ("shared_" if continuing else "primary_") if row["outcome"] in ("C3", "C5") else ""
    return {name: (int(row[prefix + name]) if row.get(prefix + name) else None)
            for name in ("early_eligible_works", "late_eligible_works", "early_institutions", "late_institutions")}


def _population(ctx):
    output = []
    for row in ctx.tables[T20]:
        result = _base(T20, row, ("degree_group", "field_code"))
        _point(result, row["share_of_all_works_percent"], "percent")
        result.update(numerator=int(row["distinct_works"]), denominator=int(row["denominator_distinct_works"]),
                      source_status=row["cell_status"], estimate_type="observed_empirical_composition")
        _no_interval(result)
        output.append(result)
    return {"rows": output, "filter_fields": ["degree_group", "field_code"]}


def _observed(ctx, groups, labels):
    coverage = _index(ctx.tables[T13], ("outcome", "group_id", "period"))
    output = []
    for row in ctx.tables[COUNTS]:
        result = _base(COUNTS, row, COUNT_KEY)
        numerator, denominator = int(row["selected_works"]), int(row["eligible_works"])
        if not 0 <= numerator <= denominator:
            raise ValueError("Invalid observed numerator/base")
        supported = row["report_supported"] == "1" and denominator > 0
        value = decimal_ratio(numerator, denominator) if supported else None
        _point(result, value, "percent", supported, row["unavailable_reason"] or "no_positive_eligible_base")
        result.update(numerator=numerator, denominator=denominator, estimate_type="observed_category_proportion")
        _group_context(result, row, groups)
        _labels(result, row, labels)
        if row["population"] == "primary":
            result["coverage_context"] = canonical_json(_copy(coverage[(row["outcome"], row["group_id"], row["period"])]))
            result["coverage_context_source"] = T13
        else:
            result["coverage_context"] = canonical_json({"eligible_works": denominator, "eligible_institutions": int(row["eligible_institutions"]), "population": "continuing"})
            result["coverage_context_source"] = COUNTS
        _no_interval(result)
        output.append(result)
    return {"rows": output, "filter_fields": list(COUNT_KEY)}


def _observed_differences(ctx, labels):
    strata = defaultdict(list)
    for row in ctx.tables[COUNTS]:
        strata[tuple(row[k] for k in ("outcome", "population", "period", "category"))].append(row)
    output = []
    for (outcome, population, period, category), members in sorted(strata.items()):
        for a in sorted(members, key=lambda r: r["group_id"]):
            for b in sorted(members, key=lambda r: r["group_id"]):
                if a["group_id"] == b["group_id"]:
                    continue
                numerator_a, numerator_b = int(a["selected_works"]), int(b["selected_works"])
                denominator_a, denominator_b = int(a["eligible_works"]), int(b["eligible_works"])
                supported = a["report_supported"] == b["report_supported"] == "1" and min(denominator_a, denominator_b) > 0
                # Form one exact integer rational before the 34-digit division.
                value = decimal_ratio(numerator_a * denominator_b - numerator_b * denominator_a,
                                      denominator_a * denominator_b) if supported else None
                pa, pb = source_row(COUNTS, a, list(COUNT_KEY)), source_row(COUNTS, b, list(COUNT_KEY))
                result = {"outcome": outcome, "population": population, "period": period, "category": category,
                          "group_a": a["group_id"], "group_b": b["group_id"], "numerator_a": numerator_a,
                          "numerator_b": numerator_b, "denominator_a": denominator_a, "denominator_b": denominator_b,
                          "eligible_institutions_a": int(a["eligible_institutions"]), "eligible_institutions_b": int(b["eligible_institutions"]),
                          "source_table_id": COUNTS, "source_key_a": pa["source_key"], "source_key_b": pb["source_key"],
                          "source_key": canonical_json([pa["source_key"], pb["source_key"]]),
                          "source_support_status_a": a["report_supported"], "source_support_status_b": b["report_supported"],
                          "source_unavailable_reason_a": a["unavailable_reason"] or None,
                          "source_unavailable_reason_b": b["unavailable_reason"] or None,
                          "estimate_type": "derived_descriptive_difference", "difference_direction": "group_a_minus_group_b"}
                _point(result, value, "percentage_points", supported, "one_or_both_observed_operands_unavailable")
                _labels(result, a, labels)
                _no_interval(result, "not_computed_descriptive_difference")
                output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "population", "period", "group_a", "group_b", "category"],
            "metadata": {"comparison_policy": "All ordered distinct pairs with shared actual outcome/population/period/category source rows; separate operand bases retained."}}


def _fitted(ctx, groups, labels):
    output = []
    for row in ctx.tables[T3]:
        result = _base(T3, row, ("estimand_id",))
        _point(result, row["estimate"], "probability", row["report_supported"] == "1", row["unavailable_reason"])
        result.update(profile_id=row["estimand_id"], estimate_type="saved_fitted_profile")
        _group_context(result, row, groups)
        _labels(result, row, labels)
        result["support_counts_by_outcome"] = canonical_json(_support_counts(row))
        _no_empirical_base(result)
        _saved_interval(result, row)
        output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "group_id", "family", "category"]}


def _contrasts(ctx, labels):
    output = []
    for table in PAIR:
        for row in ctx.tables[table]:
            result = _base(table, row, ("estimand_id",))
            _point(result, row["difference_pp"], "percentage_points", row["report_supported"] == "1", row["unavailable_reason"])
            result.update(contrast_id=row["estimand_id"], a_profile_percent=row["group_a_profile_pct"],
                          b_profile_percent=row["group_b_profile_pct"], display_direction="stored",
                          difference_direction="group_a_minus_group_b", estimate_type="saved_paired_fitted_contrast")
            _labels(result, row, labels)
            _no_empirical_base(result)
            _saved_interval(result, row, "lower_95_pp", "upper_95_pp")
            output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "pair_id", "category", "display_direction"],
            "metadata": {"display_direction": "stored only; reversed copies are not generated"}}


def _temporal(ctx, groups, labels):
    output = []
    for table in TEMP:
        continuing = table == TEMP[1]
        for row in ctx.tables[table]:
            result = _base(table, row, ("estimand_id",))
            _point(result, row["estimate"], "percentage_points", row["report_supported"] == "1", row["unavailable_reason"])
            result.update(analysis_population="continuing" if continuing else "primary",
                          period_direction="2017-2023_minus_2010-2016", estimate_type="saved_paired_temporal_change")
            _group_context(result, row, groups)
            _labels(result, row, labels)
            result["support_counts_by_outcome_and_source"] = canonical_json(_support_counts(row, continuing))
            _no_empirical_base(result)
            _saved_interval(result, row)
            output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "analysis_population", "group_id", "category"]}


def _institution_profiles(ctx, labels):
    support = _index(ctx.tables[T12], ("outcome", "institution_id"))
    coverage = defaultdict(list)
    for r in ctx.tables[T14]:
        coverage[(r["outcome"], r["institution_id"])].append(_copy(r))
    output = []
    for row in ctx.tables[T10]:
        key = row["outcome"], row["unit_id"]
        s = support[key]
        result = _base(T10, row, PROFILE_KEY)
        result["source_embedded_institution_id"] = row["institution_id"] or None
        result.update(institution_id=row["unit_id"], institution_name=s["institution_name"],
                      early_eligible_works=int(s["early_eligible_works"]), late_eligible_works=int(s["late_eligible_works"]),
                      source_institution_support=s["profile_supported"], estimate_type="saved_institutional_fitted_profile")
        valid = row["report_supported"] == s["profile_supported"] == "1"
        _point(result, row["estimate"], "probability", valid, row["unavailable_reason"])
        result["point_support"] = result["support_status"]
        _labels(result, row, labels)
        result["coverage"] = canonical_json(sorted(coverage[key], key=lambda r: r["period"]))
        _no_empirical_base(result)
        _saved_interval(result, row)
        output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "institution_id", "category"],
            "filter_aliases": {"institution_selection": "institution_id", "category_visibility": "category"}}


def _institution_benchmark(ctx, labels):
    spec = ctx.scope["institution_benchmark"]
    roster = spec["cohort"]["institution_ids"]
    roster_hash = hashlib.sha256(("\n".join(sorted(roster)) + "\n").encode("utf-8")).hexdigest()
    if len(roster) != 50 or len(set(roster)) != 50 or roster_hash != spec["cohort"]["roster_sha256"]:
        raise ValueError("Fixed institution roster differs from scope")
    support = _index(ctx.tables[T12], ("outcome", "institution_id"))
    points = _index(ctx.tables[T10], PROFILE_KEY)
    output = []
    for outcome, category in sorted(labels):
        members, unavailable = [], []
        for institution in roster:
            row = points.get((outcome, institution, category))
            s = support.get((outcome, institution))
            if not row or not s or s["profile_supported"] != "1" or row["report_supported"] != "1" or not _finite(row["estimate"]):
                unavailable.append(institution)
            if row:
                members.append(row)
        valid = not unavailable and len(members) == 50
        value = None
        if valid:
            with localcontext() as decimal_context:
                decimal_context.prec = 34
                decimal_context.rounding = ROUND_HALF_EVEN
                total = sum((Decimal(r["estimate"]) for r in members), Decimal(0))
                value = decimal_ratio(total, 50, multiplier=1)
        refs = [source_row(T10, r, list(PROFILE_KEY)) for r in members]
        result = {"benchmark_id": spec["benchmark_id"], "outcome": outcome, "category": category,
                  "cohort_n": 50, "cohort_hash": roster_hash, "valid_member_n": 50 - len(unavailable),
                  "member_weight": "0.02", "member_source_rows": canonical_json(refs),
                  "unavailable_member_ids": canonical_json(unavailable), "source_table_id": T10,
                  "source_key": canonical_json([outcome, category, roster_hash]),
                  "estimate_type": "derived_descriptive_mean_of_fitted_profiles"}
        _point(result, value, "probability", valid, "fixed_cohort_member_point_unavailable")
        if not valid:
            result["value_status"] = "unavailable"
        _labels(result, {"outcome": outcome, "category": category}, labels)
        _no_empirical_base(result)
        _no_interval(result, "not_computed_descriptive_reference")
        output.append(result)
    return {"rows": output, "filter_fields": ["outcome", "category"],
            "filter_aliases": {"category_visibility": "category"},
            "metadata": {"fixed_roster_sha256": roster_hash, "cohort_n": 50, "selection_invariant": True}}


def build(ctx):
    """Return flat records with source precision and explicit availability."""
    groups = _index(ctx.tables[T2], ("outcome", "group_id"))
    labels = _index(ctx.tables[T16], ("outcome", "category"))
    return {
        "population_composition": _population(ctx),
        "content_observed": _observed(ctx, groups, labels),
        "content_observed_difference": _observed_differences(ctx, labels),
        "content_fitted": _fitted(ctx, groups, labels),
        "content_fitted_contrasts": _contrasts(ctx, labels),
        "content_temporal_changes": _temporal(ctx, groups, labels),
        "institution_profiles": _institution_profiles(ctx, labels),
        "institution_benchmark": _institution_benchmark(ctx, labels),
    }
