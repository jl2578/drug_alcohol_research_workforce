# Dashboard data contract

Version 1.0.0 · 2 November 2026. This specifies the included views in the [scope decisions](dashboard_scope.md). The specification is implemented by the [Step 5 build](dashboard_build.md); its [receipt](../dashboard/metadata/build.json) records generated outputs. The [JSON contract](dashboard_data_contract.json) contains exact source keys, field bindings, transformations, checksums, reuse notices and download routes.

## Shared rules

- Keep identifiers as strings and preserve source decimal tokens. Exact counts stay integers; derived quantities use 34-digit decimal arithmetic. Round only for display.
- Generate CSV and JSON from the same records. Nulls need a status/reason; zero remains zero. Preserve unsupported, suppressed, instrument U, unclassifiable and unscored states separately.
- Each dataset has a declared row grain and semantic key. Generate row_id deterministically from the dataset ID and ordered key values; sorting or filtering must not change it.
- Category selection never changes a denominator. Each comparison retains both populations and bases. Only actual released combinations are valid.
- Saved contrast limits come from the paired contrast source. Never subtract marginal bounds. Point availability and interval availability are separate.
- Carry source IDs, component versions, hashes and transformation version into the download manifest. Derived rows retain their contributing keys or pinned cohort reference.
- Preserve source-specific reuse notices and link the corresponding original table/container. Neither a transformation nor a code license relicenses empirical data.

## Dataset specifications

