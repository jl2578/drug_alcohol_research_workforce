# Single-pass reviewer package data guide

Version **0.3.0-rc2**, 29 October 2026. This guide describes the authorized-input reviewer workflow. The distributed ZIP supplies methods, code and offline checks; it supplies no historical or synthetic input dataset, aggregate results, GOID list, XML, metadata export, worker assignments, checkpoints or credentials. Invented test records are generated at runtime inside the extracted package's ignored `private/` folder.

## Search inputs and private outputs

`search/topical_query.txt` preserves the complete topical query. `search/REVIEWER_SEARCH.md` specifies frame filters, required metadata, missing-abstract handling and work-key deduplication. Run a fresh search in an authorized ProQuest TDM Studio Workbench and supply its XML and Extended Metadata CSV. Record the date, database and exact interface filters. New search results and counts may differ from the original study.

The notebook creates a private roster, exclusions/review flags, evidence reference, assignments and coding plan from those inputs. Required metadata-column presence and at least one assessable record are checked; returned counts are recorded rather than forced to equal a historical target. Keep source records and all generated identifiers, text and record-level outputs within the authorized environment. The results export route is subject to the source's terms; the package's software/document licenses do not license source exports.

## One operative codebook and one scope pass

Read `config/coding/dissertation_codebook_v5_rev15_reproduction.md`. Endogenous-system rules are integrated into its procedure, scope-field, consistency and derivation sections. They are assessed in the same scope pass as the other research aims and scope fields.

The scope response contains all six S1–S4 fields for each unit plus record-level S5. Processing checks the raw response schema, applies deterministic dependencies, validates normalized fields and sentence references, and derives unit/record scope and ordered target IDs. A coded endogenous-system role admits the unit independently of S2/S3 and substance certainty, after structural validation. A valid unknown substance value is a completed scope assessment and stays unknown; it does not trigger a later request.

Content receives frozen scope fields and target IDs and returns C1–C9 only. It cannot provide S4, add aims or revise inclusion. `scope_codes` preserves the complete scope assessment; `content_codes` holds the identity, fixed targets and content fields. Failed delivery is a separate operational state and cannot be reported as scientific uncertainty.

The active configuration is `config/coding/reviewer_single_pass_v15_freeze.json`, with instruments under `config/coding/reviewer_single_pass_v15/` and runner identity `v5_rev15_single_scope_public_rerun_v1`. The freeze and release metadata identify the codebook and actual runtime dependency bytes. `manifest/rule_to_code.json` maps the operative codebook sections to their implementation and public tests. Resume only within the same plan/input/configuration identity; a changed workflow needs a new run.

## Counting

The original study retained a 21,073-record coding roster with 21,045 present abstracts and 28 missing-abstract exceptions. These are contextual historical counts, not quotas for a fresh search. Short present abstracts are assessable; blank/recognized placeholders follow the codebook's missing-abstract exception and receive no model request. Historical source replacements are not inherited by a new search.

Counts from `workflow.account` describe records in the new run. A qualifying record is not automatically a distinct work, award or person. Work-level deduplication and downstream institution/degree/funding analyses require their own appropriate inputs and procedures. No historical population-accounting, all-topic frame, IPEDS or downstream result tables are bundled by this processing ZIP.

## Verification and reproduction boundary

`manifest/files.json` and `SHA256SUMS.txt` identify distributed bytes. `manifest/release.json` identifies source/adaptation and environment provenance. Default notebook cells and offline regression tests run without source records or model calls; the single-pass checks exercise endogenous/ordinary/mixed cases, valid uncertainty, fixed content targets, resume, failures and worker reconciliation.

A clean local check certifies software behavior and package consistency on invented inputs. Authorized Studio UI, model availability, live inference, scientific coding accuracy and an exact replay of the historical full prompt/input identity are separate claims. Follow `README.md` and `LICENSED_INPUTS.md` for the authorized reader route and currently disclosed limits. Final citation/rights review and actual publication remain separate from creating this local candidate.
