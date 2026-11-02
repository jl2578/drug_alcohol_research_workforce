# First-release dashboard scope

Step 3 decisions, 2 November 2026. These resolve the scope questions in the [view-to-table map](dashboard_view_map.md). The [machine-readable decisions](dashboard_scope.json) pin the source versions, institution roster and benchmark definition. No dashboard data or interface is generated in this step.

## Decisions

| Area | First-release decision |
|---|---|
| Institution profiles | Use the saved period-standardized fitted profiles in DEP2 T10. Label them as fitted and omit the period, degree and field selectors for this view. |
| Institutional reference | Add a descriptive average of the same 50 institutions' fitted profiles, with equal institution weights. Define it here; calculate it during the data build. |
| Observed institution profiles by period | Deferred. T14 supplies coverage counts, not the missing content-category numerators. |
| Employment by training field/content | Deferred until reviewed joint aggregates exist. Existing margins cannot supply these intersections. |
| Funding-band comparisons | Deferred until the funding measure, bands and joint comparison populations are defined and validated. |

The other mapped views retain their source-specific controls and limitations. There are 25 views in preparation scope and three deferred extensions. This is a build scope, not a claim that 25 views are already operational.

## Institution profiles

Use the label **Fitted institutional research-content profiles**. Explain that the supplied profiles combine 2010–2016 and 2017–2023 with equal period weighting, while retaining degree and field composition. They do not represent institutional quality rankings or causal effects.

Allow outcome, institution selection/search and category visibility. Remove or disable the period, degree, field and custom-year controls for this view, and reject those unsupported states in shared URLs. Other views keep the period controls their sources support.

Use T10 `unit_id` with `outcome` to join T12 `institution_id` with `outcome`. The embedded T10 `institution_id` is blank on 1,000 valid rows. Keep T14's two period-specific coverage rows as explanatory metadata so the join does not duplicate fitted values. Earlier/later work counts are not denominators for recomputing the fitted profile.

All 2,200 supplied points are supported and finite. Sixty lack reportable interval bounds; show the valid points with the saved interval-unavailable status. Do not replace their missing bounds with diagnostic bounds or remove their points.

## Fixed institutional reference

Use the label **Average fitted profile (50 institutions, equal weights)**.

The cohort is exactly the same fixed 50-member T12 roster for C3, C4, C5 and C8. All 200 outcome–institution support rows have `profile_supported=1`; all 2,200 T10 points have `report_supported=1`. The sorted roster and its checksum are pinned in `dashboard_scope.json`.

For each outcome and category, calculate:

```text
benchmark probability = sum of the 50 saved fitted probabilities / 50
benchmark percentage  = 100 × benchmark probability
```

Use the saved points at their source precision. Each institution receives weight 1/50, regardless of its work count. Institution selection and category visibility must not change the reference; selected institutions remain in it. No refitting or reselection of top institutions is involved.

The reference has no confidence interval or significance test. Marginal institutional bounds cannot establish its uncertainty, and they must not be averaged. Missing profile intervals do not invalidate valid points. C8 categories remain nonexclusive and must not be renormalized to total 100%.

If a required supported point is missing, mark that outcome/category reference unavailable. Do not silently drop an institution, fill zero or change the weights. Any cohort change requires an explicit scope/version revision. This reference describes the fixed contributor cohort, not all institutions nationally.

## Deferred extensions

Keep the three deferred extensions out of operational controls and URL states. Retain their entries in the source map as later work; their absence does not remove any existing table from the complete catalog.

- **Observed institutional-period profiles:** need actual institution-period-category counts and eligible bases, plus the observed estimand and fixed-cohort definition.
- **Training-linked employment:** need reviewed joint aggregates for field OR content, with observation/scoring bases, missingness and disclosure rules. Do not combine field and content or infer intersections by joining margins.
- **Funding bands:** need a named measure, units, window, band boundaries and joint population. Distinguish project-count exposure from dollars and account for zero/missing values and overlapping exposures before generating comparisons.

## Implementation handoff

Next define the dataset contract and build exports for the included views. The benchmark will be a new documented dashboard derivation from released fitted points; it will not be inserted into the evidence package or supplement. Validate selection invariance, fixed roster membership, missing-input behavior and chart/table/download agreement during implementation.

The three source packages, the frozen Word/PDF supplement, and the original synthetic prototype remain unchanged. The `dashboard/` folder still contains only `.gitkeep`. Nothing has been uploaded or published.
