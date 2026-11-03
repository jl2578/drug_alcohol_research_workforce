# Dashboard data

The datasets and static-data loader are prepared locally. The visual dashboard and GitHub Pages deployment remain to be built.

- [Dataset index](metadata/index.json): 26 datasets supporting 25 included views. Fetch this small index first.
- [Build receipt](metadata/build.json): output checksums, row counts, pinned inputs and transformation-code provenance.
- [Ordinary source-table index](metadata/source_exports.json): all 246 released entries, restored with the evidence package's existing export code (242 CSV files and 4 JSON files).
- [ProQuest reader workflow ZIP](downloads/proquest_v5_reproducibility.zip): all 41 pinned reader files. Retrieval and model calls run separately with authorized inputs.
- [Build and integration guide](../docs/dashboard_build.md): commands, JSON decoding, filters and scientific constraints.

Every dataset has a full CSV in `data/`, a JSON shard manifest at the matching `.json` path, and a provenance/definitions manifest in `metadata/datasets/`. Browser JSON uses exact string dictionaries and column arrays to reduce repeated text; decoding restores the same canonical records as the CSV. Files are split by dataset and into bounded shards.

These files derive from the pinned [three-package snapshot](../ZENODO_SOURCE.json). The supplement and all source-package files remain unchanged. Reuse terms remain source-specific; consult each dataset manifest and its linked notices. The RC-RMI lookup enumerates potential occupation–industry combinations, not observed workers.
