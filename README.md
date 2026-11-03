# Drug and alcohol research workforce

Data, code, and supplementary materials for **Linking research content, NIH funding, and employment broadens scientific workforce evaluation: An application to U.S. drug and alcohol research**, by Jesse Liss and Maria Davradou.

This repository contains the three expanded components from the finalized combined Zenodo upload set, version `2026-11-02-local-v9`. The component files are preserved byte for byte. [ZENODO_SOURCE.json](ZENODO_SOURCE.json) records the source archives and checksums.

## Start here

| Folder | Contents |
|---|---|
| [training_workforce_evidence](training_workforce_evidence/README.md) | Frozen S1–S4 supplement, aggregate and institutional data, saved results, figures, table catalog, and verification/export code |
| [proquest_v5_reproducibility](proquest_v5_reproducibility/README.md) | ProQuest TDM Studio reader workflow, saved query, codebook, prompts, schemas, notebook and synthetic tests |
| [rc_rmi_scorer](rc_rmi_scorer/README.md) | RC-RMI occupation–industry instrument, scoring rules, crosswalk and standalone scorer |
| dashboard/ | Reserved for the future GitHub Pages dashboard; currently contains only an empty `.gitkeep` placeholder |

For the evidence, start with the [table catalog](training_workforce_evidence/TABLES.html), [data notes](training_workforce_evidence/DATA_NOTES.md), and [reproduction guide](training_workforce_evidence/REPRODUCTION.md). Download or clone the repository and open `TABLES.html` in a browser to use the interactive catalog. GitHub Pages has not been configured as part of this preparation.

The author-frozen [supplement PDF](training_workforce_evidence/supplement/Supplement_S1_S4.pdf) and [Word file](training_workforce_evidence/supplement/Supplement_S1_S4.docx) are included unchanged.

## Reproduction

Each component README provides its commands and requirements. The evidence supports table export, aggregate arithmetic checks and eight institutional count-model fits. Many other estimates, intervals and diagnostics are supplied as saved results. The reader requires separately authorized ProQuest inputs and supports a new method replication, not an identical historical retrieval. The scorer operates on potential occupation–industry pairs, not individual employment records.

Run outputs outside the preserved component folders. Run reader synthetic tests in a disposable copy, as described in its README.

## Citation and archive

Use [CITATION.cff](CITATION.cff) for the combined record and identify the component version used. The shared DOI is [10.5281/zenodo.23897503](https://doi.org/10.5281/zenodo.23897503). It was reserved during package preparation; consult Zenodo for publication status and the release date. The three components retain their own versions and citation metadata.

## Access and reuse

Licensed ProQuest source records/text, identifying linkage files and individual employment records are excluded. See the [data availability statement](training_workforce_evidence/DATA_AVAILABILITY.md) for the released materials and reproduction limits.

There is no blanket license over the repository. Original software is MIT licensed; original documentation, codebooks, instrument judgments and display expression use CC BY 4.0 within the authors' stated rights. Empirical and third-party material retains its source-specific status. Consult each component's licenses, notices and manifests.

Dashboard development will take place outside the three preserved component folders. No dashboard data, synthetic mock-up or application has been added yet.

The [dashboard view-to-table map](docs/dashboard_view_map.md) identifies the released sources, supported filters, denominators and remaining definition/data gaps. Its [machine-readable companion](docs/dashboard_view_map.json) records exact fields and source checksums. These are preparation documents; the dashboard folder remains an empty placeholder.

[First-release scope decisions](docs/dashboard_scope.md) adopt fitted institutional profiles and a fixed equal-institution reference, and defer the three extensions requiring new aggregates. Dataset and interface implementation remain pending.

The [data contract](docs/dashboard_data_contract.md) and [machine-readable specifications](docs/dashboard_data_contract.json) define the rows, keys, measures, statuses and provenance for those datasets. Run `python -B scripts/validate_data_contract.py` to check the contract against the released sources without producing exports.
