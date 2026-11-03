# SPDX-License-Identifier: MIT
"""Actual released tuples, not cross products of marginal selector values."""
from urllib.parse import parse_qsl
from dashboard_common import canonical_json, require


def compile_filters(dataset, payload, contract):
    fields = payload['filter_fields']
    # Unsupported saved rows remain downloadable but cannot generate an available selection.
    eligible = [r for r in payload['rows'] if r['support_status'] != 'unsupported']
    tuples = {tuple(r[f] for f in fields) for r in eligible}
    domains = {f: sorted({t[i] for t in tuples}, key=canonical_json) for i, f in enumerate(fields)}
    codes = {f: {canonical_json(v): i for i, v in enumerate(values)} for f, values in domains.items()}
    encoded = sorted({tuple(codes[f][canonical_json(t[i])] for i, f in enumerate(fields)) for t in tuples})
    return {'format': 'supported-tuples-v1', 'dataset_id': dataset, 'fields': fields,
            'domains': domains, 'tuples': encoded, 'aliases': payload.get('filter_aliases', {}),
            'virtual_filters': payload.get('metadata', {}).get('virtual_filters', {}),
            'forbidden': contract['filter_contract']['forbidden'],
            'combination_rule': contract['filter_contract']['combination_rule'],
            'category_selection_rule': contract['filter_contract']['category_selection_rule'],
            'selection_semantics': 'OR within a field; AND across fields; every selected value must occur in a matching released tuple. Unsupported rows do not grant a selection.'}


def validate_selection(spec, selection):
    normalized = {}
    virtual = {}
    for raw_key, raw_values in selection.items():
        key = spec['aliases'].get(raw_key, raw_key)
        require(key not in normalized and key not in virtual, 'Duplicate/aliased selector: ' + key)
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        require(values and all(isinstance(v, str) for v in values), 'Selectors require nonempty lists of strings')
        values = list(dict.fromkeys(values))
        if key in spec['virtual_filters']:
            require(all(v in spec['virtual_filters'][key]['values'] for v in values), 'Invalid virtual selector: ' + key)
            require(len(values) == 1, 'Virtual selectors accept one value')
            virtual[key] = values[0]
        else:
            require(key in spec['fields'], 'Unknown or forbidden selector: ' + key)
            require(all(v in spec['domains'][key] for v in values), 'Unknown selector value: ' + key)
            normalized[key] = values
    matches = []
    for encoded in spec['tuples']:
        row = {f: spec['domains'][f][encoded[i]] for i, f in enumerate(spec['fields'])}
        if all(row[k] in values for k, values in normalized.items()):
            matches.append(row)
    require(bool(matches), 'Unsupported combination')
    for key, values in normalized.items():
        require(all(any(r[key] == v for r in matches) for v in values), 'Unsupported value within combination: ' + key)
    return {'filters': normalized, 'virtual': virtual, 'matching_tuple_count': len(matches)}


def validate_query(spec, query):
    params = {}
    for key, value in parse_qsl(query.lstrip('?'), keep_blank_values=True):
        params.setdefault(key, []).append(value)
    datasets = params.pop('dataset', [])
    require(datasets == [spec['dataset_id']], 'URL must identify exactly one dataset')
    return validate_selection(spec, params)