| Dataset | View(s) | One row | Stable key |
|---|---|---|---|
| [population_composition](#population-composition) | population_composition | One presentation credential group × adopted field cell in the full study corpus. | ["degree_group", "field_code"] |
| [content_observed](#content-observed) | content_observed | One outcome × primary/continuing population × supported degree-field group × completion-period bin × category. | ["outcome", "population", "group_id", "period", "category"] |
| [content_observed_difference](#content-observed-difference) | content_observed_difference | One ordered comparison of two released observed groups at the same outcome, population, period and category. | ["outcome", "population", "period", "group_a", "group_b", "category"] |
| [content_fitted](#content-fitted) | content_fitted | One saved early, late or equal-period standardized fitted profile target for an outcome, group and category. | ["source_table_id", "estimand_id"] |
| [content_fitted_contrasts](#content-fitted-contrasts) | content_fitted_contrasts | One saved ordered fitted-profile group contrast for an outcome and category. | ["source_table_id", "estimand_id"] |
| [content_temporal_changes](#content-temporal-changes) | content_temporal_changes | One saved later-minus-earlier fitted change for outcome, group, category and primary/continuing analysis. | ["source_table_id", "estimand_id"] |
| [institution_profiles](#institution-profiles) | institution_profiles | One saved fitted profile point for a fixed-roster institution, outcome and category. | ["outcome", "institution_id", "category"] |
| [institution_benchmark](#institution-benchmark) | institution_benchmark | One descriptive average fitted probability across the fixed 50 institutions for an outcome/category. | ["benchmark_id", "outcome", "category"] |
| [funding_reach](#funding-reach) | funding_reach | One saved identified-connection share for one ownership population, credential population, connection definition and institute. | ["result_id"] |
| [funding_content_profiles](#funding-content-profiles) | funding_content_profiles | One observed outcome-category percentage for a degree and connection-status series, within an ownership population and connection definition. | ["connection_definition", "ownership", "degree_target", "outcome", "category", "connection_status"] |
| [funding_content_contrasts](#funding-content-contrasts) | funding_content_profiles | One saved observed connected-minus-remaining difference, or its saved Masters-minus-research-doctorate difference of differences, per connection definition/ownership/outcome/category. | ["source_table_id", "target_id"] |
| [institutional_count_associations](#institutional-count-associations) | institutional_count_association | One saved adopted institutional count-model target per ownership population and degree target, with both saved interval families on the same record. | ["result_id"] |
| [within_pi_participation](#within-pi-participation) | within_pi_participation | One saved mean or paired mean difference for one ownership population and degree; three measure records are produced from each source row. | ["ownership", "degree_group", "measure"] |
| [award_frame_disposition](#award-frame-disposition) | student_award_frame_coverage | One disposition share for one award-frame extension/match/mechanism/completion-period scenario. | ["extension_years", "match_definition", "mechanism_group", "completion_period", "disposition"] |
| [award_search_capture](#award-search-capture) | student_award_search_capture | One named capture/inclusion/nonretrieval measure for one extension/match/mechanism/completion-period scenario, with its own numerator/base. | ["extension_years", "match_definition", "mechanism_group", "completion_period", "measure"] |
| [employment_roles](#employment-roles) | employment_roles | One detailed degree × specification × joint role state × denominator basis. | ["degree_group", "specification", "joint_state", "basis"] |
| [employment_occupations](#employment-occupations) | employment_occupations | One detailed degree × occupation reporting status × released SOC instrument code. | ["degree_group", "occupation_status", "soc_unit_code"] |
| [outside_destinations](#outside-destinations) | outside_destinations | One pooled degree × grouped outside destination, after verified collapse of repeated role/specification totals. | ["degree_group", "destination_dimension", "destination"] |
| [outside_roles](#outside-roles) | outside_roles | One pooled degree × destination or All outside × specification × role state × denominator basis. | ["source_table_id", "source_key", "basis"] |
| [employment_connection_profiles](#employment-connection-profiles) | employment_connection_profiles | One pooled degree × identified connection group × available specification × role state. | ["degree_group", "connection_clear", "specification", "state"] |
| [destination_connection](#destination-connection) | destination_connection | One Research-doctorate destination dimension × group × specification, carrying the paired connection proportions and their saved difference. | ["degree_group", "dimension", "group", "specification"] |
| [destination_saved_contrasts](#destination-saved-contrasts) | destination_saved_contrasts | One saved result family × specification; each family retains its native paired measures and methodological context. | ["source_table_id", "specification"] |
| [employment_sensitivities](#employment-sensitivities) | employment_sensitivities | One source-specific saved sensitivity row, identified by its original ordered scenario/degree/role keys. | ["source_table_id", "source_key"] |
| [outside_occupation_breakdowns](#outside-occupation-breakdowns) | outside_occupation_breakdowns | One released occupation row within its exact degree/role/destination breakdown; no new intersections. | ["source_table_id", "source_key"] |
| [rc_rmi_lookup](#rc-rmi-lookup) | rc_rmi_lookup | One potential canonical occupation × canonical industry pair under one frozen scoring specification. | ["specification", "soc_code_canonical", "naics_code_canonical"] |
| [table_catalog](#table-catalog) | table_catalog | One released catalog entry, including numeric tables, metadata entries and detailed display snapshots. | ["table"] |

<a id="population-composition"></a>

### population_composition

**Population and period:** All 13,227 distinct in-scope scientific works; all six presentation credential groups and field-unavailable retained. Full study completion window 2010–2023; not period-filterable.

**Measure:** observed_empirical_composition. Units: Count: distinct works; estimate: percent of all corpus works.

**Base and weighting:** numerator: DEP2_T20_degree_field_composition.distinct_works Denominator: DEP2_T20_degree_field_composition.denominator_distinct_works (13,227 for every row) Weighting: One contribution per distinct work. No model or period weights.

**Filters:** degree_group, field_code. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** not_provided_descriptive. No confidence interval or significance test is added.

**Transformation:** `population_composition_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T20_degree_field_composition`](../training_workforce_evidence/TABLES.html#table-dep2-t20-degree-field-composition) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="content-observed"></a>

### content_observed

**Population and period:** Outcome-eligible distinct works in the selected primary or continuing-institution population and released supported degree-field group. 2010–2016 or 2017–2023 exactly as source period.

**Measure:** observed_category_proportion. Units: Percent of outcome-eligible works; counts in distinct works and eligible institutions.

**Base and weighting:** numerator: DEP2_group_period_category_counts.selected_works Denominator: DEP2_group_period_category_counts.eligible_works; eligible_institutions is coverage, not the percentage denominator. Weighting: Observed period-specific work counts. period_weight=0.5 is not applied to these observed percentages.

**Filters:** outcome, population, group_id, period, category. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** not_provided_descriptive. No interval or p-value inferred from these count margins.

**Transformation:** `content_observed_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_group_period_category_counts`](../training_workforce_evidence/TABLES.html#table-dep2-group-period-category-counts) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="content-observed-difference"></a>

### content_observed_difference

**Population and period:** Two separate outcome-eligible group populations; not a pooled group or new joint sample. One common released period bin for both operands.

**Measure:** derived_descriptive_difference. Units: Percentage points, A minus B.

**Base and weighting:** numerator: {"A": "count_A.selected_works", "B": "count_B.selected_works"} Denominator: {"A": "count_A.eligible_works", "B": "count_B.eligible_works"} Weighting: Compute each observed proportion with its own work base, then subtract. No period weights.

**Filters:** outcome, population, period, group_a, group_b, category. A and B must be distinct released groups with rows for the same outcome/population/period/category; only their common supported categories may be compared.

**Uncertainty:** not_computed_descriptive_difference. No confidence interval, p-value or significance from independent count margins.

**Transformation:** `content_observed_difference_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_group_period_category_counts`](../training_workforce_evidence/TABLES.html#table-dep2-group-period-category-counts) — two profile operands selected from this table
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="content-fitted"></a>

### content_fitted

**Population and period:** The source target group, subject to outcome-specific model support; unsupported registry targets remain identifiable. family early_profile=2010–2016; late_profile=2017–2023; standardized_profile=equal fitted period weights.

**Measure:** saved_fitted_profile. Units: Stored probability. Display percentage=100*estimate; scale reportable interval endpoints identically.

**Base and weighting:** numerator: null Denominator: {"meaning": "No empirical denominator for a fitted probability. Retain outcome-specific early/late work and institution counts as support metadata.", "source_layout": {"C3_C5": "primary_early_eligible_works, primary_late_eligible_works, primary_early_institutions, primary_late_institutions", "C4_C8": "early_eligible_works, late_eligible_works, early_institutions, late_institutions"}} Weighting: Saved fitted estimates; standardized profiles average earlier/later probabilities with equal weights. No work-count reweighting.

**Filters:** outcome, group_id, family, category. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** saved_conditional_pointwise_95. Use reportable lower/upper only when both supplied and reportable; never replace with diagnostic bounds. Convert probability bounds to percentage together with point.

**Transformation:** `content_fitted_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T3_profiles_and_periods`](../training_workforce_evidence/TABLES.html#table-dep2-t3-profiles-and-periods) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="content-fitted-contrasts"></a>

### content_fitted_contrasts

**Population and period:** Saved supported pair comparisons of standardized fitted group profiles; preserve each group and its own early/late support bases. Combined equal-period standardized profiles; no period selector.

**Measure:** saved_paired_fitted_contrast. Units: Percentage points already; generic source scale is blank and must not be used to infer probability units.

**Base and weighting:** numerator: null Denominator: {"meaning": "No pooled empirical denominator for fitted contrast. Retain separate A/B early/late eligible works and institutions.", "fields": ["group_a_early_eligible_works", "group_a_late_eligible_works", "group_b_early_eligible_works", "group_b_late_eligible_works", "group_a_early_institutions", "group_a_late_institutions", "group_b_early_institutions", "group_b_late_institutions"]} Weighting: Saved equal-period profile contrast; retain paired resampling inference.

**Filters:** outcome, pair_id, category, display_direction. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** saved_paired_conditional_pointwise_95. Use these exact paired bounds. Generic lower/upper/status may be blank. Never subtract marginal profile bounds; no simultaneous/multiplicity correction is implied.

**Transformation:** `content_fitted_contrasts_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T4_C3_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t4-c3-pairwise) — primary numerical rows
- [`DEP2_T5_C5_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t5-c5-pairwise) — primary numerical rows
- [`DEP2_T6_C4_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t6-c4-pairwise) — primary numerical rows
- [`DEP2_T7_C8_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t7-c8-pairwise) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="content-temporal-changes"></a>

### content_temporal_changes

**Population and period:** Primary population in T8; continuing-institution sensitivity in T9. These are distinct source targets. 2017–2023 minus 2010–2016 only.

**Measure:** saved_paired_temporal_change. Units: Percentage points already; copy scale=percentage_points without a further factor of 100.

**Base and weighting:** numerator: null Denominator: {"meaning": "No empirical denominator for the fitted change. Attach each source row’s early/late eligible work and institution counts as support metadata.", "source_layout": {"primary_C3_C5": "primary_* early/late work and institution fields", "continuing_C3_C5": "shared_* early/late work and institution fields", "C4_C8_both_tables": "unprefixed early_eligible_works, late_eligible_works, early_institutions, late_institutions"}} Weighting: Saved paired temporal contrast within the declared primary or continuing-institution analysis.

**Filters:** outcome, analysis_population, group_id, category. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** saved_paired_conditional_pointwise_95. Retain paired reportable temporal limits; missing reportable limits remain missing. Do not construct them by subtracting early/late marginal limits.

**Transformation:** `content_temporal_changes_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T8_temporal_changes`](../training_workforce_evidence/TABLES.html#table-dep2-t8-temporal-changes) — primary numerical rows
- [`DEP2_T9_continuing_changes`](../training_workforce_evidence/TABLES.html#table-dep2-t9-continuing-changes) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="institution-profiles"></a>

### institution_profiles

**Population and period:** The fixed 50 institutional contributors; saved profiles retain their degree/field composition. Saved period-standardized profile combining 2010–2016 and 2017–2023 equally; no profile period filter.

**Measure:** saved_institutional_fitted_profile. Units: Stored probability; display percent=100*estimate with saved bounds scaled identically.

**Base and weighting:** numerator: null Denominator: {"meaning": "No empirical denominator for the fitted probability. T12 early_eligible_works/late_eligible_works and T14 coverage are explanatory counts only.", "T12_fields": ["early_eligible_works", "late_eligible_works"], "T14_fields": ["period", "total_in_scope_works", "eligible_coded"]} Weighting: Saved equal-period institutional fitted probabilities; no work-count reweighting or refitting.

**Filters:** outcome, institution_selection, category_visibility. Use only combinations present in the selected released primary table; never construct the Cartesian product of independent levels.

**Uncertainty:** saved_conditional_pointwise_95. Display supplied reportable bounds only. All 2,200 points remain valid, including 60 with missing interval bounds; diagnostic bounds are not replacements.

**Transformation:** `institution_profiles_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T10_institution_profiles`](../training_workforce_evidence/TABLES.html#table-dep2-t10-institution-profiles) — primary numerical rows
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="institution-benchmark"></a>

### institution_benchmark

**Population and period:** Exactly the pinned 50-member T12 cohort, identical across all four outcomes; selected institutions remain included. Same saved period-standardized fitted profiles as the institutional view; no period filter.

**Measure:** derived_descriptive_mean_of_fitted_profiles. Units: Stored probability; display percentage=100*fixed mean.

**Base and weighting:** numerator: null Denominator: {"aggregation_divisor": 50, "meaning": "50 is the equal-institution mean divisor, not an empirical work denominator. No pooled work numerator/base exists."} Weighting: Exactly 1/50 per pinned institution; no work weighting, refitting or selection-dependent weights.

**Filters:** outcome, category_visibility. Only released outcome/category combinations with all 50 pinned member points are numeric; institution selection does not filter the aggregation.

**Uncertainty:** not_computed_descriptive_reference. No benchmark confidence interval, significance test, or institution-minus-benchmark interval from marginal profile limits.

**Transformation:** `institution_benchmark_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP2_T10_institution_profiles`](../training_workforce_evidence/TABLES.html#table-dep2-t10-institution-profiles) — 50 member operands per output row
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="funding-reach"></a>

### funding_reach

**Population and period:** Distinct adopted works in the source population and ownership frame; default population is Masters or Research doctorate, with other released credential totals separately labelled. Fixed study population and source connection timing; no user-selectable year or period.

**Measure:** observed_descriptive_share. Units: percent for display; probability companion; distinct adopted works for counts.

**Base and weighting:** numerator: DEP3_observed_reach.numerator: distinct works with the named identified connection. Denominator: DEP3_observed_reach.denominator: all distinct works in the selected ownership/credential population. Preserve denominator_status and unit. Weighting: Each distinct work once. Do not add overlapping NIDA/NIAAA or credential total/component populations.

**Filters:** ownership, population, connection_definition, institute. Choose actual tuples present in DEP3_observed_reach. Default connection_definition=combined_clear and institute=NIDA/NIAAA. PI_only and combined_clear_or_possible are labelled sensitivities.

**Uncertainty:** none_observed_description. Preserve raw not_added_observed_descriptive in source_interval_status. Canonical interval_status=not_computed; interval_unavailable_reason=observed_description_no_interval. Do not fabricate bounds.

**Transformation:** `funding_reach_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP3_observed_reach`](../training_workforce_evidence/TABLES.html#table-dep3-observed-reach) — primary numerical source

<a id="funding-content-profiles"></a>

### funding_content_profiles

**Population and period:** Outcome-eligible distinct works within each degree and connected/remaining group; excluded coding states remain coverage metadata. Fixed released study population; no period selector.

**Measure:** observed_descriptive_profile. Units: percent and probability; distinct works for count/base.

**Base and weighting:** numerator: connection_status=connected uses connected_category_n; remaining uses remaining_category_n. Denominator: connection_status=connected uses connected_n; remaining uses remaining_n. These are separate outcome-eligible bases, fixed when categories change. Weighting: Pooled distinct works within each eligible series, not equal institutions or equal PIs; C8 is multi-response.

**Filters:** connection_definition, ownership, degree_target, outcome, category, connection_status. Use only source row tuples; expand each row to connected and remaining. Default primary_combined. Explicit reach-to-content crosswalk: combined_clear→primary_combined; PI_only→PI_component; combined_clear_or_possible→award_possible_sensitivity.

**Uncertainty:** none_observed_description. Canonical interval_status=not_computed and interval_unavailable_reason=observed_description_no_interval; no confidence limits or significance are supplied for this observed profile.

**Transformation:** `funding_content_profiles_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP3/other_rq3/reach_content/data/NA38_T4_D_observed_counts.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na38-t4-d-observed-counts-csv) — primary numerical source
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="funding-content-contrasts"></a>

### funding_content_contrasts

**Population and period:** The source reference_population and degree_target; direct degree contrasts use four distinct outcome-eligible connection-by-degree groups. Fixed released study population; no period selector.

**Measure:** saved_observed_descriptive_contrast. Units: percentage_points; probability_difference companion.

**Base and weighting:** numerator: Preserve the two/four named source numerator counts as a canonical structured-cell JSON string in both CSV and JSON under the shared serialization rule; it is not one scalar numerator. Denominator: Preserve the two/four named source denominator bases as a canonical structured-cell JSON string in both CSV and JSON, along with denominator_role. Do not combine connection-by-degree bases. Weighting: Differences of separately pooled observed subgroup shares; no fitted adjustment.

**Filters:** connection_definition, ownership, degree_target, outcome, category. Select actual saved contrast tuples. Masters minus research doctorate means (Masters connected−remaining)−(research doctorate connected−remaining), not a raw degree gap.

**Uncertainty:** none_observed_description. All source bounds are blank. Preserve not_applicable_observed_corpus_description in source_interval_status; canonical interval_status=not_applicable and interval_unavailable_reason=observed_corpus_description_no_inference.

**Transformation:** `funding_content_contrasts_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP3_observed_content`](../training_workforce_evidence/TABLES.html#table-dep3-observed-content) — saved descriptive contrasts
- [`DEP3/other_rq3/reach_content/data/NA40_T4_D_award_possible_sensitivity.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na40-t4-d-award-possible-sensitivity-csv) — saved descriptive contrasts
- [`DEP3/other_rq3/reach_content/data/NA41_T4_D_PI_component_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na41-t4-d-pi-component-profiles-csv) — saved descriptive contrasts
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="institutional-count-associations"></a>

### institutional_count_associations

**Population and period:** Target-specific retained institutions and degree cells. Separate-degree targets use their main retained populations; the direct degree contrast uses its own common retained population. Fixed fitted analysis window and degree-specific preceding funding exposure; no selectable period or arbitrary funding increment.

**Measure:** saved_model_rate_ratio_or_ratio_of_rate_ratios. Units: rate_ratio (positive, reference 1); log_rate_ratio and percent_change companions.

**Base and weighting:** numerator: Not an observed count ratio; no empirical numerator is assigned to rate_ratio. Denominator: Not an observed count ratio. cluster_count and expected_cells/expected_clusters describe fit support only. Weighting: Saved institutional count-model estimates; no browser pooling, refitting or work-weighted aggregation.

**Filters:** ownership, degree_target, interval_family. Only the six saved ownership×degree_target tuples. Interval selector switches bounds, not points/population. Keep the source contrast orientation; no reverse or arbitrary funding-change control.

**Uncertainty:** saved_95_percent_pointwise_or_familywise. User interval family chooses the corresponding saved lower/upper pair for the same result_id. Direct degree target has its own interval.

**Transformation:** `institutional_count_associations_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP3_count_primary_reference`](../training_workforce_evidence/TABLES.html#table-dep3-count-primary-reference) — primary numerical source
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="within-pi-participation"></a>

### within_pi_participation

**Population and period:** Paired investigators in the released finite-panel summary, with both relevant funded and unfunded-year histories under the source design. Fixed source panel. Preserve preceding_funding_window_FY (5 research doctorate, 2 Masters) and completion_FY_excluded.

**Measure:** saved_finite_panel_equal_pi_mean_or_paired_difference. Units: qualifying PI-work participations per year, averaged equally across PIs; paired_difference uses the same rate units.

**Base and weighting:** numerator: No single pooled numerator reconstructs the saved equal-PI mean. funded/unfunded_qualifying_PI_work_participations remain context, not mean numerators. Denominator: PIs is the equal-weight averaging base. PI_years/funded_years/unfunded_years are contextual exposure totals, not divisors of the saved means. Weighting: Equal PI weights; a shared work may contribute once for each investigator. Do not substitute pooled works/years.

**Filters:** ownership, degree_group, measure. Only actual ownership×degree pairs. Measures are funded_mean, unfunded_mean and paired_difference; compare funded/unfunded means separately from the signed difference.

**Uncertainty:** none_finite_panel_description. Preserve inference in source_inference. Canonical interval_status=not_computed and interval_unavailable_reason=finite_panel_description_no_inference. Quantiles/ranges are not confidence intervals.

**Transformation:** `within_pi_participation_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP3_investigator_equal_pi_summary`](../training_workforce_evidence/TABLES.html#table-dep3-investigator-equal-pi-summary) — primary numerical source

<a id="award-frame-disposition"></a>

### award_frame_disposition

**Population and period:** Distinct matched frame-eligible thesis/dissertation works, under the selected award frame scenario; not award records or people. Source completion_period values: all (2010–2023), 2010–2013, 2014–2017, 2018–2023. These are separate from research-content period bins.

**Measure:** observed_descriptive_disposition_share. Units: percent; distinct matched frame-eligible works for counts.

**Base and weighting:** numerator: Source n (lowercase), the disposition count. Denominator: Source N (uppercase), the scenario base repeated across disposition rows; never sum it over dispositions. Weighting: Each distinct work once within the chosen scenario. Mechanisms and match/timing scenarios overlap and are not additive.

**Filters:** extension_years, match_definition, mechanism_group, completion_period, disposition. Use only complete source tuples. Default extension_years=3, match_definition=clear, disposition=included. All_mechanisms and F30_F31 overlap their component groups.

**Uncertainty:** none_supplied. Canonical interval_status=not_computed and interval_unavailable_reason=not_provided_for_disposition. Search-capture Wilson limits cannot transfer to inclusion/disposition shares.

**Transformation:** `award_frame_disposition_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP1_coverage_by_mechanism_period_scenario`](../training_workforce_evidence/TABLES.html#table-dep1-coverage-by-mechanism-period-scenario) — primary numerical source

<a id="award-search-capture"></a>

### award_search_capture

**Population and period:** Distinct linked award-frame works and the named nested retrieved/assessable/included subsets. Every measure labels its own base. Use the award-specific source completion_period bins, not the research-content bins; all denotes the full 2010–2023 span.

**Measure:** observed_share_with_measure_specific_interval. Units: percent; distinct works for counts.

**Base and weighting:** numerator: {"search_capture": "candidate_frame_work_n", "included_of_linked": "included_work_n", "included_of_retrieved": "included_work_n", "included_of_assessable_retrieved": "included_work_n", "nonretrieval_share_of_noninclusion": "not_retrieved_work_n"} Denominator: {"search_capture": "linked_work_N", "included_of_linked": "linked_work_N", "included_of_retrieved": "candidate_frame_work_n", "included_of_assessable_retrieved": "assessable_candidate_work_n", "nonretrieval_share_of_noninclusion": "linked_work_N - included_work_n"} Weighting: Distinct works within one scenario; no addition of overlapping scenarios/mechanism totals.

**Filters:** extension_years, match_definition, mechanism_group, completion_period, measure. Use actual source scenario tuples and the five explicitly mapped measures; selecting a measure changes its labelled base, never silently reuses a previous measure denominator. Default extension_years=3 and match_definition=clear.

**Uncertainty:** Wilson95_for_search_capture_only. For measure=search_capture, preserve supplied Wilson bounds and use interval_status=available when both bounds exist. Missing required capture bounds use interval_status=unavailable and interval_unavailable_reason=not_provided_in_released_source. Other measures have null bounds, interval_status=not_computed and interval_unavailable_reason=not_supplied_for_measure. An unavailable zero base uses unavailable bounds with interval_unavailable_reason=zero_denominator.

**Transformation:** `award_search_capture_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP1_search_capture_by_period_and_scenario`](../training_workforce_evidence/TABLES.html#table-dep1-search-capture-by-period-and-scenario) — primary numerical source

<a id="employment-roles"></a>

### employment_roles

**Population and period:** Observed employment-linked sample, five detailed credential groups plus the separately supplied all_observations total. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive proportion. Units: percent; count metadata

**Base and weighting:** numerator: n for reportable observed/scored role shares; source n is retained as count metadata for an unscored row whose scored-only share is unavailable. Denominator: basis=observed -> observed_n; basis=scored -> scored_n. Weighting: One observed record per released count; no reweighting.

**Filters:** degree_group or compare degrees, specification, basis: observed or scored, role category selection. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `employment_roles_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_degree_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-degree-role-profiles) — primary

<a id="employment-occupations"></a>

### employment_occupations

**Population and period:** Observed employment-linked sample within each detailed degree group, including occupation-unavailable and aggregate-residual records. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive proportion. Units: percent; count metadata

**Base and weighting:** numerator: n Denominator: observed_degree_n, including unavailable occupations. Weighting: Unweighted released record counts.

**Filters:** degree_group or compare degrees, occupation category selection. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `employment_occupations_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_occupation_frequencies`](../training_workforce_evidence/TABLES.html#table-dep4-occupation-frequencies) — primary
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="outside-destinations"></a>

### outside_destinations

**Population and period:** Known outside-university employment among pooled Masters and Research doctorate. Unknown industry stays outside the outside-university denominator. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive destination proportion. Units: percent; count metadata

**Base and weighting:** numerator: destination_n Denominator: outside_n; this is not observed_n and not the scored-only base. Weighting: Unweighted released destination record counts.

**Filters:** degree_group or compare two degrees, grouped destination selection. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `outside_destinations_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/destination_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-destination-role-profiles-csv) — primary
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="outside-roles"></a>

### outside_roles

**Population and period:** Observed outside-university sample, with destination-specific or All outside populations. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive role proportion. Units: percent; count metadata

**Base and weighting:** numerator: n Denominator: Destination source: destination_n or destination_scored_n. All outside source: outside_n or outside_scored_n. Weighting: Unweighted counts within the exact released base.

**Filters:** degree_group or compare two degrees, grouped destination or All outside, specification, basis: observed or scored, role category selection. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `outside_roles_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/destination_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-destination-role-profiles-csv) — primary
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/outside_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-outside-role-profiles-csv) — primary
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="employment-connection-profiles"></a>

### employment_connection_profiles

**Population and period:** Observed employment-linked sample within pooled degree and clear NIDA/NIAAA connection group. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive role proportion. Units: percent; count metadata

**Base and weighting:** numerator: n Denominator: denominator_n: full observed connection group; there is no scored-only basis toggle. Weighting: Unweighted released record counts.

**Filters:** degree_group or compare two degrees, connection_clear, specification: inclusive or conservative, role category selection. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `employment_connection_profiles_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_funding_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-funding-role-profiles) — primary
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="destination-connection"></a>

### destination_connection

**Population and period:** Research doctorate only; each dimension/group defines its own released observed population. Pooled Scored observations is a separately supplied subset. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive proportions and saved connected-minus-no-identified-connection contrast. Units: percent for proportions; percentage_points for difference; dimensionless p-values; counts

**Base and weighting:** numerator: connected_likely_n and no_identified_connection_likely_n for their corresponding proportions. Difference has no single numerator. Denominator: connected_observed_n and no_identified_connection_observed_n respectively; total_n is context, not a common replacement base. Weighting: Unweighted released record proportions.

**Filters:** destination dimension, group within dimension, specification. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** saved_Wilson_95_for_each_proportion_and_Newcombe_95_for_difference. Pair each bound with its own measure. Preserve saved Fisher and Holm p-values and original within-dimension/specification multiplicity family; do not recompute after filters.

**Transformation:** `destination_connection_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_destination_connection_roles`](../training_workforce_evidence/TABLES.html#table-dep4-destination-connection-roles) — primary

<a id="destination-saved-contrasts"></a>

### destination_saved_contrasts

**Population and period:** Research-doctorate populations defined separately: known-industry 189-record gap/standardization target versus the fixed scientific-R&D/manufacturing subset. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved exploratory contrasts; saved sector-standardized proportions; saved subset proportions. Units: percentage_points and percent; dimensionless p-value; count context

**Base and weighting:** numerator: Industry comparison uses connected_likely_research / no_identified_connection_likely_research. Gap and standardized contrasts have no single empirical numerator. Denominator: Industry comparison: connected_observations / no_identified_connection_observations; gap n_known_industry is context; standardized target remains its supplied target string. Weighting: Gap uses saved HC3 contrast; standardization uses saved 189-known-industry pooled broad-sector weights; industry comparison uses unweighted subset counts.

**Filters:** saved result type, specification. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** saved_HC3_normal_approximation_only_for_gap_contrast. Only DEP4_destination_gap_contrast has this interval. Standardization and industry comparison have no supplied uncertainty; do not borrow interval bounds.

**Transformation:** `destination_saved_contrasts_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_destination_gap_contrast`](../training_workforce_evidence/TABLES.html#table-dep4-destination-gap-contrast) — primary
- [`DEP4_destination_sector_standardization`](../training_workforce_evidence/TABLES.html#table-dep4-destination-sector-standardization) — primary
- [`DEP4_scientific_rd_manufacturing`](../training_workforce_evidence/TABLES.html#table-dep4-scientific-rd-manufacturing) — primary

<a id="employment-sensitivities"></a>

### employment_sensitivities

**Population and period:** Source-specific frozen detailed-degree specification transitions or pooled-degree outside-definition populations; the two populations are not interchangeable. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive sensitivity results. Units: Counts and percent; preserve per-field units

**Base and weighting:** numerator: Transition changed-state percentage uses joint_state_changed_n; outside profile shares use n. Denominator: Transition percent base observed_n; paired_scored_n applies to paired score comparisons. Outside shares use subset_n or observed_degree_n as explicitly labeled. Weighting: Unweighted released record counts.

**Filters:** saved sensitivity family, only the categorical combinations provided in each family. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `employment_sensitivities_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4_specification_transition_summary`](../training_workforce_evidence/TABLES.html#table-dep4-specification-transition-summary) — primary
- [`DEP4_outside_sensitivity_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-outside-sensitivity-role-profiles) — primary
- Supporting labels, coverage and definitions: see the dataset support_sources in the JSON contract.

<a id="outside-occupation-breakdowns"></a>

### outside_occupation_breakdowns

**Population and period:** Pooled Masters and Research doctorate outside-university samples within the exact published breakdown. The frozen employment observation used in the study; no year or completion-period filtering is supplied.

**Measure:** saved descriptive occupation composition. Units: Counts and percent

**Base and weighting:** numerator: n Denominator: breakdown_n for pct_breakdown; outside_n for pct_outside. Weighting: Unweighted counts within fixed source breakdown.

**Filters:** catalog table selection; existing source rows only. Use only combinations present in the named source after its fixed row selection. Table families and alternate groupings are not additive or freely joinable.

**Uncertainty:** none_descriptive. No intervals are supplied for these descriptive counts or shares; do not create them.

**Transformation:** `outside_occupation_breakdowns_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_role.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-role-csv) — primary
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_destination.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-destination-csv) — primary
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_destination_and_role.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-destination-and-role-csv) — primary

<a id="rc-rmi-lookup"></a>

### rc_rmi_lookup

**Population and period:** The fixed instrument domain: 303 occupation units × 68 industry units, 20,604 potential pairs per specification. These are not observed workers. Instrument version rc-rmi-standalone-2026-10-30-local-v6; no time selector.

**Measure:** deterministic instrument output. Units: Ordinal research and clinical scores 0–4 or U; categorical joint class; boolean likely flags.

**Base and weighting:** numerator: Not applicable: instrument lookup. Denominator: Not applicable: not a sampled-person percentage. Weighting: None: deterministic rule application to each potential pair.

**Filters:** specification, soc_code_canonical, naics_code_canonical. Allow the full canonical 303×68 domain under inclusive,no_hospital_override,conservative, only after generation passes the frozen fingerprints. Noncanonical input uses the exact released crosswalk; no guessed mapping.

**Uncertainty:** not_applicable. Preserve the source-specific field bindings and statuses in the JSON contract.

**Transformation:** `rc_rmi_domain_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [rc_rmi_scorer/scorer.py](../rc_rmi_scorer/scorer.py)
- [rc_rmi_scorer/instrument.py](../rc_rmi_scorer/instrument.py)
- [rc_rmi_scorer/data/occupation_decisions.csv](../rc_rmi_scorer/data/occupation_decisions.csv)
- [rc_rmi_scorer/data/industry_decisions.csv](../rc_rmi_scorer/data/industry_decisions.csv)
- [rc_rmi_scorer/data/combination_rules.csv](../rc_rmi_scorer/data/combination_rules.csv)
- [rc_rmi_scorer/data/constructs_and_scales.csv](../rc_rmi_scorer/data/constructs_and_scales.csv)
- [rc_rmi_scorer/data/soc_crosswalk.csv](../rc_rmi_scorer/data/soc_crosswalk.csv)
- [rc_rmi_scorer/data/original_two_specifications.json](../rc_rmi_scorer/data/original_two_specifications.json)
- [rc_rmi_scorer/expected_domain_fingerprints.json](../rc_rmi_scorer/expected_domain_fingerprints.json)

<a id="table-catalog"></a>

### table_catalog

**Population and period:** All 246 released catalog entries; not a study population. Evidence component version 2026-11-02-local-v9; each entry retains its own scientific period.

**Measure:** Navigation metadata.. Units: Catalog entry; source rows/columns are file shape metadata, not participant counts.

**Base and weighting:** numerator: Not applicable. Denominator: Not applicable. Weighting: Not applicable.

**Filters:** table, title, backs_displays, check. Search/filter catalog metadata only; no scientific population cross-filter.

**Uncertainty:** not_applicable. Preserve the source-specific field bindings and statuses in the JSON contract.

**Transformation:** `catalog_index_v1`; exact steps, field bindings and availability rules are specified in the JSON contract.

**Primary sources:**
- [training_workforce_evidence/data/TABLE_INDEX.csv](../training_workforce_evidence/data/TABLE_INDEX.csv)
- [training_workforce_evidence/code/table_restore.csv](../training_workforce_evidence/code/table_restore.csv)
- [training_workforce_evidence/DISPLAY_MAP.csv](../training_workforce_evidence/DISPLAY_MAP.csv)
- [training_workforce_evidence/DATA_DICTIONARY.csv](../training_workforce_evidence/DATA_DICTIONARY.csv)
- [training_workforce_evidence/data/catalog_displays.json](../training_workforce_evidence/data/catalog_displays.json)

## Precision, status and source details

The JSON contract is authoritative for field bindings and source-specific selectors. Its shared_contract defines numeric serialization, row IDs, separate support/value/interval states, manifest fields and validation gates. Source registry entries retain the exact restored-table hash, container hash, component version, rights notice, existing source download and ordinary-table export command.

The dashboard/data paths are generated downloads. Matching JSON paths are shard manifests decoded by the static-data client. Existing source containers and table-catalog links remain usable locally. The three deferred views have no export contract in this version.

## Validation and next step

Run `python -B scripts/validate_data_contract.py` from the repository root to check the specification against the released sources. This reads and verifies source keys/hashes without generating datasets.

The deterministic adapters and CSV/JSON verification are implemented in Step 5. See the [build guide](dashboard_build.md) for commands and loader behavior. All 170 package files, including the frozen supplement, remain unchanged.
