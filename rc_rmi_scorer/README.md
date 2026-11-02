# RC-RMI scorer

This package provides a standalone scorer for the fixed RC-RMI occupation–industry instrument. Component version `rc-rmi-standalone-2026-10-30-local-v6`. It is prepared for the combined study-evidence Zenodo record, whose DOI `10.5281/zenodo.23897503` is reserved and will be registered on publication. This scorer has no separate DOI. Python 3.10 or later is sufficient; there are no third-party dependencies, network requests, paid APIs or hidden repository inputs.

## Run

From this extracted folder:

```text
python -B scorer.py verify
python -B -m unittest test_scorer
python -B scorer.py domain --specification inclusive --output ../inclusive_lookup.csv
python -B scorer.py domain --specification no_hospital_override --output ../no_hospital_override_lookup.csv
python -B scorer.py domain --specification conservative --output ../conservative_lookup.csv
python -B scorer.py score --specification inclusive --input fixtures/synthetic_pairs.csv --output ../synthetic_scored.csv
```

Output paths must be new files outside this package. Input CSVs have exactly `soc_code,naics_code`, using quoted strings where needed; never store a person name or source/work key in this example. Codes remain strings, including O*NET decimal extensions. The example pairs are synthetic code combinations and missing/invalid-code cases, not sampled employment observations. Direct domain codes take precedence; another source SOC maps only when the frozen crosswalk has one valid domain target. Missing codes produce blank scores with `missing_pair_applicability_unresolved`; unresolved nonblank pairs receive `unmapped_pair`. Neither becomes zero, instrument U or verified nonapplicability.

## What is reproduced

There are 303 occupation definitions and 68 industry definitions, giving 20,604 **potential pairs** per specification. These are not observed workers. The scorer applies the common mathematics/teaching corrections, industry dissent selection, establishment override and nursing-base specification, then the clinical corroboration gate and all 60 matrix rules. Threshold 3 defines likely research/care; U is outside the ordinal 0–4 scale. No-care violations raise errors, rather than silently capping an inconsistent input.

`data/original_two_specifications.json` is the unchanged original two-specification declaration. `no_hospital_override` is the later application variant: inclusive selection and nursing base, with the establishment override limited to 611310. It is implemented separately without relabeling the historical declaration. The clinical axis is unchanged in all three variants. Repeated runs restart from recorded component inputs; already-resolved occupation scores are not used as raw component decisions.

`expected_domain_fingerprints.json` supplies score benchmarks checked against the fixed historical engine and the retained inclusive/conservative lookups. The tests cover the full domain, all matrix keys, all 25 clinical-gate combinations, thresholds, U, no-care failures, operations, crosswalk/missing cases and hospital-only intermediate changes. The package does not reconstruct individual histories, matching, job duties, employment selection or author adjudication.

## Limits

The instrument reproduces frozen rule application. The study's person, work, employer, profile and identity inputs are not included, so this package does not offer empirical re-scoring or original employment-matching reproduction. The study's employment aggregates and development evidence are in `study_evidence_v9.zip`, supplied alongside this scorer in the same Zenodo record. Development agreement and SDR comparisons do not establish independent individual-duty validation.

See [data dictionary](DATA_DICTIONARY.md), [attribution](NOTICE.md) and [reproduction matrix](REPRODUCTION.md). O*NET provenance is handled in the source notice without treating a later download as proof of historical construction.

## Archive and citation

Creators, in citation order: **Jesse Liss; Maria Davradou**. Their supplied affiliations and this component version are recorded in [CITATION.cff](CITATION.cff). Cite the combined record and identify the RC-RMI scorer component/version when referring specifically to this instrument implementation. The shared DOI identifies the whole deposit, not a separate scorer publication. No public release date is asserted by this draft.

The record is prepared as three coordinated ZIP files:

- `study_evidence_v9.zip` — the supplement, aggregate evidence, result catalog and study-verification code; extracts as `training_workforce_evidence/`.
- `proquest_v5_reproducibility.zip` — the reader-run search/coding workflow; extracts as `proquest_v5_reproducibility/`.
- `rc_rmi_scorer.zip` — this standalone instrument/scorer; extracts as `rc_rmi_scorer/`.

Extract the scorer ZIP and run its commands from `rc_rmi_scorer/`. The scorer remains self-contained; other ZIPs are not runtime dependencies. Reuse scopes and source attributions remain in LICENSE, LICENSE-CC-BY-4.0.txt and NOTICE.md.
