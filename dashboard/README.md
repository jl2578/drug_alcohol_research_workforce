# Dashboard data

The interactive dashboard, datasets and static-data loader are available locally. GitHub Pages deployment remains pending.

Using Python 3.11 or newer, run `python -B -m http.server 8123 --bind 127.0.0.1 --protocol HTTP/1.1` from the repository root, then open **http://127.0.0.1:8123/dashboard/**. See the [interface guide](../docs/dashboard_interface.md).

- **Front pages** (`index.html`, `content.html`, `funding.html`, `careers.html`, `data.html`): one question per page, answer first, at most two controls per chart. They read the same datasets below.
- **Full explorer** (`explore.html`): all 26 datasets with every filter, interval, status column and selection download.

- [Dataset index](metadata/index.json): 26 datasets supporting 25 included views. Fetch this small index first.
- [Build receipt](metadata/build.json): output checksums, row counts, pinned inputs and transformation-code provenance.
- [Ordinary source-table index](metadata/source_exports.json): all 246 released entries, restored with the evidence package's existing export code (242 CSV files and 4 JSON files).
- [ProQuest reader workflow ZIP](downloads/proquest_v5_reproducibility.zip): all 41 pinned reader files. Retrieval and model calls run separately with authorized inputs.
- [Build and integration guide](../docs/dashboard_build.md): commands, JSON decoding, filters and scientific constraints.

Every dataset has a full CSV in `data/`, a JSON shard manifest at the matching `.json` path, and a provenance/definitions manifest in `metadata/datasets/`. Each manifest links a CSVW column dictionary in `metadata/dictionaries/`, including source bindings, status meanings and counts of nonempty values. Browser JSON uses exact string dictionaries and column arrays to reduce repeated text; decoding restores the same canonical records as the CSV. Files are split by dataset and into bounded shards. Selection CSV downloads omit only columns empty for the whole selected subset; the full canonical CSV retains all source columns.

These files derive from the verified published [three-package snapshot](../ZENODO_SOURCE.json), aligned to Zenodo on November 2, 2026. The supplement and all source-package files are preserved byte for byte from the published ZIP contents. Reuse terms remain source-specific; consult each dataset manifest and its linked notices. The RC-RMI lookup enumerates potential occupation–industry combinations, not observed workers.
