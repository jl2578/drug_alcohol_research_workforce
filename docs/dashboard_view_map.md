# Dashboard view-to-table map

Step 2 source map, updated with the [Step 3 first-release decisions](dashboard_scope.md) on 2 November 2026. The sources remain the finalized `2026-11-02-local-v9` upload set. Data export and dashboard implementation remain pending.

The [machine-readable map](dashboard_view_map.json) records exact table IDs, source files and checksums, source column names, observed filter levels, and interpretation rules. Source-specific filter levels do not imply that every combination is available.

All three packages and the frozen supplement remain byte-identical. `dashboard/` still contains only `.gitkeep`. The mapping documentation lives here so the dashboard folder stays empty.

## Readiness

Scope is resolved: 25 mapped views are included in preparation; the observed institutional-period, training-linked employment and funding-band extensions are deferred. This does not assert that any view has been implemented.

| View | Dataset family | Source readiness |
|---|---|---|
| [Degree and field composition](#population-composition) | `population_composition` | mapped existing |
| [Observed group content profiles](#content-observed) | `content_observed` | mapped existing |
| [Descriptive observed A-minus-B differences](#content-observed-difference) | `content_observed` | mapped existing |
| [Saved fitted group profiles](#content-fitted) | `content_fitted` | mapped existing |
| [Saved fitted pairwise contrasts](#content-fitted-contrasts) | `content_contrasts` | mapped existing |
| [Saved temporal changes and continuing-institution sensitivity](#content-temporal-changes) | `content_contrasts` | mapped existing |
| [Saved fitted institutional profiles](#institution-profiles) | `institution_profiles` | mapped existing |
| [Fixed equal-institution comparison benchmark](#institution-benchmark) | `institution_profiles` | mapped existing |
| [Original mock-up: observed institutional profiles by period](#institution-observed-period-profiles) | `institution_profiles` | needs new aggregate |
| [Identified funding-connection reach](#funding-reach) | `funding_connection` | mapped existing |
| [Observed content by funding connection](#funding-content-profiles) | `funding_connection` | mapped existing |
| [Institutional count-model funding associations](#institutional-count-association) | `funding_connection` | mapped existing |
| [Within-investigator participation during funded and unfunded years](#within-pi-participation) | `funding_connection` | mapped existing |
| [Student-award frame inclusion and disposition](#student-award-frame-coverage) | `award_capture` | mapped existing |
| [Search capture and inclusion among linked award-frame works](#student-award-search-capture) | `award_capture` | mapped existing |
| [Funding-band comparisons (deferred)](#funding-bands-extension) | `funding_connection` | needs new aggregate |
| [Employment role profiles](#employment-roles) | `employment_profiles` | mapped existing |
| [Occupations by degree](#employment-occupations) | `employment_profiles` | mapped existing |
| [Outside-university destination shares](#outside-destinations) | `employment_profiles` | mapped existing |
| [Roles within outside-university destinations](#outside-roles) | `employment_profiles` | mapped existing |
| [Role profiles by funding connection](#employment-connection-profiles) | `employment_profiles` | mapped existing |
| [Research-role likelihood by destination and funding connection](#destination-connection) | `destinations` | mapped existing |
| [Saved destination contrasts and standardization](#destination-saved-contrasts) | `destinations` | mapped existing |
| [Employment specification and population sensitivity tables](#employment-sensitivities) | `employment_profiles` | mapped existing |
| [Released outside occupation breakdowns (catalog)](#outside-occupation-breakdowns) | `destinations` | mapped existing |
| [Employment roles by training field or content](#employment-training-linked) | `employment_profiles` | needs new aggregate |
| [RC-RMI potential occupation-industry lookup](#rc-rmi-lookup) | `rc_rmi_lookup` | mapped existing |
| [Complete evidence catalog and downloads](#table-catalog) | `table_catalog` | mapped existing |

“Mapped existing” means the sources are available and identified; it does not mean an adapter or dashboard has been built. “Needs definition” requires a decision about the measure or display. “Needs new aggregate” requires additional analysis beyond these released tables.

## Rules shared across views

- The three component folders, including both supplement formats, remain unchanged.
- Filter columns are source-specific. Actual released combinations define support; independent margins do not authorize new intersections.
- Observed percentages, fitted profiles, model contrasts, and descriptive differences must be separately labeled.
- Use saved contrast uncertainty; never subtract marginal interval endpoints. Preserve unsupported and missing interval states.
- Keep numeric zeros, unavailable values, instrument U and unscored employment distinct. Preserve source precision.
- Source field names are case-sensitive: n and N are different columns. Do not lowercase or merge them.
- Institutional U/UNITID-style profile IDs and NIH INST IDs are distinct namespaces. Use only documented verified joins.
- Use the current DATA_AVAILABILITY.md notices and existing employment pooling. Do not invent blanket suppression or data licensing rules.
- Future CSV and JSON representations must come from the same transformed rows. No numbers copied from the synthetic prototype.

<a id="population-composition"></a>

## Degree and field composition

**Family:** `population_composition`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T20_degree_field_composition`](../training_workforce_evidence/TABLES.html#table-dep2-t20-degree-field-composition) — Exact empirical cells and all-corpus denominator; 72 rows.
- [`DEP1_population_accounting`](../training_workforce_evidence/TABLES.html#table-dep1-population-accounting) — Population accounting context; 18 rows.

**Proposed controls and supported comparisons**

- Presentation credential group
- Adopted broad field including Unavailable

**Interpretation and preparation**

- All 72 degree-field cells cover 13,227 distinct works exactly once.
- Filtering chooses cells; preserve the all-corpus denominator for share_of_all_works_percent. A within-subset percentage would be a separate, explicitly defined measure.
- Repeated field_total_distinct_works and degree_total_distinct_works must not be summed across rows.
- Preserve all six presentation degree groups and field-unavailable. T20 credential labels and membership are not interchangeable with model-supported T2 groups.
- No outcome, period, institution, funding or employment filter is supported by this table.

<a id="content-observed"></a>

## Observed group content profiles

**Family:** `content_observed`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_group_period_category_counts`](../training_workforce_evidence/TABLES.html#table-dep2-group-period-category-counts) — Exact category counts and usable bases; 2528 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Outcome-specific category labels and order; 44 rows.
- [`DEP2_T2_group_support`](../training_workforce_evidence/TABLES.html#table-dep2-t2-group-support) — Model-support registry and group labels; 332 rows.
- [`DEP2_T13_group_period_coverage`](../training_workforce_evidence/TABLES.html#table-dep2-t13-group-period-coverage) — Primary group-period coverage context; 664 rows.
- [`DEP2_T1_outcome_coverage`](../training_workforce_evidence/TABLES.html#table-dep2-t1-outcome-coverage) — Overall outcome coverage; 4 rows.

**Proposed controls and supported comparisons**

- Outcome
- Population: primary or continuing
- Supported degree-field group
- Completion-period bin
- Category selection

**Interpretation and preparation**

- Compute observed percent as 100*selected_works/eligible_works at source precision; period_weight=0.5 is for standardized calculations and must not be applied to an observed period percentage.
- Use only tuples actually present in the 2,528-row count table. Outcomes C3/C4/C5/C8, periods 2010-2016 and 2017-2023, and primary/continuing populations are available; the Cartesian product of listed dimension levels is not permission to fabricate combinations.
- Category selection never changes eligible_works. C8 is multi-response and category percentages can sum above 100%; C3/C4/C5 are exclusive.
- Join category labels on outcome+category; join group labels/support on outcome+group_id. T2 has unsupported groups not present in the count table.
- T13 is primary-population coverage context. Do not attach it to continuing-population profiles as if it described their eligible base. Continuing bases are provided by count rows and shared_* T2 fields.
- Preserve real zero counts. No inferential intervals are supplied for these observed percentages in this view.
- Verified many-to-one join: `DEP2_group_period_category_counts` (outcome, group_id) to `DEP2_T2_group_support` (outcome, group_id); every left key has a matching right key.
- Verified many-to-one join: `DEP2_group_period_category_counts` (outcome, category) to `DEP2_T16_category_labels` (outcome, category); every left key has a matching right key.

<a id="content-observed-difference"></a>

## Descriptive observed A-minus-B differences

**Family:** `content_observed`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_group_period_category_counts`](../training_workforce_evidence/TABLES.html#table-dep2-group-period-category-counts) — Two observed profiles from the same outcome/population/period; 2528 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Category labels; 44 rows.

**Proposed controls and supported comparisons**

- Outcome
- Population
- Shared completion period
- Supported group A
- Supported group B
- Categories

**Interpretation and preparation**

- Compute 100*(selected_A/eligible_A-selected_B/eligible_B); retain distinct A and B numerators and bases.
- Both groups must be present for the same outcome, population, period and category. Preserve their selected group identities in downloads.
- This is descriptive arithmetic, not a saved fitted contrast. Do not supply confidence intervals, p-values or significance from marginal information.
- Do not pool groups or change the denominator when categories are selected.

<a id="content-fitted"></a>

## Saved fitted group profiles

**Family:** `content_fitted`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T3_profiles_and_periods`](../training_workforce_evidence/TABLES.html#table-dep2-t3-profiles-and-periods) — Saved early, late and equal-period standardized fitted profiles; 10956 rows.
- [`DEP2_T2_group_support`](../training_workforce_evidence/TABLES.html#table-dep2-t2-group-support) — Support and group labels; 332 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Category labels; 44 rows.

**Proposed controls and supported comparisons**

- Outcome
- Supported degree-field group via T2
- Profile family: earlier/later/equal-period standardized
- Categories

**Interpretation and preparation**

- Select family early_profile, late_profile or standardized_profile. The standardized profile gives equal weight to the two fitted period probabilities; it is not pooled observed composition.
- Join T3 outcome+unit_id to T2 outcome+group_id; this key relationship was verified against the current tables. Do not parse degree/field out of labels when T2 supplies them.
- The 10,956-row registry includes 8,844 unsupported rows without estimates and two additional missing-interval rows. Keep unavailable states visible and do not convert blanks to zero.
- Only rows with report_supported=1 support plotted numeric profiles; preserve status/source_status and reportable interval availability separately. A supplied point with unavailable interval need not disappear.
- Scale is probability; convert points and reportable lower/upper bounds together if displaying percentages. Diagnostic bounds are not substitutes for blank reportable bounds.
- The early and late bases explain support; a standardized fitted probability has no single empirical numerator/denominator.
- The stacked estimate registry uses different support columns by outcome: C3/C5 use primary_* for T3/T8 and shared_* for T9; C4/C8 use the unprefixed early_eligible_works/late_eligible_works and early_institutions/late_institutions on the relevant source row. Preserve this source-specific mapping; blank prefixed fields do not mean zero support.
- Verified many-to-one join: `DEP2_T3_profiles_and_periods` (outcome, unit_id) to `DEP2_T2_group_support` (outcome, group_id); every left key has a matching right key.

<a id="content-fitted-contrasts"></a>

## Saved fitted pairwise contrasts

**Family:** `content_contrasts`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T4_C3_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t4-c3-pairwise) — Saved pairwise contrasts for C3; 1440 rows.
- [`DEP2_T5_C5_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t5-c5-pairwise) — Saved pairwise contrasts for C5; 1440 rows.
- [`DEP2_T6_C4_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t6-c4-pairwise) — Saved pairwise contrasts for C4; 960 rows.
- [`DEP2_T7_C8_pairwise`](../training_workforce_evidence/TABLES.html#table-dep2-t7-c8-pairwise) — Saved pairwise contrasts for C8; 1440 rows.
- [`DEP2_T2_group_support`](../training_workforce_evidence/TABLES.html#table-dep2-t2-group-support) — Group identity/support; 332 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Category labels; 44 rows.

**Proposed controls and supported comparisons**

- Outcome
- Saved group pair
- Categories

**Interpretation and preparation**

- Use saved difference_pp and lower_95_pp/upper_95_pp, not differences of marginal bounds. All 5,280 saved targets have usable paired resampling attempts.
- Pair order and direction are defined by group_a/group_b and pair_id. If allowing reversal, reverse point sign and negate/swap interval endpoints explicitly; never reuse the original bounds unchanged.
- Intervals are conditional pointwise with no simultaneous or multiplicity adjustment.
- Available comparisons are the saved pair rows, not all combinations of every group appearing elsewhere in the repository.
- This family is for standardized fitted profile comparisons. Do not add a period or primary/continuing population selector that the source does not contain.

<a id="content-temporal-changes"></a>

## Saved temporal changes and continuing-institution sensitivity

**Family:** `content_contrasts`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T8_temporal_changes`](../training_workforce_evidence/TABLES.html#table-dep2-t8-temporal-changes) — Primary-population later-minus-earlier changes; 3652 rows.
- [`DEP2_T9_continuing_changes`](../training_workforce_evidence/TABLES.html#table-dep2-t9-continuing-changes) — Continuing-institution later-minus-earlier sensitivity; 3652 rows.
- [`DEP2_T2_group_support`](../training_workforce_evidence/TABLES.html#table-dep2-t2-group-support) — Group support and labels; 332 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Category labels; 44 rows.

**Proposed controls and supported comparisons**

- Outcome
- Supported group
- Primary or continuing-institution analysis
- Categories

**Interpretation and preparation**

- Choose the complete source table for the primary versus continuing-institution target; do not relabel the primary estimates as continuing estimates.
- Direction is later 2017-2023 minus earlier 2010-2016. This is a fixed two-period contrast, not an arbitrary year-range comparison.
- Scale is already percentage_points; do not multiply by 100 again.
- Use saved paired temporal intervals. Preserve the one supported T8 needs_investigation row with a point but missing reportable bounds.
- T2 joins on outcome+group_id to each result table outcome+unit_id; use shared support for T9.
- Do not fabricate new temporal contrasts by joining unrelated result rows.
- The stacked estimate registry uses different support columns by outcome: C3/C5 use primary_* for T3/T8 and shared_* for T9; C4/C8 use the unprefixed early_eligible_works/late_eligible_works and early_institutions/late_institutions on the relevant source row. Preserve this source-specific mapping; blank prefixed fields do not mean zero support.

<a id="institution-profiles"></a>

## Saved fitted institutional profiles

**First-release scope:** Included in preparation; not implemented.

**Family:** `institution_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T10_institution_profiles`](../training_workforce_evidence/TABLES.html#table-dep2-t10-institution-profiles) — 2,200 saved fitted profile rows for the fixed 50-institution roster; 2200 rows.
- [`DEP2_T12_institution_support`](../training_workforce_evidence/TABLES.html#table-dep2-t12-institution-support) — Complete institutional labels and outcome-specific support; 200 rows.
- [`DEP2_T14_institution_period_coverage`](../training_workforce_evidence/TABLES.html#table-dep2-t14-institution-period-coverage) — Period-specific coverage context; 400 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Category labels; 44 rows.

**Proposed controls and supported comparisons**

- Outcome
- Institution multiselect using T12 labels
- Categories

**Interpretation and preparation**

- Use T10 outcome+unit_id as the authoritative profile key and join to T12 outcome+institution_id. These sets match exactly (200 outcome-institution keys); T12 is unique on this key.
- T10 institution_id is blank in 1,000 of 2,200 rows although unit_id is populated. Filtering/joining solely on T10 institution_id would silently lose valid profiles. Nonblank embedded IDs equal unit_id.
- T14 contributes two coverage rows per outcome/institution. Keep period-specific coverage as nested/separate metadata to avoid multiplying profile rows.
- These are fitted institutional probabilities with equal earlier/later period weighting, not period-specific observed proportions. No degree, field or period filter applies to the profile itself.
- All 2,200 point estimates exist; 60 reportable intervals are missing (27 needs_investigation and 33 unavailable). Preserve point and interval availability separately.
- Institution U-prefixed keys here are not the INST-prefixed NIH funding keys. Do not infer cross-namespace identity from prefixes or names.
- Retain the fixed roster. Institution search changes visible selections, not cohort membership.
- Verified many-to-one join: `DEP2_T10_institution_profiles` (outcome, unit_id) to `DEP2_T12_institution_support` (outcome, institution_id); every left key has a matching right key.

**Remaining work or limitation**

- Step 3 adopts the saved fitted-profile view, with outcome, institution selection and category controls only. Earlier/later work counts are context. Adapter and interface implementation remain.

<a id="institution-benchmark"></a>

## Fixed equal-institution comparison benchmark

**First-release scope:** Included in preparation; not implemented.

**Family:** `institution_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP2_T10_institution_profiles`](../training_workforce_evidence/TABLES.html#table-dep2-t10-institution-profiles) — Saved fitted-profile points for the defined reference; 2200 rows.
- [`DEP2_T12_institution_support`](../training_workforce_evidence/TABLES.html#table-dep2-t12-institution-support) — Fixed institutional support roster; 200 rows.

**Proposed controls and supported comparisons**

- Outcome
- Categories; institution selection must not change the benchmark

**Interpretation and preparation**

- For each outcome and category, average the 50 supplied supported T10 estimates with weight 1/50, then multiply by 100 for percentage display.
- Pin the T12 roster in dashboard_scope.json. Institution selection and category visibility never change the roster or weights; selected institutions remain included.
- Use T10 unit_id to join T12 institution_id. Verify T12 profile_supported and T10 report_supported/finite estimate; missing profile intervals do not exclude valid points.
- If any fixed member lacks a required supported point, mark that benchmark unavailable. Do not drop, impute zero, reselect or silently reweight institutions.
- The benchmark is a descriptive mean of fitted profiles, with no confidence interval. Do not average profile bounds or manufacture institution-minus-benchmark inference.
- No work-count weighting, refitting or observed-period relabeling is allowed. C8 categories remain nonexclusive.

**Remaining work or limitation**

- Generate and validate the benchmark during the dataset-build step. The fixed roster, eligibility, formula and missing-input policy are in [dashboard_scope.json](dashboard_scope.json).

<a id="institution-observed-period-profiles"></a>

## Original mock-up: observed institutional profiles by period

**First-release scope:** Deferred.

**Family:** `institution_profiles`. **Readiness:** needs new aggregate.

**Sources**

- [`DEP2_T14_institution_period_coverage`](../training_workforce_evidence/TABLES.html#table-dep2-t14-institution-period-coverage) — Released period coverage only; lacks category numerators; 400 rows.

**Proposed controls and supported comparisons**

- Outcome
- Institution
- Period
- Category, only after new aggregates exist

**Interpretation and preparation**

- Coverage counts are not content category numerators. Do not substitute fitted T10 estimates as observed period-specific values.
- Any additional release must preserve fixed cohort membership and category-specific scientific definitions.

**Remaining work or limitation**

- No released institution-period-category count table was found in the current catalog. Retaining the original observed-period mock-up requires new reviewed aggregates; otherwise use the labeled fitted-profile alternative.

<a id="funding-reach"></a>

## Identified funding-connection reach

**Family:** `funding_connection`. **Readiness:** mapped existing.

**Sources**

- [`DEP3_observed_reach`](../training_workforce_evidence/TABLES.html#table-dep3-observed-reach) — Primary observed connection shares and source counts; 72 rows.

**Proposed controls and supported comparisons**

- Ownership population
- Degree comparison or one degree
- Connection definition (primary or named sensitivity)
- Funding institute

**Interpretation and preparation**

- Primary connection is the clear advisor/committee-or-award union. PI_only is a component and combined_clear_or_possible is a separate sensitivity.
- Unit is distinct adopted works. Do not add NIDA and NIAAA shares because dual connections overlap.
- No identified connection does not establish absence of funding.
- Both full and exclude_ever_for_profit ownership populations are supplied. The exclusion removes entire institutions ever identified as for-profit and retains unknown ownership.
- These are finite-corpus observed descriptive shares; interval_status is not_added_observed_descriptive. Do not invent intervals.
- No institution, flexible completion-year, field or dollar-band filter is present in this source. Separate released field-reach tables do not authorize cross-filtering this view.
- Do not substitute DEP3_cohort.connected: it means PI-only rather than the current combined connection.
- Row selection: Default connection_definition=combined_clear, institute=NIDA/NIAAA, and population in {Masters, Research doctorate}; retain All credentials and Other credentials only as explicitly labelled alternative populations.

<a id="funding-content-profiles"></a>

## Observed content by funding connection

**Family:** `funding_connection`. **Readiness:** mapped existing.

**Sources**

- [`DEP3/other_rq3/reach_content/data/NA38_T4_D_observed_counts.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na38-t4-d-observed-counts-csv) — Category counts and usable denominators for primary and two sensitivity connections; 528 rows.
- [`DEP3/other_rq3/reach_content/data/NA39_T4_D_observed_coverage.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na39-t4-d-observed-coverage-csv) — Outcome-specific eligibility and excluded-state context; 48 rows.
- [`DEP3_observed_content`](../training_workforce_evidence/TABLES.html#table-dep3-observed-content) — Saved primary profiles, connected-minus-remaining and direct degree contrasts; 616 rows.
- [`DEP3/other_rq3/reach_content/data/NA40_T4_D_award_possible_sensitivity.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na40-t4-d-award-possible-sensitivity-csv) — Saved possible-award sensitivity profiles and contrasts; 616 rows.
- [`DEP3/other_rq3/reach_content/data/NA41_T4_D_PI_component_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep3-other-rq3-reach-content-data-na41-t4-d-pi-component-profiles-csv) — Saved PI-component profiles and contrasts; 616 rows.
- [`DEP2_T16_category_labels`](../training_workforce_evidence/TABLES.html#table-dep2-t16-category-labels) — Outcome/category labels; join on outcome and category only after verifying key coverage; 44 rows.

**Proposed controls and supported comparisons**

- Ownership population
- Degree comparison or one degree
- Outcome and categories
- Connection definition (primary or named sensitivity)
- Profiles or saved descriptive contrasts

**Interpretation and preparation**

- Explicit connection-name crosswalk: reach combined_clear maps to content primary_combined; PI_only maps to PI_component; combined_clear_or_possible maps to award_possible_sensitivity. Never match these labels implicitly.
- Counts table contains 528 rows; coverage contains 48. Each saved profile/contrast file contains 616 rows. These are complementary or repeated representations, not additive observations.
- Join counts to coverage on connection_definition, ownership, degree_target, outcome, validating many categories to one coverage row.
- Each degree and connection group has its own outcome-eligible base. Selecting categories must leave its denominator unchanged.
- C8 is multi-response, so its category percentages can sum above 100%.
- Saved direct degree contrast labelled Masters minus research doctorate is a difference of connected-minus-remaining differences, not a raw degree-profile gap.
- Source numerator and denominator fields in saved contrasts can be JSON objects holding two or four bases; do not coerce to a single number.
- Observed content has no fitted model, sampling interval or significance test. Blank bounds remain blank.
- No field, institution or flexible-year filter is supported by these tables.
- Row selection: Default counts connection_definition=primary_combined. Show connected and remaining series using their respective denominators. Saved profile metrics are connected_profile_percent and remaining_profile_percent; content_pp_difference is a separate contrast display.

<a id="institutional-count-association"></a>

## Institutional count-model funding associations

**Family:** `funding_connection`. **Readiness:** mapped existing.

**Sources**

- [`DEP3_count_primary_reference`](../training_workforce_evidence/TABLES.html#table-dep3-count-primary-reference) — Six adopted degree and direct degree-contrast estimates with saved uncertainty; 6 rows.
- [`DEP3_count_fit_registry`](../training_workforce_evidence/TABLES.html#table-dep3-count-fit-registry) — Eight fit identities and retained-cell/cluster support; 8 rows.
- [`institution_panel`](../training_workforce_evidence/TABLES.html#table-institution-panel) — Downloadable public input for supported fits, not an extra chart filter source; 7798 rows.

**Proposed controls and supported comparisons**

- Ownership population
- Degree comparison or one target
- Pointwise or familywise saved interval

**Interpretation and preparation**

- Funding contrast is 1 to 4 annualized funded application IDs per fiscal year. The model applies log(5)-log(2); this is not a one-dollar or one-project increase.
- Use rate_ratio and exponentiated interval bounds on a log axis with reference 1. Masters minus research doctorate names a log-contrast; its rate_ratio is a ratio of degree-specific associations.
- The direct degree contrast uses its own common retained population. Do not divide the displayed separate-degree full-sample rate ratios or their interval endpoints to reconstruct it.
- Cluster counts are model-support counts, not a numerator/denominator for the ratio.
- Full versus exclude_ever_for_profit is the UI sample control. The registry's main/common values describe separate fit roles and are not an unrestricted selector of additional adopted target estimates.
- The saved target-to-fit route must follow code/compare_count_fits.py and the fit registry; do not join target rows to every fit having the same degree and ownership.
- No institution, category, flexible period, dollar band or alternative funding-contrast control is authorized by this saved-result view.
- Row selection: One row per ownership x degree_target; comparison displays the two degree targets and the separately estimated direct degree contrast.

<a id="within-pi-participation"></a>

## Within-investigator participation during funded and unfunded years

**Family:** `funding_connection`. **Readiness:** mapped existing.

**Sources**

- [`DEP3_investigator_equal_pi_summary`](../training_workforce_evidence/TABLES.html#table-dep3-investigator-equal-pi-summary) — Four equal-PI finite-panel summaries; 4 rows.

**Proposed controls and supported comparisons**

- Ownership population
- Degree comparison or one degree

**Interpretation and preparation**

- The unit is equal-weight PI; annual distinct qualifying PI-work participations. Plot saved mean_funded_works_per_year and mean_unfunded_works_per_year.
- Do not compute these means by dividing pooled participation counts by pooled year counts. The paired-PI base is PIs, not PI_years.
- A shared work can count once for each investigator; participation totals are not distinct-work counts.
- The paired difference is a saved mean across investigators. No inference was performed for these finite-panel summaries; quantiles/ranges are not confidence intervals.
- Preserve preceding_funding_window_FY (5 doctorate, 2 Masters) and completion_FY_excluded in explanatory metadata.
- Equal-PI content profiles are a different saved family and must not substitute for this participation summary.
- Row selection: One source row per ownership x degree_group; funded/unfunded plotted series are the two saved mean columns.

<a id="student-award-frame-coverage"></a>

## Student-award frame inclusion and disposition

**Family:** `award_capture`. **Readiness:** mapped existing.

**Sources**

- [`DEP1_coverage_by_mechanism_period_scenario`](../training_workforce_evidence/TABLES.html#table-dep1-coverage-by-mechanism-period-scenario) — Six disposition counts within each matched award-frame scenario; 720 rows.

**Proposed controls and supported comparisons**

- Mechanism
- Completion-period bin
- Extension window
- Match definition
- Disposition

**Interpretation and preparation**

- Source n and N are different case-sensitive fields. Rename explicitly to numerator and denominator in a future browser adapter.
- The unit is distinct matched frame-eligible thesis/dissertation work, not awards, people or award-person relationships.
- The base N repeats across disposition rows; do not sum the repeated denominator.
- F30_F31 overlaps F30/F31; all_mechanisms overlaps the individual mechanisms. Timing and match scenarios overlap; do not add scenarios.
- No degree, institution, research-content or flexible-year control is supported.
- No intervals are supplied in this disposition table; do not transfer capture intervals to inclusion shares.
- Row selection: Default extension_years=3, match_definition=clear, disposition=included. All denotes the complete 2010-2023 completion span, not a sum alongside period rows.

<a id="student-award-search-capture"></a>

## Search capture and inclusion among linked award-frame works

**Family:** `award_capture`. **Readiness:** mapped existing.

**Sources**

- [`DEP1_search_capture_by_period_and_scenario`](../training_workforce_evidence/TABLES.html#table-dep1-search-capture-by-period-and-scenario) — Capture, linked/retrieved/assessable inclusion bases and saved capture Wilson bounds; 120 rows.

**Proposed controls and supported comparisons**

- Mechanism
- Completion-period bin
- Extension window
- Match definition
- Explicit measure/base

**Interpretation and preparation**

- This table has 120 scenario rows; it is not a second sample to add to the 720 disposition rows.
- Join with the disposition table only on extension_years, match_definition, mechanism_group, completion_period, and retain its one-to-many disposition structure.
- Saved Wilson bounds apply only to search capture; inclusion among linked, retrieved and assessable works are different measures with different bases.
- nonretrieval_share_of_noninclusion_percent uses the noninclusion base (linked_work_N minus included_work_n), not all linked works; preserve unavailable behavior for zero base.
- Use the same finite award-specific filter values as student_award_frame_coverage. Do not synchronize these period bins to the training/content two-period selector.
- Row selection: Default extension_years=3 and match_definition=clear. Capture is candidate_frame_work_n / linked_work_N. Inclusion measures use included_work_n over the specifically named linked, retrieved or assessable base.

<a id="funding-bands-extension"></a>

## Funding-band comparisons (deferred)

**First-release scope:** Deferred.

**Family:** `funding_connection`. **Readiness:** needs new aggregate.

**Sources**

- [`institution_panel`](../training_workforce_evidence/TABLES.html#table-institution-panel) — Potential institutional-model inputs only; 7798 rows.
- [`nih/data/institution_completion_year_degree_funding_exposure.csv`](../training_workforce_evidence/TABLES.html#table-nih-data-institution-completion-year-degree-funding-exposure-csv) — Potential exposure inputs; no finalized dashboard bands or joint content/employment aggregates; 26628 rows.

**Proposed controls and supported comparisons**


**Interpretation and preparation**

- Do not expose a working band selector in the first dashboard release.
- Annualized application counts, funding-window sums and dollars are different measures. Specify measure, window and band boundaries before calculating any band summary.
- Exposure rows include joint-program and predecessor reuse; do not add them as if they were independent source dollars.
- Existing marginal profiles do not support deriving work/content/employment-by-band results.

**Remaining work or limitation**

- No adopted band boundaries or band-specific population/denominator definition.
- No finalized joint band aggregates for the proposed comparisons.

<a id="employment-roles"></a>

## Employment role profiles

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_degree_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-degree-role-profiles) — primary role counts and both bases; 108 rows.

**Proposed controls and supported comparisons**

- degree_group or compare degrees
- specification
- basis: observed or scored
- role category selection

**Interpretation and preparation**

- Use degree_group as key and degree_label as display. Preserve five detailed degree groups and the separately supplied all_observations total; never sum total with components.
- Basis chooses the saved pct_observed or pct_scored field; changing visible role categories must not change either denominator.
- Keep unscored distinct from unclassifiable (instrument U); the latter remains an instrument information state. Scored-only unscored percentages remain unavailable.
- All three specifications exist: inclusive, conservative, no_hospital_override.

<a id="employment-occupations"></a>

## Occupations by degree

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_occupation_frequencies`](../training_workforce_evidence/TABLES.html#table-dep4-occupation-frequencies) — thresholded occupation rows; 25 rows.
- [`DEP4_occupation_degree_coverage`](../training_workforce_evidence/TABLES.html#table-dep4-occupation-degree-coverage) — degree coverage and unavailable bases; 5 rows.

**Proposed controls and supported comparisons**

- degree_group or compare degrees
- occupation category selection

**Interpretation and preparation**

- Occupation frequency status vocabulary is coded, aggregate_residual, unavailable; do not replace it with the different outside-table occupation_row_type vocabulary.
- Join coverage many-to-one on exact degree_group. Keep unavailable and aggregate_residual rows in the denominator and display counts.
- Preserve reported competition_rank, count_tie_size and main_table_group. No scoring-specification or year filter exists for this occupation-only table.

<a id="outside-destinations"></a>

## Outside-university destination shares

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/destination_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-destination-role-profiles-csv) — destination totals repeated by role state and specification; 828 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/observation_bases.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-observation-bases-csv) — observed/outside degree bases; 2 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/destination_classification.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-destination-classification-csv) — frozen category labels and precedence; 16 rows.

**Proposed controls and supported comparisons**

- degree_group or compare two degrees
- grouped destination selection

**Interpretation and preparation**

- Initial view selects destination_dimension=grouped. Degree groups are pooled Master's and Research doctorate, not the detailed five-group role universe.
- For a destination-only share, select one specification (inclusive) and collapse repeated role rows only after checking that outside_n, destination_n and destination_pct_outside agree; do not sum repeated totals. Check destination totals are invariant across specifications.
- Use destination_n/outside_n. Unknown industry is not recoded as outside, and outside universities may include academically affiliated hospitals.
- Row selection: ["destination_dimension = grouped", "specification = inclusive for destination-only totals"]

<a id="outside-roles"></a>

## Roles within outside-university destinations

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/destination_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-destination-role-profiles-csv) — destination-specific role counts and all-observed/scored bases; 828 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/outside_role_profiles.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-outside-role-profiles-csv) — all-outside role summaries; 36 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/observation_bases.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-observation-bases-csv) — coverage context; 2 rows.

**Proposed controls and supported comparisons**

- degree_group or compare two degrees
- grouped destination or All outside
- specification
- basis: observed or scored
- role category selection

**Interpretation and preparation**

- Initial destination view selects grouped destinations. Within-destination profiles use pct_within_destination or pct_scored_within_destination; source figure shares pct_outside answer a different question.
- If All outside is selected, use outside_role_profiles directly; do not fabricate a combined base from overlapping detailed and grouped categories.
- Preserve zero segments, U/unclassifiable and unscored. Denominator is fixed when role categories are hidden.
- Row selection: ["destination_dimension = grouped for destination-specific rows"]

<a id="employment-connection-profiles"></a>

## Role profiles by funding connection

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_funding_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-funding-role-profiles) — two-specification role profile; 48 rows.
- [`DEP4_funding_connection_roles`](../training_workforce_evidence/TABLES.html#table-dep4-funding-connection-roles) — inclusive source/reference; 24 rows.

**Proposed controls and supported comparisons**

- degree_group or compare two degrees
- connection_clear
- specification: inclusive or conservative
- role category selection

**Interpretation and preparation**

- Use the two released degree groups and connection_clear 0/1; retain exact connection labels and the confirmed connection definition.
- Only inclusive and conservative role profiles exist in DEP4_funding_role_profiles; DEP4_funding_connection_roles is inclusive only.
- Use full observed denominator_n; no supplied scored-only base exists here. Do not infer a no_hospital_override role distribution from the separate research-likelihood destination table.

**Remaining work or limitation**

- The complete no_hospital_override six-state funding-connection profile is not supplied. Disable that specification for this view.

<a id="destination-connection"></a>

## Research-role likelihood by destination and funding connection

**Family:** `destinations`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_destination_connection_roles`](../training_workforce_evidence/TABLES.html#table-dep4-destination-connection-roles) — saved likelihood proportions, differences and inference; 117 rows.

**Proposed controls and supported comparisons**

- destination dimension
- group within dimension
- specification

**Interpretation and preparation**

- This table contains Research doctorate only. All three specifications are present; it reports likely research, not six-state role distributions.
- Allow only observed (dimension, group, specification) combinations. Pooled, broad_sector, college_vs_outside, figure_destination and retained_detailed_destination are separate nonadditive views.
- Use the row-specific connected and no-identified-connection observed bases, preserving unscored counts. The pooled Scored observations row is a separate defined subset, not a basis toggle for all destinations.
- Difference direction is connected minus no identified connection. Preserve saved Wilson and Newcombe limits and the original Holm family; do not recompute adjusted p-values after user filtering.
- Keep sparse_group_n_under_10 visible. No institution, field, employer or period cross-filter.

<a id="destination-saved-contrasts"></a>

## Saved destination contrasts and standardization

**Family:** `destinations`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_destination_gap_contrast`](../training_workforce_evidence/TABLES.html#table-dep4-destination-gap-contrast) — outside minus college research-likelihood connection-gap contrast; 3 rows.
- [`DEP4_destination_sector_standardization`](../training_workforce_evidence/TABLES.html#table-dep4-destination-sector-standardization) — saved sector-standardized comparison; 3 rows.
- [`DEP4_scientific_rd_manufacturing`](../training_workforce_evidence/TABLES.html#table-dep4-scientific-rd-manufacturing) — exploratory scientific R&D/manufacturing comparison; 3 rows.

**Proposed controls and supported comparisons**

- saved result type
- specification

**Interpretation and preparation**

- Treat these as separate saved results selected by specification, not results recalculated after destination filters.
- Gap contrast retains inference_scope: exploratory independent-record HC3 normal approximation, not design-based or causal. Its interval cannot be made by subtracting marginal bounds.
- Standardization retains its exact target: 189 known-industry research-doctorate pooled broad-sector distribution. No uncertainty fields are supplied for the standardized contrast.
- Industry comparison retains naics_groups=5417;3254;3345;3391 and threshold 3; do not turn individual constituent industries into supported filters.

<a id="employment-sensitivities"></a>

## Employment specification and population sensitivity tables

**Family:** `employment_profiles`. **Readiness:** mapped existing.

**Sources**

- [`DEP4_specification_transition_summary`](../training_workforce_evidence/TABLES.html#table-dep4-specification-transition-summary) — specification change summary; 18 rows.
- [`DEP4_outside_sensitivity_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-outside-sensitivity-role-profiles) — outside-definition alternative role profiles; 252 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/sensitivity_definition_bases.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-sensitivity-definition-bases-csv) — definition-specific population and missingness bases; 14 rows.

**Proposed controls and supported comparisons**

- saved sensitivity family
- only the categorical combinations provided in each family

**Interpretation and preparation**

- These are supplementary catalog/download views initially; no new primary dashboard controls are required.
- Specification transition directions use only supplied ordered pairs; degree grouping differs from the pooled outside-analysis degree grouping.
- Sensitivity definitions overlap; never add them into a population total. Preserve subset and observed-degree denominator distinctions.

<a id="outside-occupation-breakdowns"></a>

## Released outside occupation breakdowns (catalog)

**Family:** `destinations`. **Readiness:** mapped existing.

**Sources**

- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_role.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-role-csv) — degree-role occupation breakdown; 94 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_destination.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-destination-csv) — degree-destination occupation breakdown; 100 rows.
- [`DEP4/rc_rmi/evidence/employment/outside_university_20261016/occupation_by_destination_and_role.csv`](../training_workforce_evidence/TABLES.html#table-dep4-rc-rmi-evidence-employment-outside-university-20261016-occupation-by-destination-and-role-csv) — grouped destination-role occupation breakdown; 588 rows.

**Proposed controls and supported comparisons**

- catalog table selection; existing source rows only

**Interpretation and preparation**

- Keep as downloadable catalog tables initially. Named occupations require n>=5 within each exact source breakdown; retain pooled_small and unavailable rows including zeros.
- No joining separate marginals to produce new intersections. Detailed destination AND role is not supplied; the joint source supports grouped destinations only.
- Preserve occupation_row_type, soc_code as text, breakdown_n and outside_n; label which percentage is displayed.

<a id="employment-training-linked"></a>

## Employment roles by training field or content

**First-release scope:** Deferred.

**Family:** `employment_profiles`. **Readiness:** needs new aggregate.

**Sources**

- [`DEP4_degree_role_profiles`](../training_workforce_evidence/TABLES.html#table-dep4-degree-role-profiles) — existing role margins do not provide field/content joint cells; 108 rows.

**Proposed controls and supported comparisons**


**Interpretation and preparation**

- Existing degree-role and research-content marginal tables cannot be joined to reconstruct this population.
- If later prepared, use field OR content, with reviewed support/missingness and disclosure rules; do not add combined field-and-content or employer/institution conditioning.

**Remaining work or limitation**

- Requires new joint aggregates and release review; no production dataset or enabled control in the first release.

<a id="rc-rmi-lookup"></a>

## RC-RMI potential occupation-industry lookup

**Family:** `rc_rmi_lookup`. **Readiness:** mapped existing.

**Sources**

- [rc_rmi_scorer/scorer.py](../rc_rmi_scorer/scorer.py)
- [rc_rmi_scorer/instrument.py](../rc_rmi_scorer/instrument.py)
- [rc_rmi_scorer/data/occupation_decisions.csv](../rc_rmi_scorer/data/occupation_decisions.csv)
- [rc_rmi_scorer/data/industry_decisions.csv](../rc_rmi_scorer/data/industry_decisions.csv)
- [rc_rmi_scorer/data/combination_rules.csv](../rc_rmi_scorer/data/combination_rules.csv)
- [rc_rmi_scorer/data/constructs_and_scales.csv](../rc_rmi_scorer/data/constructs_and_scales.csv)
- [rc_rmi_scorer/data/soc_crosswalk.csv](../rc_rmi_scorer/data/soc_crosswalk.csv)
- [rc_rmi_scorer/data/original_two_specifications.json](../rc_rmi_scorer/data/original_two_specifications.json)
- [rc_rmi_scorer/expected_domain_fingerprints.json](../rc_rmi_scorer/expected_domain_fingerprints.json)

**Proposed controls and supported comparisons**

- canonical occupation
- canonical industry
- specification

**Interpretation and preparation**

- Generate later using the released scorer domain command separately for inclusive, no_hospital_override and conservative; verify against expected_domain_fingerprints.json before use.
- 303 instrument occupations x 68 industries = 20,604 potential pairs per specification. No empirical population numerator or denominator exists.
- Preserve canonical codes as strings, 0-4 ordinal axis values and U off-grid. Scores >=3 are likely; neither means neither threshold is met, not absence of research or care.
- Use the instrument occupational catalogs and frozen crosswalk; seven instrument codes are aggregation targets, not distinct O*NET occupations.
- Unmapped/missing input pairs are not ordinal zero or U. Use frozen operations, including clinical gate; do not reapply rules to already resolved scores.
- The original declaration contains two specifications; no_hospital_override is the separately implemented third variant.

**Remaining work or limitation**

- Lookup generation and full-domain verification belong to the later dataset-build step; no generated lookup is included in step 2.

<a id="table-catalog"></a>

## Complete evidence catalog and downloads

**Family:** `table_catalog`. **Readiness:** mapped existing.

**Sources**

- [training_workforce_evidence/data/TABLE_INDEX.csv](../training_workforce_evidence/data/TABLE_INDEX.csv)
- [training_workforce_evidence/code/table_restore.csv](../training_workforce_evidence/code/table_restore.csv)
- [training_workforce_evidence/DISPLAY_MAP.csv](../training_workforce_evidence/DISPLAY_MAP.csv)
- [training_workforce_evidence/DATA_DICTIONARY.csv](../training_workforce_evidence/DATA_DICTIONARY.csv)
- [training_workforce_evidence/data/catalog_displays.json](../training_workforce_evidence/data/catalog_displays.json)
- [training_workforce_evidence/TABLES.html](../training_workforce_evidence/TABLES.html)

**Proposed controls and supported comparisons**

- Search existing table titles, IDs, topics and display labels; filter the catalog without filtering scientific observations.

**Interpretation and preparation**

- Keep all 246 catalog entries accessible, including the 50 detailed display transcriptions. Display snapshots are reported values, not new source data.
- Use table_access export logic to recover ordinary CSV/JSON with original headers and qualifiers. Preserve source-specific reuse notices.
- Keep NIH institution/funding rebuild inputs downloadable without requiring the dashboard to load them.
- The reader is a downloadable workflow component; it supplies no empirical dashboard observations.

## Next step

The first-release definitions and deferrals are settled in [dashboard_scope.md](dashboard_scope.md). Next define the data contract, then implement deterministic exports for the included views. This map does not generate the RC-RMI lookup, construct new employment intersections, calculate funding bands, or modify the prototype. Preserve the complete catalog as the download route for evidence not charted initially.

## Mapping checks

All 246 catalog entries resolved using the existing export logic without writing data exports. All 453 mapped field references exist in their specified source tables. All 170 package files match the source archives byte for byte. Source hashes and the mapping validation receipt are retained locally.
