# SPDX-License-Identifier: MIT
"""CSVW column metadata derived from the pinned contract and source columns."""
import json


COMMON = {
    'row_id': 'Stable dataset-specific identifier calculated from the declared output key.',
    'value': 'Canonical estimate in the units column; stored precision is retained. Fitted probabilities remain 0–1 in CSV and are displayed as percentages by the interface.',
    'lower': 'Saved lower interval endpoint in source units. Consult interval_status and interval_scope; not reconstructed from separate marginal intervals.',
    'upper': 'Saved upper interval endpoint in source units. Consult interval_status and interval_scope; not reconstructed from separate marginal intervals.',
    'units': 'Units of the canonical value and endpoints, before display-only percentage conversion.',
    'numerator': 'Count or structured counts contributing to the measure, as defined by the dataset contract. Null for fitted estimates without an empirical numerator.',
    'denominator': 'Base or structured group bases defined in the dataset contract; filtering categories does not change these bases.',
    'source_key': 'JSON serialization of the native source key. Paired or derived records may contain multiple contributing keys.',
    'source_table_id': 'Identifier of the released source table; download it using this dataset manifest’s source_download_routes.',
    'source_reference': 'Path to the released source or instrument definition.',
    'support_status': 'Scientific support status; unsupported is distinct from zero and from missing.',
    'value_status': 'Availability of the point estimate. Consult unavailable_reason for exclusions or missing values.',
    'interval_status': 'Availability of the saved uncertainty interval; an unavailable interval does not by itself invalidate an available point estimate.',
    'unavailable_reason': 'Released or contract-defined reason the value is unavailable.',
    'interval_reason': 'Released or contract-defined reason the uncertainty interval is unavailable.',
    'denominator_status': 'Whether an empirical denominator is applicable and available for this measure.',
    'denominator_reason': 'Explanation of the denominator’s applicability or availability.',
    'category_order': 'Released category order; used for display within otherwise identical groups.',
    'category': 'Released category identifier. Where supplied, category_label and category_order give its label and within-group display sequence.',
    'pvalue': 'Saved p-value. Its hypothesis and any multiplicity adjustment follow the source table and estimate family.',
    'support_PIs': 'Number of principal investigators contributing to the saved participation estimate.',
    'sparse_flag': 'Preserved source warning for sparse group support. It is not a suppression instruction.',
    'sparse_group_n_under_10': 'Source indicator that at least one comparison group has fewer than ten observations.',
    'specification': 'Released scoring specification, including its own research/clinical rules.',
    'basis': 'Observed or scored percentage base; unscored employment and instrument U are distinct.',
    'research_axis': 'Research score 0–4 or U. U denotes insufficient information and is not an ordinal score.',
    'clinical_axis': 'Clinical score 0–4 or U. U denotes insufficient information and is not an ordinal score.',
    'ordinary_download': 'Repository-relative route to the recovered source table.',
    'cohort_n': 'Number of institutions in the fixed reference cohort; independent of interface selections.',
    'member_weight': 'Equal weight assigned to each member of the fixed institution cohort.',
}


def describe(value):
    if isinstance(value, dict):
        return '; '.join(f'{k}: {describe(v)}' for k, v in value.items())
    if isinstance(value, list):
        return '; '.join(describe(v) for v in value)
    return str(value)


def dictionary(dataset, rows, fields, contract, ctx):
    sources = sorted({s['table_id'] for s in contract['primary_sources'] + contract['support_sources']})
    source_columns = {table: set(ctx.tables[table][0]) if ctx.tables.get(table) else set() for table in sources}
    columns = []
    for field in fields:
        binding = contract['field_bindings'].get(field)
        native = [table for table, names in source_columns.items() if field in names]
        nonempty = sum(row[field] is not None and row[field] != '' for row in rows)
        description = COMMON.get(field)
        if binding is not None:
            description = (description + ' ' if description else '') + 'Contract binding: ' + describe(binding) + '.'
        elif not description:
            if native:
                description = f'Released source column {field}, retained from ' + ', '.join(native) + '. Its interpretation follows those source tables and this dataset’s contract.'
            else:
                description = f'{field.replace("_", " ").capitalize()}; an adapter field defined by this dataset’s transformation and field bindings in the linked contract.'
        if not nonempty:
            description += ' Empty for every record in this dataset; retained in the complete CSV for source-schema compatibility and omitted from compact selection downloads.'
        if field in ('numerator', 'denominator'):
            description += ' Dataset definition: ' + describe(contract[field]) + '.'
        columns.append({'name': field, 'titles': field.replace('_', ' ').capitalize(),
                        # Preserve lexical decimals, identifiers, valid blanks and U.
                        'datatype': 'string', 'null': [], 'dc:description': description,
                        'schema:additionalProperty': {'@type': 'schema:PropertyValue',
                                                      'schema:name': 'nonempty_rows', 'schema:value': nonempty}})
    return {
        '@context': ['http://www.w3.org/ns/csvw', {'@language': 'en'}],
        'url': '../../data/' + dataset + '.csv',
        'dc:title': dataset.replace('_', ' ').capitalize(),
        'dc:description': contract['row_grain'],
        'dc:source': 'https://doi.org/10.5281/zenodo.23897503',
        'schema:subjectOf': ['../../../docs/dashboard_data_contract.json', '../datasets/' + dataset + '.json'],
        'dialect': {'encoding': 'utf-8', 'delimiter': ',', 'header': True},
        'tableSchema': {'columns': columns, 'primaryKey': 'row_id'},
        'notes': [
            'All cells are described as lexical strings to preserve source decimal precision and codes. Parse measures using units and status fields.',
            'A blank CSV cell alone does not identify missingness: valid blank keys, structurally inapplicable fields and unavailable values are distinguished by the dataset contract, status columns and companion JSON.',
            'Source units and values are unchanged; the interface converts probabilities to percentages only for display.',
            'Field bindings: ' + describe(contract['field_bindings']),
            'Reuse terms remain source-specific; see the dataset manifest and released access notices.'
        ]
    }
