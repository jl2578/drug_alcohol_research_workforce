# Local dashboard interface

Run from this curated repository, not the private research workspace, using Python 3.11 or newer:

```text
python -B -m http.server 8123 --bind 127.0.0.1 --protocol HTTP/1.1
```

Open **http://127.0.0.1:8123/dashboard/** in a browser. Keep the server running while exploring; Ctrl+C in its terminal stops it. Opening the HTML directly with a `file:` URL does not provide the HTTP data loading required by the interface. The [`--protocol` option](https://docs.python.org/3.11/library/http.server.html#command-line-interface) was added in Python 3.11. HTTP/1.1 avoids the response failures observed with the earlier local preview command on this Windows machine; this is a measured local workaround, not a finding about every Python server.

The interface is buildless HTML/CSS/JavaScript. It uses no third-party runtime, CDN, tracking, retrieval or model service. All 26 datasets are accessible through eight topic sections. Mixed result families use tables, the instrument uses score cards, and comparable numerical views use charts with saved intervals where available.

## Controls and consistency

- Choose a topic or view, change filters, and press **Apply selection**. A change preserves the other choices. Incompatible combinations require an explicit correction; populations and overlapping scenarios are not silently broadened. Pending changes and the applied population/scenario are labeled separately. Institution selection supports multiple institutions.
- The chart and table display the same page of up to 20 records, in the same order. Previous/Next update both while retaining the same scale across the entire selection. Category order follows the released order where provided.
- Fitted probabilities are displayed as percentages. Percentages and percentage-point differences use one decimal; rate ratios use three. Rounding applies only to presentation. Exact source values and bounds remain accessible through keyboard/touch detail controls and in CSV. Ratios use a logarithmic axis with a reference at 1.
- Saved sparse-group flags and bases below 30 are labeled as cautions. Values are not suppressed. The below-30 marker is a descriptive dashboard caution, not a claim that a survey reliability standard applies to this study.
- Signed comparisons identify the subtraction direction. Rate-ratio comparisons identify the numerator and reference group rather than being labeled as differences.
- **Download selection** includes every matching record across all pages at original precision. **Full dataset CSV** is the unfiltered canonical dataset. Both keep source units; a fitted probability displayed as a percentage remains a probability in the CSV.
- For institutional count models, selected pointwise/familywise bounds are used in the chart, table and selection CSV. Selection CSV lower/upper aliases match the chosen family and include an explicit `interval_family`; both original bound families remain present. Source records are not mutated.
- Catalog search filters the table and selection download together. Its individual source links resolve to restored CSV/JSON files with recognizable download filenames.
- Shared links preserve applied filters; browser Back restores prior applied selections. Invalid, unknown or deferred selections show an unavailable message without fallback data. Network/file-load failures have a separate message and retry path. Reset remains an explicit action. Local links work only on the computer running the preview server.
- Field, institution, occupation and industry selectors include readable labels from pinned released tables. Original identifiers remain in URLs and downloads. Occupations can be searched by title or code.
- Zero, null, unscored employment and instrument U remain distinct. Valid points remain visible without unavailable intervals.

The fixed 50-institution reference has its own view. Its cohort, weights and values do not change with institution selections elsewhere. The profile definitions link to it. No period control is offered for standardized institutional profiles.

Definitions and source downloads are available below each view. The archive DOI links to the study deposit; publication and package alignment are recorded in `ZENODO_SOURCE.json` and `docs/published_release_verification.json`. Training/content-linked employment, observed institutional period profiles and funding bands remain outside the released scope. The HTML includes [Schema.org Dataset metadata](https://schema.org/Dataset) identifying the source DOI and downloadable CSV distributions. The dashboard exports are derivatives of that deposit, not a new DOI version.

## Verification and release status

Run the source/contract and model regression checks from the repository root:

```text
node --test tests/dashboard_client.test.mjs tests/dashboard_loading.test.mjs tests/dashboard_ui_model.test.mjs tests/dashboard_semantics.test.mjs tests/publication_links.test.mjs
python -B -m unittest discover -s tests -p "test_*.py"
python -B scripts/build_dashboard.py --check
```

The repository includes Chromium browser and axe accessibility regressions in `tests/browser/dashboard.spec.mjs`. Use Node.js 22.12 or newer for the locked test dependencies. Install the pinned development dependencies and browser once, then run:

```text
npm ci
npx playwright install chromium
npm run test:browser
```

Playwright starts `scripts/serve_dashboard.mjs` on **127.0.0.1:8124** and tests beneath the repository prefix `/drug_alcohol_research_workforce/dashboard/`, matching GitHub Pages path resolution. This server serves only the curated repository, rejects traversal and dot paths, and does not list directories. It leaves a separate user preview on port 8123 alone. Browser test output and failure traces go to ignored `test-results/`; they are not study data or release artifacts. These automated checks cover Chromium at desktop and narrow viewport sizes, not every browser, physical phone or screen reader.

Tests must cover the reported failure cases: filter changes preserving populations; distinct award-scenario labels; invariant pagination scales; visible sparse/base cautions; rate-ratio direction and reference; readable definitions and cells; network recovery; URL history; and chart/table/download agreement. Browser checks and accessibility checks supplement model tests. A passing model suite alone does not establish correct labeling or accessible interaction.

Each dataset manifest links a generated CSVW column dictionary, with source bindings, status meanings and nonempty counts. The complete canonical CSV retains its source schema; selection downloads omit only columns empty across the selected rows and preserve every nonempty value, including zero and false.

The build records hashes of the Python transformation scripts and shared JavaScript data client. After changing those files, regenerate the data manifests with `python -B scripts/build_dashboard.py`, even when numerical values are unchanged. Presentation-only edits require browser/model checks but do not change data provenance. The current work is local. Interface work does not edit source-package or supplement contents. The final checks use the checksum-pinned published Zenodo snapshot.

Before public GitHub/Pages release, review and commit all intended interface, test and metadata files, rebuild with the committed transformation code, rerun `--check`, and commit the refreshed generated artifacts. Confirm that the build receipt identifies committed transformation code. Push the reviewed repository and enable Pages only after the local release checks pass; validate deployed routes and downloads separately. A successful local preview does not establish that the Pages URL is live.
