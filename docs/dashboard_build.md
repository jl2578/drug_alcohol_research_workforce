# Build and use the dashboard datasets

Step 5 implements the [data contract](dashboard_data_contract.md) locally. It produces 26 datasets for the 25 included views, 246 ordinary source-table downloads, supported filter combinations, and the released reader workflow as a downloadable ZIP. It does not publish a site or execute retrieval, model calls, or new statistical fits.

## Rebuild

Python 3.10 or later is sufficient; the build uses only the standard library. Run from the repository root:

```text
python -B scripts/validate_data_contract.py
python -B scripts/build_dashboard.py
python -B -m unittest discover -s tests -p "test_dashboard_*.py"
node --test tests/dashboard_client.test.mjs
python -B scripts/build_dashboard.py --check
```

Node 18 or later is needed only for the browser-client tests. No Python package installation, credentials, or network access is required. The build imports the preserved evidence export code and scorer with bytecode writing disabled. It verifies all 170 protected files against [their pinned checksums](preserved_components.sha256.json) before loading inputs and again before completing the build.

The build creates files in a temporary directory, validates them, then updates only its managed output paths under `dashboard/`. It refuses to overwrite an existing unmanaged file. `--check` regenerates into a temporary directory and compares every output byte without replacing outputs. A normal rebuild works from a downloaded repository ZIP; a strict `--check` also expects the recorded Git provenance to be available and unchanged.

When changing build code, run the tests, commit that code locally, regenerate the datasets, and then commit the generated files. This lets manifests name the exact transformation commit without a self-referential output commit. File hashes also identify the exact code. No timestamp or absolute machine path is embedded in generated artifacts. Code changes, contract changes, or a different source snapshot require a new build and verification.

## Files and provenance

| Path | Purpose |
|---|---|
| `dashboard/metadata/index.json` | Small entry point listing datasets, row counts and download routes |
| `dashboard/data/{dataset}.csv` | Complete flat downloadable records, including unsupported saved targets with explicit statuses |
| `dashboard/data/{dataset}.json` | Column schema, types, shard paths, hashes and filter domains used to prune downloads |
| `dashboard/data/{dataset}/{part}.json` | Compact browser records with lossless dictionaries for repeated strings |
| `dashboard/metadata/filters/{dataset}.json` | Actual eligible tuples and selector domains; never a Cartesian product |
| `dashboard/metadata/datasets/{dataset}.json` | Scientific definitions, source keys/versions/hashes, rights, transformations and exact source downloads |
| `dashboard/sources/` | Verbatim restored source entries; names are stable hashes of table IDs |
| `dashboard/downloads/proquest_v5_reproducibility.zip` | Deterministic archive of the 41 unchanged reader files |

The generated CSV and decoded JSON contain identical field names, row IDs, values and statuses. JSON `null` represents unavailable/not-applicable numerical cells according to the contract and reason fields; explicitly permitted blank categorical keys remain `""`. CSV readers must use the column types and status fields to distinguish these cases. Saved decimal tokens remain strings, exact counts remain integers, and calculations use 34-digit decimal arithmetic. Display rounding belongs in the future interface.

Each shard has `rows` (arrays in the manifest's column order) and `dictionaries` (optional arrays indexed by column number). A non-null value in a dictionary-encoded column is an index into that column's dictionary. Other values are literal. Use the supplied decoder; do not treat encoded indices as measurements. Partitions are bounded by 1,500 records or roughly 1 MB of uncompressed canonical row content before dictionary encoding. A single unusually large row may exceed that byte target.

Source-level blanks in retained wide saved-result columns remain unprovided source values; columns absent from a heterogeneous source family are not applicable to that family. The manifest's source schema/definitions and original downloads resolve those fields. Canonical value, support and interval statuses govern plotting. Valid points with unavailable intervals remain valid points.

## Connect a static interface

The loader is [data-client.mjs](../dashboard/assets/data-client.mjs). It reads the small index first, then only the chosen dataset's filters, shard manifest and potentially matching shards. A project-site base URL must include the repository directory; relative URLs below handle that automatically when the page is in `dashboard/`.

```javascript
import {createDataClient, availableOptions} from './assets/data-client.mjs';
const data = createDataClient(new URL('./', window.location.href));
const result = await data.load('population_composition');
// result.rows contains full exact records; round only when displaying a value.
const csvForCurrentSelection = result.csv();

// Validate a shared URL using the same rules as interactive controls.
const shared = await data.load('institution_profiles', window.location.search);
// Example: ?dataset=institution_profiles&outcome=C3&institution_selection=...

const spec = await data.filters('employment_connection_profiles');
const options = availableOptions(spec, {}, 'specification');
```

Select multiple values by repeating a URL parameter. Values are ORed within a field and ANDed across fields. Every chosen value must occur in at least one matching released tuple. Unknown fields, unsupported tuples and deferred datasets raise errors; the interface must explain that the selection is unavailable. It must not replace it with zero or silently fall back. Empty source-code categories are legitimate only where explicitly present; `soc_unit_code=` and a bare `soc_unit_code` have the same empty-value interpretation.

Filters hide records and preserve their original denominators and weighting. They never join separate margins into new populations. Unsupported source targets remain in full downloads but do not generate available options; `includeUnsupported: true` may include their rows alongside an otherwise valid selection for diagnostic use.

For institutional count-model results, `interval_family` selects saved bounds for the same six records. Use the explicit accessor:

```javascript
const rates = await data.load('institutional_count_associations',
  {interval_family: 'familywise'});
for (const row of rates.rows) {
  const {value, lower, upper, interval_status} = rates.measure(row);
  // Plot this selected measure. Both original bound families remain in row/CSV.
}
```

`activeFields` names the selected source columns. Canonical stored rows/CSV retain the default pointwise aliases and both original families; selecting a family does not rewrite archived values. The loader never constructs contrast intervals from marginal limits.

## Scientific boundaries

Institutional profiles remain the released period-standardized fitted profiles. They have no period selector. The equal-institution reference always uses the pinned 50 institutions and equal weights; selections never change its roster, mean or denominator. No reference interval is invented.

The RC-RMI build invokes the released scorer for all three specifications, verifies 20,604 potential pairs per specification and all three frozen fingerprints, and preserves score `U` separately from zero, unclassifiable roles and unscored employment. Browser code retrieves the lookup; it does not reimplement the scoring rules.

Employment by training field/content, observed institutional period profiles and funding-band comparisons remain deferred. They have no exports or operational selectors. The initial dashboard can be built from the completed datasets without those extensions.

All three preserved component folders remain the authoritative pinned inputs. A newer archive elsewhere is not automatically adopted. Reconcile any changed submission/deposit package separately before publication, including its supplement, citation metadata and source checksums.
