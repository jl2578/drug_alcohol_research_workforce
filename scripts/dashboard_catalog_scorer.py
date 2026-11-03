# SPDX-License-Identifier: MIT
"""Preserve the full evidence catalog and call the released RC-RMI engine."""
import json
import sys
from dashboard_common import canonical_json, require, sha256, source_export_path


def build(ctx):
    catalog = []
    # Definition/display files remain verbatim and downloadable; tables carry exact routes.
    for key, entry in ctx.entries.items():
        raw = ctx.raw_tables[key]
        catalog.append({**entry, 'source_file': 'training_workforce_evidence/' + entry['file'],
                        'source_rows': int(entry['rows']), 'source_columns': int(entry['columns']),
                        'source_table_id': key, 'source_key': canonical_json([key]),
                        'ordinary_download': 'dashboard/' + source_export_path(key),
                        'restored_table_sha256': sha256(raw),
                        'catalog_path': 'training_workforce_evidence/TABLES.html#' + ctx.table_access.anchor(key),
                        'dictionary_path': 'training_workforce_evidence/DATA_DICTIONARY.csv',
                        'display_map_path': 'training_workforce_evidence/DISPLAY_MAP.csv',
                        'display_snapshots_path': 'training_workforce_evidence/data/catalog_displays.json',
                        'rights_notice': 'training_workforce_evidence/DATA_AVAILABILITY.md',
                        'value_status': 'not_applicable', 'support_status': 'not_applicable',
                        'interval_status': 'not_applicable'})
    require(len(catalog) == 246, 'Catalog changed')
    sys.path.insert(0, str(ctx.repo / 'rc_rmi_scorer'))
    import scorer
    scorer.verify_files()
    expected = json.loads((ctx.repo / 'rc_rmi_scorer/expected_domain_fingerprints.json').read_text(encoding='utf-8'))
    lookup = []
    fingerprints = {}
    for specification in scorer.SPECS:
        domain = scorer.domain(specification)
        fingerprints[specification] = scorer.fingerprint(domain)
        require(len(domain) == expected['pairs_per_specification'] == 20604, 'Scorer pair count changed')
        require(fingerprints[specification] == expected['score_fingerprints'][specification], 'Scorer fingerprint changed')
        for row in domain:
            lookup.append({**row, 'occupation': row['soc_code_canonical'], 'industry': row['naics_code_canonical'],
                           'research_axis': row['research_final_score'], 'clinical_axis': row['clinical_final_score'],
                           'joint_role': row['joint_class'],
                           'source_research_likely': row['research_likely'], 'source_clinical_likely': row['clinical_likely'],
                           'research_likely': row['research_final_score'] != 'U' and int(row['research_final_score']) >= 3,
                           'clinical_likely': row['clinical_final_score'] != 'U' and int(row['clinical_final_score']) >= 3,
                           'application_status': 'scored_potential_pair',
                           'source_reference': 'rc_rmi_scorer/expected_domain_fingerprints.json',
                           'source_key': canonical_json([specification, row['soc_code_canonical'], row['naics_code_canonical']]),
                           'value_status': 'available', 'support_status': 'not_applicable', 'interval_status': 'not_applicable'})
    return {
        'table_catalog': {'rows': catalog, 'filter_fields': ['table', 'title', 'backs_displays', 'check'],
                          'metadata': {'search_fields': ['table','title','description','backs_displays'],
                                       'restored_entries': 246, 'csv_entries': 242, 'json_entries': 4,
                                       'detailed_display_snapshots': 50}},
        'rc_rmi_lookup': {'rows': lookup, 'filter_fields': ['specification','soc_code_canonical','naics_code_canonical'],
                          'metadata': {'score_fingerprints': fingerprints, 'pairs_per_specification': 20604,
                                       'population_warning': 'Potential instrument pairs, not observed workers.',
                                       'noncanonical_input': 'Use the released scorer and frozen crosswalk; the browser accepts only exact canonical codes.'}}
    }
