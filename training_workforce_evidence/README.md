# Training to workforce: supplement and evidence

This package accompanies **Linking research content, NIH funding, and employment broadens scientific workforce evaluation: An application to U.S. drug and alcohol research**. It holds the S1–S4 scientific supplement, complete deposited tables and figures, aggregate data, and the code that checks them.

Study-evidence component version `2026-11-02-local-v9`. Creators: **Jesse Liss and Maria Davradou**, in citation order. The shared Zenodo DOI **`10.5281/zenodo.23897503`** identifies the combined record containing this evidence package, the ProQuest reader and the RC-RMI scorer. The DOI was reserved during preparation; no separate component DOI is assigned.

## What to read

| File | Use it to |
|---|---|
| [supplement/Supplement_S1_S4.pdf](supplement/Supplement_S1_S4.pdf) | Read the methods, tables and figures (also in [Word](supplement/Supplement_S1_S4.docx)) |
| [TABLES.html](TABLES.html) | Read the deposited tables and figure captions, find definitions and source links, and export tables |
| [DISPLAY_MAP.csv](DISPLAY_MAP.csv) | Look up the data and check route for a particular table or figure |
| [DATA_NOTES.md](DATA_NOTES.md) | See how particular tables are built and what to watch for when using them |
| [REPRODUCTION.md](REPRODUCTION.md) | Check the numbers with one command, and see what cannot be reproduced |
| [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md) | See what is shared, what is excluded and how each kind of file can be reused |

<a id="find-evidence"></a>

## The data

| File | What it holds |
|---|---|
| [data/population.csv](data/population.csv) | The in-scope population: accounting, coverage, counts, and cuts by funding connection |
| [data/employment.csv](data/employment.csv) | The employment-linked sample: roles, occupations and destinations |
| [data/validation.csv](data/validation.csv) | How the coding compares with human readers |
| [data/institution_panel.csv](data/institution_panel.csv) | Institution-year counts and funding, the input to the count models |
| [data/results.csv](data/results.csv) | Saved estimates for funding, investigators, opioid research and held-out checks |
| [data/rq2_estimates.csv](data/rq2_estimates.csv) | Every research-content estimate with its interval (DEP2 Table T15) |
| [data/nih_funding_rebuild.zip](data/nih_funding_rebuild.zip) | NIH funding tables and code, needed only to rebuild the panel's funding column |
| [data/additional_results.zip](data/additional_results.zip) | Additional evidence and metadata. TABLE_INDEX.csv records the source used for each table; the checks read most of them. |
| [data/industry_focus.csv](data/industry_focus.csv) | Section S4.6 exploratory scientific R&D/manufacturing counts under three scoring specifications |
| [data/destination_connection.csv](data/destination_connection.csv) | Table S4.15 and Section S4.6: research roles by employment destination and funding connection, under three scoring specifications |
| [data/destination_gap_contrast.csv](data/destination_gap_contrast.csv) | Table S4.15 Panel B: outside versus college/university gap contrast |
| [data/destination_standardization.csv](data/destination_standardization.csv) | Table S4.15 Panel B: sector-standardized connection difference |
| [data/TABLE_INDEX.csv](data/TABLE_INDEX.csv) | Every table: where it is, its size, what it backs and how it can be reused |
| [code/table_restore.csv](code/table_restore.csv) | Used only by the checks: how each table is stored, where it is rebuilt and its expected hash |
| [DATA_DICTIONARY.csv](DATA_DICTIONARY.csv) | What each column means |

These are saved results as well as data, because the work-level records cannot be shared. Counts can rebuild point estimates. Many intervals and model results are supplied as saved numbers; eight institutional count fits can be run afresh. See [REPRODUCTION.md](REPRODUCTION.md).

### Open ordinary tables

Open [TABLES.html](TABLES.html) in a browser to search by table title, display label or topic. It works offline. To export every table as an ordinary CSV with its own column headers, into a new folder outside this package (Python's standard library is enough):

```bash
python code/verify_all.py export-tables --output ../readable-tables
```

To export one table, use the command in its catalog entry, for example:

```bash
python code/verify_all.py export DEP2_T1_outcome_coverage --output table.csv
```

`population.csv`, `employment.csv`, `validation.csv` and `results.csv` each hold many tables: `table` names the table, `row` = 0 holds its column names, and later rows hold its values.

### Labels

DEP1–DEP4 name the corpus/measurement, research-content, funding, and employment table families. The supplement cites labels such as "DEP2 Table T20" and "DEP1-E09". Find them in the catalog or DISPLAY_MAP.csv. The catalog preserves all 50 detailed display tables with captions and qualifications. Display transcriptions preserve the reported values and do not independently reproduce withheld source records. TABLE_INDEX.csv gives the source and any filter for every table. Older display labels, such as SM4.T4a, are in the `former_label` column of DISPLAY_MAP.csv.

<a id="separate-deposits"></a>
<a id="companion-packages"></a>

## Companion packages in this record

Download the other ZIP components from the same Zenodo record. They remain independently runnable and have their own component versions.

- `proquest_v5_reproducibility.zip` extracts to `proquest_v5_reproducibility/`: saved query, codebook, prompts, notebook and workflow for a new authorized ProQuest TDM Studio search/coding run (version `0.3.0-rc2`).
- `rc_rmi_scorer.zip` extracts to `rc_rmi_scorer/`: the standalone RC-RMI occupation–industry scorer (version `rc-rmi-standalone-2026-10-30-local-v6`).

This evidence ZIP is `study_evidence_v9.zip`, extracting to `training_workforce_evidence/`. Cite the combined record and identify the component/version used. The legacy navigation anchor is retained for existing references.

## Files and citation

[MANIFEST.csv](MANIFEST.csv) lists every file with its size, hash and reuse terms. From this folder, `sha256sum -c SHA256SUMS.txt` checks them (`shasum -a 256 -c SHA256SUMS.txt` on macOS). [CITATION.cff](CITATION.cff) records the confirmed creators, affiliations, version and reserved DOI. The actual public release date will be added on publication.
