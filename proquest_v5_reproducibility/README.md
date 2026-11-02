# ProQuest v5 reviewer reproducibility package

Version **0.3.0-rc2**, software configuration dated 29 October 2026. This component is for an authorized reviewer or reader **inside ProQuest TDM Studio**. It contains the saved search expression, codebook, scripts, frozen coding configuration and instructions. It contains **no ProQuest records, raw text, prebuilt input dataset, GOID list, worker assignment or credentials**. The reviewer runs the search and creates all private inputs in their own Workbench.

Original software uses [MIT](LICENSE); original documentation and methods use [CC BY 4.0](LICENSES/CC-BY-4.0.txt). Both permit commercial reuse. [License scopes](LICENSES/README.md) distinguish those original materials from separately licensed inputs.

## Combined archive and citation

Creators: **Jesse Liss and Maria Davradou**, in citation order; supplied affiliations are in [CITATION.cff](CITATION.cff) and [CITATION.md](CITATION.md). This reader is one of three ZIP components in the same Zenodo record as `study_evidence_v9.zip` and `rc_rmi_scorer.zip`. The reader upload is `proquest_v5_reproducibility.zip`, with top-level folder `proquest_v5_reproducibility/`, as used in the instructions below.

The combined-record DOI is **`10.5281/zenodo.23897503`**. Cite the combined record and identify reader version **0.3.0-rc2**; consult Zenodo for publication status and the release date. The study's supplement, aggregate evidence and numerical verification code are in the study-evidence ZIP. The standalone occupation–industry scoring instrument is in the RC-RMI scorer ZIP.


## Scientific inclusion and content targets

The [integrated revision-15 codebook](config/coding/dissertation_codebook_v5_rev15_reproduction.md) is the current scientific instrument. Its ordinary procedure, scope-field and derivation sections jointly specify substance-related and endogenous-system research. One scope pass assesses all six S1–S4 fields for every aim and record-level S5. An aim is in scope through the connected substance-topic/purpose criterion or its coded endogenous-system role. Software applies the book's deterministic rules to that same scope response and fixes the ordered target IDs.

All applicable S4 fields are assessed during scope. Unsupported values remain `cannot_determine`; this is a complete assessment and does not reverse endogenous inclusion. Later content coding returns C1–C9 for the fixed targets only. It cannot fill substance fields, add endogenous aims or change any scope field or target. Normalization and validation are deterministic processing of the one scope response. Operational retries are recorded attempts within that same stage.

## Why the study's TDM Studio exports are not distributed

