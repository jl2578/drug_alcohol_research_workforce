# Data and code availability

This is an unpublished candidate associated with the authors' Zenodo draft. DOI `10.5281/zenodo.23897503` is reserved and will be registered on publication. No public availability or tested public download is asserted yet. This is the package's own statement; it does not replace the availability text in the main manuscript.

## What is shared

- Aggregate counts and saved results for the in-scope population, the employment-linked sample and the coding validation. Display CSVs preserve the previously reported detailed tables without adding underlying restricted records.
- A 7,798-row institutional panel for eight fresh count fits. Institutions and retained model membership are intentionally identifiable.
- Public-source NIH funding inputs and the authors' institution mapping.
- Code that checks the supplied numbers. The same Zenodo record includes two additional ZIP components: the ProQuest reader (`proquest_v5_reproducibility.zip`) and RC-RMI scorer (`rc_rmi_scorer.zip`). Each component carries its own execution, input and reuse notices.

## What is not shared

Licensed titles, abstracts and source records; work, person, award and profile bridges; individual employment evidence; paired measurement labels and bootstrap draws; the larger RQ2 saved-result capsule; and internal review records. This statement makes no promise of access on request. Readers who need original source material must obtain their own source authorization.

## Reuse by kind of material

There is no blanket license for the package. [data/TABLE_INDEX.csv](data/TABLE_INDEX.csv) gives the terms for each table and [MANIFEST.csv](MANIFEST.csv) for each file. A license on code or documentation does not extend to neighboring empirical files.

| Material | Terms |
|---|---|
| Original software | MIT, copyright 2026 Training-to-workforce contributors ([text](LICENSE-MIT.txt)) |
| Original narrative, codebooks, dictionaries, table and figure design, and instrument judgments | CC BY 4.0, only to the extent the authors hold those rights ([text](LICENSE-CC-BY-4.0.txt)); retain credit and identify changes |
| Empirical counts, analysis panels, numerical snapshots, result registries and display values | The source-use scope below; no blanket data license |
| NIH, IPEDS and BRDPI facts and the authors' mappings | Public factual sources; CC BY 4.0 only for the authors' protectable contributions. No new copyright or restrictions in facts or federal information. |
| Mixed supplement, empirical figures and deposited display tables | CC BY 4.0 covers original expression only; empirical values and third-party material keep their own status |

## Source-use scope for the empirical files

These summaries are supplied for teaching, learning, research and analysis, including research publication and peer review. They contain no ProQuest citation or index records, source text, or person or work identifiers.

The project reads the current [ProQuest TDM Studio supplemental terms](https://about.proquest.com/en/about/supplemental-terms-of-use-tdm-studio/) (last updated 6 July 2026; checked 20 and 27 October 2026) as supporting this non-substitutive, article-supporting aggregate output. That is the project's own bounded interpretation. It is not a vendor confirmation or an IRB dissemination determination.

The authors grant no commercial-use rights in source-constrained derived data and no rights in the underlying licensed records. This notice claims no copyright in numerical facts, does not sublicense third-party material, imposes no new recipient agreement and waives no independent rights or exceptions. A Creative Commons label does not supply missing third-party rights. Institutional factual data have a different source basis from the joined ProQuest-derived counts, and sharing them together does not extend one file's rights to the other.

## Disclosure limits

- Institutions can be recognized by name, UNITID and funding history. Their keys are not anonymized, and the funding grid does not mask which cells appear in the count panel.
- Exact small counts and their complements are retained. They can reveal that a public dissertation belongs, or does not belong, to the study's research-topic corpus, and a very small institution, year and degree group can identify a public work through outside search. No suppression, rounding or minimum-cell rule is claimed, except that named occupations in the employment tables require at least five records.
- Corpus inclusion, a study classification or a recorded funding connection is not an author's diagnosis, personal substance use, employment outcome or personal receipt of NIH funds.
- Some field-content tables reveal observed degree-field margins that also bear on RQ2. This overlap is declared. Marginal tables cannot be joined into individual records or unsupported intersections.

## Attribution

The study-evidence deposit creators are Jesse Liss and Maria Davradou, in citation order. Their supplied affiliations and the reserved DOI are recorded in [CITATION.cff](CITATION.cff). Retain the separate software and source attributions below and in the license notices.

NIH funding data come from [NIH RePORTER](https://reporter.nih.gov/) and its [API](https://api.reporter.nih.gov/?urls.primaryName=V2.0), with an official comparison recorded on 29 September 2026. Institution names come from [IPEDS](https://nces.ed.gov/ipeds/use-the-data), and real dollars use NIH's BRDPI. Exact sources and vintages are in the provenance tables in [data/nih_funding_rebuild.zip](data/nih_funding_rebuild.zip).

O*NET material is credited to the U.S. Department of Labor, Employment and Training Administration and the National Center for O*NET Development, O*NET 30.3 Database (2026), under CC BY 4.0. O*NET® is a trademark of USDOL/ETA, which has not approved or endorsed these modifications. The scorer component's NOTICE gives the versioned attribution and changes. Occupation and industry classifications use SOC and 2022 NAICS. SDR comparisons refer to NCSES Survey of Doctorate Recipients tabulations. These source publications are not sublicensed here.
