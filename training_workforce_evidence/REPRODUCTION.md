# Checking the numbers

One command restores every original table from the data files, confirms each matches its recorded hash, and runs all the checks.

```bash
python -m pip install -r code/requirements.txt
python code/verify_all.py --output ../verification-output
```

It takes under a minute on a desktop computer and prints one line per check. Choose an output folder outside this package. Use Python 3.11 or later, and do not use `python -O`, because some checks use assertions. The two packages (NumPy 2.2.6 and SciPy 1.16.3) are needed only for the count fits; without them, add `--skip-fits` and every other check still runs. The numerical routes were run on Windows with Python 3.13.14; other platforms have not been tested.

## Read or export tables

Open [TABLES.html](TABLES.html) for a searchable catalog with the detailed display tables, figure captions, definitions, source links and table-export commands. To export every table into ordinary CSVs and the supplied metadata into JSON files:

```bash
python code/verify_all.py export-tables --output ../readable-tables
```

Choose a new output folder outside this package. The export includes its own catalog, index, dictionary and reuse notices. It needs only the standard library and does not run numerical checks or model fits. DEP2 Tables T3–T11 are exported by applying their documented filters to T15. An individual filtered or full table can also be exported with `export TABLE_ID --output table.csv`.

## What each check does

| Check | Covers | Expected result | Does not do |
|---|---|---|---|
| `table_restore` | Every table against its recorded SHA-256 | All tables match | |
| `measurement` | Coding validation and search capture | 2,284 rows; 1,761 proportions; 549 Wilson intervals; eight kappa values; one Jaccard point | Bootstrap intervals are saved results. The paired labels needed to redraw them are withheld. |
| `rq2_points` | Research-content points and contrasts | 2,528 count rows rebuild 3,376 group points and 5,280 directed contrasts | No institution models, intervals or held-out training are rerun. Those results are saved. |
| `funding_rebuild` | NIH funding arithmetic | All 26,628 exposure rows rebuilt byte for byte; source totals conserved | Original source retrieval and ownership decisions are not redone. |
| `count_tables`, `count_fits`, `count_reference` | Institutional count models | Eight fits run fresh from the panel; six primary targets match the adopted results within stated tolerances | Original sample selection and institutional mapping are not redone. |
| `rq3_aggregates` | Funding reach and content, investigators, opioid comparison | 19,353 numerical checks; 98 saved-inference rows recalculated | Investigator and opioid models are not refit. Covariance, bootstrap, deletion and simulation results are saved. |
| `employment` | Employment aggregates | 14,024 arithmetic checks over 5,751 rows, including all 156 cells of the roles, destinations and funding figure | The 307 individual-level employment observations and associated identifying linkage records are not retained after verification. The supplied aggregates and frozen instrument scorer do not reconstruct the individual matching process. |
| `added_tables` | Printed tables that follow from supplied data | 624 checks: Tables S3.6, S3.7, S3.8 and S3.12, later-doctorate counts, and S4.6 destination, gap, standardization and industry results | The later-doctorate screen itself needs private inputs. Its saved counts are checked for arithmetic only. |

A passing check confirms arithmetic and reproduces the stated fits. It does not establish source access, independent validation or rights in the inputs.

## What cannot be reproduced from this package

- **Retrieval and coding.** Licensed source text is excluded. A new search and coding run needs a reader's own ProQuest TDM Studio access and the reader package in this Zenodo record. A new search establishes a new population and does not claim to match the historical one.
- **Measurement bootstrap.** Paired labels and saved draws are withheld. The original intervals were rechecked privately.
- **Saved model results.** RQ2 institution models, investigator models and opioid models need work-level or person-level records that are not shared.
- **Employment matching.** Individual-level employment observations and associated person, work, employer and profile linkage records are not retained after verification. The supplied aggregates and frozen scorer do not reproduce individual identity matching, human adjudication or actual job duties.
- **Later-doctorate screen.** Candidate links rest on names, which are private. The screen was independently reproduced on 30 October 2026 from the full comparison frame, using private inputs. Candidate links do not establish verified educational histories.
- **Display transcriptions.** The catalog and ordinary display CSVs preserve all 50 detailed tables, including results previously available only as printed values. Exact transcription and file-hash checks preserve those values; they do not rerun the underlying bootstrap, selective checks, deletion analyses or restricted relationship ledger. DISPLAY_MAP.csv retains the original verification limits.

## Companion packages in this record

The reader package has offline synthetic tests, which do not call a live model or use licensed data. Run them in a throwaway copy, because they write fixtures into the package folder. On Windows, keep that copy in a short folder path: the fixtures are deeply nested, and a long path fails with a file-not-found error.

```bash
python tests/test_behavior.py
python tests/test_single_pass.py
```

The scorer package needs only the standard library:

```bash
python scorer.py verify
python -m unittest test_scorer
```

`scorer.py verify` covers the fixed domain of 303 occupations and 68 industries: 20,604 potential pairs under each of three specifications. A score is an instrument classification, not validation of actual duties.

## The supplement

The supplement is supplied in Word and PDF formats. MANIFEST.csv and SHA256SUMS.txt record their hashes for integrity checks.
