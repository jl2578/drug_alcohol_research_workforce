# Input and output dictionary

All machine data use UTF-8 CSV/JSON. Codes are strings; blanks are unavailable, not numeric zero. The original scales and matrix rationale appear in `data/constructs_and_scales.csv` and `data/combination_rules.csv`.

| Asset | Unit / fields |
|---|---|
| occupation_decisions.csv | One fixed domain occupation. `soc_code_canonical` and `official_soc_title` identify it; `research_final` and `clinical_final` are recorded ordinal 0–4 or U; `directness_final` supplies affirmative-care/no-care/unknown evidence. These are pre-resolution component inputs. |
| industry_decisions.csv | One fixed six-digit NAICS industry. Recorded `research_final` is R0–R3/RU and `clinical_final` is C0–C3/CU. `research_reviewer_a/b` support the declared min/max dissent rule; no reviewer identities or prose ledgers are supplied. |
| original_two_specifications.json | Original historical component declaration, including operation order and grounds; exactly two named specifications. The scorer documents the later third variant separately. |
| combination_rules.csv | One rule per axis × six occupation score states × five context states; 60 unique keys. `output_score` and `rule_id` identify the result and exact matrix rule. |
| soc_crosswalk.csv | A source occupation code/title and target instrument unit code/title plus recorded relationship/rule. Only unique valid targets are mapped automatically. |
| Domain output | One potential pair per specification. Canonical codes, titles, recorded/effective bases and contexts, ordered component paths, clinical gate, final scores, likely flags and joint class. `pair_id` joins occupation and industry codes, never an individual. |
| Scoring input | Exactly two columns: `soc_code` and `naics_code`. No already-resolved scores or personal identifiers. |
| Scoring output | Input row number, specification, source/normalized SOC, NAICS, mapping/application status, research/clinical final scores and joint class. Unknown application leaves all three scoring outputs blank. |
| Joint class | `both`, `research_likely_only`, `clinical_likely_only`, `neither` or `unclassifiable`. If either axis is U, joint class is unclassifiable, although the other axis may remain known. |
| Figure data | Each row is a plot segment with its state, numerator, full observed group denominator and unrounded percent. Zero segments are retained. |

`expected_domain_fingerprints.json` hashes sorted `pair_id`, research score, clinical score and joint class with tab separators and a terminal newline. It is a domain benchmark, not a sampled-person fingerprint.

The historical field name `official_soc_title` is retained for compatibility. Seven instrument-unit codes are project aggregation targets assembled from source occupations, rather than distinct O*NET occupations; the exact list and source-title check are in `NOTICE.md`. The crosswalk makes source occupations and target instrument units explicit.