This package's reader-run search design follows [ProQuest's Supplemental Terms of Use – TDM Studio](https://about.proquest.com/en/about/supplemental-terms-of-use-tdm-studio/) (last updated 6 July 2026; checked 5 October 2026). Section 4 prohibits redistribution of citation and index records exported from TDM Studio, which also remain subject to the underlying database terms. Section 1 permits qualifying derived data to be used for research publication and peer review under its conditions; this does not authorize redistribution of the source exports. We therefore distribute the saved query, code, frozen configuration and instructions, without the study's direct exports.

Reviewers and readers must obtain the inputs through their own authorized TDM Studio access: rerun the saved search, create XML and Extended Metadata CSV inputs within their Workbench, and set the notebook's `XML_DIR` and `METADATA_CSV` to those paths. The steps below explain how to run the package with those private inputs.

## Why future search results may differ

ProQuest's [Search Tips](https://www.proquest.com/help/academic/Search_Tips.html) explains that retrieval depends on the matching content and indexing available in ProQuest. Its [RSS/search documentation](https://www.proquest.com/help/academic/rss.html) describes new matching documents, including newly added historical material, and retrieval of current results. For our `NOFT` query, the implication is that additions to indexed coverage or changes to searchable metadata can alter which records match. Newly indexed older dissertations can enter the same 2010–2023 publication window even when the query and date limits are unchanged.

A future execution consequently cannot be expected to return the exact original record set or count. This package supports a new search-derived replication of the documented method; it does not promise identical historical inputs or results. Record your search date, exact query, database, filters and resulting counts. A matching count alone does not establish identical records, and a different count alone does not establish a processing error.

## Step 0 — run your own search and keep its results in TDM Studio

Upload `proquest_v5_reproducibility.zip` to the Workbench's SageMaker home. In its terminal, run `cd ~/SageMaker` and `unzip proquest_v5_reproducibility.zip`. Read `proquest_v5_reproducibility/search/REVIEWER_SEARCH.md`, then execute the complete query in `search/topical_query.txt` against ProQuest Dissertations & Theses Global. Export **your own new search results** as record XML and Extended Metadata CSV into this same Workbench. Note their exact locations, the search time and all interface filters. The CSV is your own search export, not a dataset supplied by this package.

## Step 1 — point the notebook at those results

Open `proquest_v5_reproducibility/START_HERE.ipynb` inside TDM Studio. Run its first code cell to verify the package. In the next code cell, replace the path values with the actual locations of **your** exports; for example:

```python
XML_DIR = Path('/home/ec2-user/SageMaker/my_new_search/xml')
METADATA_CSV = Path('/home/ec2-user/SageMaker/my_new_search/Extended_Metadata.csv')
SEARCH_EXECUTED_AT = '2026-10-03 09:30 UTC'  # use your actual time
INTERFACE_FILTERS = 'PQDT Global; Date Published 2010-01-01 to 2023-12-31'  # your exact selections
SEARCH_RESULT_COUNT = None  # optional: the count Studio displayed, kept as provenance
PREPARE_FROM_MY_SEARCH = True
```

Run that cell once. `workflow.prepare_from_search(XML_DIR, METADATA_CSV, RERUN, ...)` matches the XML and CSV by GOID, applies the rules in `search/REVIEWER_SEARCH.md`, and creates the **new private roster, evidence reference, assignments and coding input** under `private/reviewer_rerun/`. It does not read an author-supplied GOID list or historical reference.

**Preparation does not depend on what a search returns.** ProQuest searches can return different records over time, so result counts are recorded but never compared, and missing values never stop the run. A record found in only one export, repeated in the XML, or missing metadata that a rule needs is excluded with a stated reason. A title that differs between XML and metadata, or a missing author, is flagged for review and the record is kept. Preparation stops only if a required metadata column is absent or no assessable record remains. Before live calls, review `search_audit_PRIVATE.json`, `search_removals_PRIVATE.csv`, `search_review_flags_PRIVATE.csv` and `source_partition/unassessable_goids.json` in the private folder. Do not hand-edit the exports or roster to change these results.

## Step 2 — code and account

Use notebook section 2 for scope, then content, with authorized model access. Revision 15 includes an aim coded `endogenous_system_only` independently of S2/S3 and substance labels. Other aims retain the connected substance-topic/purpose rules. A record enters if any aim qualifies. Unknown substance labels do not reverse endogenous-system inclusion.

GPT-5 codes the complete S1–S5 scope contract once for each newly retrieved assessable record. Software checks the raw schema, fills the codebook's deterministic consequences, validates normalized fields and references, and derives inclusion and ordered qualifying aim IDs. GPT-4o then codes C1–C9 for those targets jointly. It cannot change S1–S5, inclusion, aim/sentence IDs or targets. A substance classification unsupported by the abstract stays `cannot_determine` from scope through content; this does not block supported research-content coding. Content uses temperature 0 and an 8,000-token cap; scope uses low reasoning effort and a 12,000-token cap. Both use the snapshots named below, with seed unset.

Section 3 merges only completed, validated exports. `scope_codes` is the complete scope assessment; `content_codes` contains C1–C9 and the fixed identity/target fields. The merger rechecks target membership and scope dependency identity. Missing/failed delivery remains distinct from scientific uncertainty. Blank/placeholder exceptions retain the existing `not_assessable` wire status. Compatibility file names containing `rev14` do not identify the current instrument; the active freeze and runner identity do.

**Start a new run:** extract this package into a clean folder and use a separately named private plan/output directory. Keep each plan and its checkpoints with the codebook, instruments, workflow and freeze under which they were created. `LICENSED_INPUTS.md` explains recovery and failures.

The package is inert by default: opening and running its default cells makes no live call and reads no licensed record. Do not place private Workbench outputs in a public repository or move raw dissertation content to a local computer. The `.gitignore` excludes `private/`.

## Before paying for model calls

- **Free checks.** From the package folder, `python tests/test_behavior.py` exercises preparation, evidence checks, resume, checkpoint recovery and merging. `python tests/test_single_pass.py` checks endogenous inclusion, scope rules, full scope assessment, fixed targets, unknown labels, content-only outputs and one/two-worker reconciliation. The tests generate invented inputs under `private/`, with no licensed records or model calls. Preparation and its preflight in notebook section 1 also make no model calls.
- **Scale.** Each assessable record needs one GPT-5 scope request, and each qualifying record one GPT-4o content request. Estimate workload from your search results and the request rate and quota available in your Workbench.
- **Cost.** The runner has no record limit. After the first few hundred scope responses, read `usage_by_stage` in `worker_1_output/production_progress.json` to project tokens and cost. The run can be interrupted and resumed from its checkpoint (`LICENSED_INPUTS.md`).
- **Model availability.** The active reader configuration requests GPT-5 (2025-08-07) for scope and GPT-4o (2024-08-06) for content. Offline package tests do not establish authenticated model availability. Verify both snapshots in your authorized TDM Studio session before paying for a run. A substitute model requires a separately recorded configuration.

## What this reproduces

Preparation builds a new private roster from the reviewer's own XML and metadata exports. It applies the documented filters and work-key deduplication, freezes evidence hashes, partitions workers and runs an evidence preflight. The main production runner has the bounded HTTP 400 record safeguard integrated into scope and content. Confirmed content-policy refusals become explicit record failures for later review; unresolved failures are never relabeled as model-coded uncertainty. The codebook, prompts, schemas, scope processing and validation have versioned hashes.

A fresh search can retrieve a different set of records. The original overlapping brief-citation pass files, exact pass dates and some interface filters are unavailable, so a new combined-query run is a **new search-derived replication**, not an exact replay of the historical evidence identity. Search membership alone does not establish inclusion; software applies revision-15 rules to the scope-stage fields. Historical results, final v5 population counts, institution mapping and IPEDS displays are not bundled as datasets in this reviewer processing ZIP.

The active codebook is `config/coding/dissertation_codebook_v5_rev15_reproduction.md`. `config/coding/reviewer_single_pass_v15_freeze.json` pins that book, instruments under `config/coding/reviewer_single_pass_v15/`, and the actual runtime dependencies. Both scope and C1–C9-only content instructions are generated from the book. `manifest/rule_to_code.json` connects operative sections to the packaged scope processor and public checks. Runner identity is `v5_rev15_single_scope_public_rerun_v1`. This search-derived reader configuration does not establish byte-identical replay of the study's full prompt/input identity or recreate its model judgments. Offline software checks do not establish scientific coding accuracy.

Source hashes and script adaptations are listed in `manifest/release.json`. The package supports method replication using the reader's inputs; the study's human/model reference judgments, scientific datasets and results are not distributed or replaced by a reader run.

`manifest/files.json` and `SHA256SUMS.txt` identify distributed bytes. `tests/test_behavior.py` generates its own temporary invented records; there are no input fixtures in the release. Current study counts are documented in Supplement S1; a fresh search-derived run is not required to match them.
