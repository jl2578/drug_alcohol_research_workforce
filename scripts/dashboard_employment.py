"""Deterministic employment adapters over the preserved released tables."""
from collections import defaultdict
from decimal import Decimal

from dashboard_common import canonical_json, source_row

OUTSIDE = 'DEP4/rc_rmi/evidence/employment/outside_university_20261016/'
DESTINATION = OUTSIDE + 'destination_role_profiles.csv'
ALL_OUTSIDE = OUTSIDE + 'outside_role_profiles.csv'
COUNT_NAMES = {'n', 'n_known_industry', 'total_observations', 'connected_observations',
               'no_identified_connection_observations', 'connected_likely_research',
               'no_identified_connection_likely_research', 'research_score_threshold',
               'competition_rank', 'count_tie_size', 'named_occupation_categories_reported_n',
               'records_in_named_occupation_categories'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _is_count(name):
    return name in COUNT_NAMES or name.endswith('_n')


def _is_number(name):
    return (_is_count(name) or 'pct' in name or 'percent' in name or name.endswith('_pp')
            or name.endswith('_p') or name in {'fisher_two_sided_p', 'holm_p_within_dimension_spec'})


def _base(table, row, key):
    """Keep exact source tokens beside typed native fields and source lineage."""
    result = dict(source_row(table, row, key))
    for name, value in row.items():
        result['source_' + name] = value
        if _is_number(name):
            result[name] = None if value == '' else int(value) if _is_count(name) else value
            result[name + '_status'] = 'unavailable' if value == '' else 'available'
            result[name + '_reason'] = 'not_provided_in_released_source' if value == '' else None
        else:
            result[name] = value
    return result


def _point(row, value, numerator, denominator, units='percent'):
    row.update(value=value, numerator=numerator, denominator=denominator, units=units,
               support_status='supported', value_status='available' if value is not None else 'unavailable',
               unavailable_reason=None if value is not None else 'not_provided_in_released_source',
               interval_status='not_computed', interval_type='none_descriptive', lower=None, upper=None,
               interval_unavailable_reason='not_supplied_for_descriptive_measure',
               estimate_type='saved_descriptive_proportion', numerator_status='available' if numerator is not None else 'not_applicable',
               numerator_reason=None if numerator is not None else 'no_single_numerator_for_measure')
    return row


def _interval(row, lower, upper, kind):
    available = lower is not None and upper is not None
    row.update(lower=lower, upper=upper, interval_type=kind,
               interval_status='available' if available else 'unavailable',
               interval_unavailable_reason=None if available else 'not_provided_in_released_source')


def _index(rows, key):
    index = {}
    for row in rows:
        item = tuple(row[k] for k in key)
        _require(item not in index, 'Duplicate support key: ' + repr(item))
        index[item] = row
    return index


def _spec(ctx, dataset_id):
    return next(d for d in ctx.contract['datasets'] if d['id'] == dataset_id)


def _keys(ctx, dataset_id):
    return {s['table_id']: s['key'] for s in _spec(ctx, dataset_id)['primary_sources']}


def _result(rows, filters, **metadata):
    return {'rows': rows, 'filter_fields': filters, 'metadata': metadata}


def _role_rows(table, rows, keys, observed_value, scored_value, observed_base, scored_base,
               state_field, label_field, all_outside=False):
    output = []
    for source in rows:
        for basis, val, den in [('observed', observed_value, observed_base), ('scored', scored_value, scored_base)]:
            row = _base(table, source, keys)
            _point(row, row[val], row['n'], row[den])
            row.update(basis=basis, category=source[state_field], category_label=source[label_field],
                       denominator_basis=basis, denominator_unit='observed_records' if basis == 'observed' else 'scored_records')
            if all_outside:
                row.update(destination='all_outside', destination_dimension='all_outside', destination_label='All outside')
            if basis == 'scored' and source[state_field] == 'unscored':
                row.update(value=None, numerator=None, value_status='not_applicable',
                           unavailable_reason='unscored_state_excluded_from_scored_basis',
                           numerator_status='not_applicable', numerator_reason='unscored_state_excluded_from_scored_basis')
            output.append(row)
    return output


def build(ctx):
    results = {}
    table = 'DEP4_degree_role_profiles'
    keys = _keys(ctx, 'employment_roles')
    rows = _role_rows(table, ctx.tables[table], keys[table], 'pct_observed', 'pct_scored',
                      'observed_n', 'scored_n', 'joint_state', 'joint_state_label')
    results['employment_roles'] = _result(rows, ['degree_group', 'specification', 'basis', 'joint_state'])

    table = 'DEP4_occupation_frequencies'
    keys = _keys(ctx, 'employment_occupations')
    coverage = _index(ctx.tables['DEP4_occupation_degree_coverage'], ['degree_group'])
    rows = []
    for source in ctx.tables[table]:
        context = coverage[(source['degree_group'],)]
        _require(source['observed_degree_n'] == context['observed_degree_n'], 'Occupation coverage base mismatch')
        if source['occupation_status'] == 'coded':
            _require(bool(source['soc_unit_code']) and int(source['n']) >= 5, 'Invalid named occupation release')
        else:
            _require(source['occupation_status'] in ('aggregate_residual', 'unavailable') and source['soc_unit_code'] == '', 'Invalid aggregate occupation key')
        row = _base(table, source, keys[table])
        _point(row, row['percent_within_degree'], row['n'], row['observed_degree_n'])
        row.update(category=canonical_json([source['occupation_status'], source['soc_unit_code']]),
                   category_label=source['occupation_title'], reporting_status=source['occupation_status'])
        row['coverage_context'] = canonical_json({k: int(v) if _is_count(k) and v else v for k, v in context.items()})
        rows.append(row)
    results['employment_occupations'] = _result(rows, ['degree_group', 'occupation_status', 'soc_unit_code'])

    keys = _keys(ctx, 'outside_destinations')
    coverage = _index(ctx.tables[OUTSIDE + 'observation_bases.csv'], ['degree_group'])
    groups = defaultdict(list)
    for source in ctx.tables[DESTINATION]:
        if source['destination_dimension'] == 'grouped':
            groups[(source['degree_group'], source['destination_dimension'], source['destination'])].append(source)
    rows = []
    keep = ['degree_group', 'destination_dimension', 'destination', 'destination_label', 'outside_n', 'destination_n', 'destination_pct_outside']
    for group in sorted(groups):
        candidates = groups[group]
        for field in ('outside_n', 'destination_n', 'destination_pct_outside'):
            _require(len({r[field] for r in candidates}) == 1, 'Destination totals vary across role/specification: ' + field)
        included = sorted((r for r in candidates if r['specification'] == 'inclusive'), key=lambda r: tuple(r[k] for k in keys[DESTINATION]))
        _require(bool(included), 'Missing inclusive destination representation')
        source = included[0]
        _require(source['outside_n'] == coverage[(source['degree_group'],)]['outside_n'], 'Outside population base mismatch')
        # State/specification are lineage only, not dimensions of the collapsed destination share.
        row = _base(DESTINATION, source, keys[DESTINATION])
        row = {k: v for k, v in row.items() if k in ('source_table_id', 'source_key') or k in keep or any(k == prefix + f for f in keep for prefix in ('source_',)) or any(k == f + suffix for f in keep for suffix in ('_status', '_reason'))}
        row['contributing_source_keys'] = canonical_json([source_row(DESTINATION, r, keys[DESTINATION])['source_key'] for r in included])
        _point(row, row['destination_pct_outside'], row['destination_n'], row['outside_n'])
        row.update(category=source['destination'], category_label=source['destination_label'])
        rows.append(row)
    results['outside_destinations'] = _result(rows, ['degree_group', 'destination_dimension', 'destination'], deduplicated_repeated_totals=True)

    keys = _keys(ctx, 'outside_roles')
    selected = [r for r in ctx.tables[DESTINATION] if r['destination_dimension'] == 'grouped']
    rows = _role_rows(DESTINATION, selected, keys[DESTINATION], 'pct_within_destination', 'pct_scored_within_destination', 'destination_n', 'destination_scored_n', 'state', 'state_label')
    rows += _role_rows(ALL_OUTSIDE, ctx.tables[ALL_OUTSIDE], keys[ALL_OUTSIDE], 'pct_outside', 'pct_scored_outside', 'outside_n', 'outside_scored_n', 'state', 'state_label', True)
    results['outside_roles'] = _result(rows, ['degree_group', 'destination_dimension', 'destination', 'specification', 'basis', 'state'])

    table = 'DEP4_funding_role_profiles'
    keys = _keys(ctx, 'employment_connection_profiles')
    companion = _index(ctx.tables['DEP4_funding_connection_roles'], keys[table])
    rows = []
    for source in ctx.tables[table]:
        _require(source['specification'] in ('inclusive', 'conservative'), 'Unsupported connection role specification')
        if source['specification'] == 'inclusive':
            other = companion[tuple(source[k] for k in keys[table])]
            _require(source['n'] == other['n'] and source['denominator_n'] == other['denominator_n'], 'Inclusive companion count mismatch')
            _require(abs(Decimal(source['width_pct']) - Decimal(other['width_pct'])) <= Decimal('1e-10'), 'Inclusive companion share mismatch')
        row = _base(table, source, keys[table])
        _point(row, row['width_pct'], row['n'], row['denominator_n'])
        row.update(category=source['state'], category_label=source['state_label'], connection=source['connection_clear'], basis='observed')
        rows.append(row)
    results['employment_connection_profiles'] = _result(rows, ['degree_group', 'connection_clear', 'specification', 'state'], available_basis='observed_only')

    table = 'DEP4_destination_connection_roles'
    keys = _keys(ctx, 'destination_connection')
    rows = []
    for source in ctx.tables[table]:
        _require(source['degree_group'] == 'Research doctorate', 'Unexpected destination-connection degree')
        row = _base(table, source, keys[table])
        paired_base = canonical_json({'connected_observed_n': row['connected_observed_n'], 'no_identified_connection_observed_n': row['no_identified_connection_observed_n']})
        _point(row, row['difference_pp'], None, paired_base, 'percentage_points')
        row.update(estimate_type='saved_connected_minus_no_identified_connection_contrast',
                   connected_percent=row['connected_pct'], no_identified_connection_percent=row['no_identified_connection_pct'],
                   sparse_flag=source['sparse_group_n_under_10'].lower() == 'true',
                   contrast_direction='connected_minus_no_identified_connection')
        _interval(row, row['newcombe_low_pp'], row['newcombe_high_pp'], 'saved_Newcombe_95')
        # The two Wilson intervals remain bound to their respective native proportion fields.
        row['paired_measure_definitions'] = canonical_json({
            'connected_pct': {'numerator': 'connected_likely_n', 'denominator': 'connected_observed_n', 'lower': 'connected_wilson_low_pct', 'upper': 'connected_wilson_high_pct', 'interval_type': 'Wilson_95'},
            'no_identified_connection_pct': {'numerator': 'no_identified_connection_likely_n', 'denominator': 'no_identified_connection_observed_n', 'lower': 'no_identified_connection_wilson_low_pct', 'upper': 'no_identified_connection_wilson_high_pct', 'interval_type': 'Wilson_95'}})
        rows.append(row)
    results['destination_connection'] = _result(rows, ['dimension', 'group', 'specification'], canonical_measure='difference_pp', retained_other_measures=['connected_pct', 'no_identified_connection_pct'])

    keys = _keys(ctx, 'destination_saved_contrasts')
    rows = []
    for table, key in keys.items():
        for source in ctx.tables[table]:
            row = _base(table, source, key)
            if table == 'DEP4_destination_gap_contrast':
                _point(row, row['outside_minus_college_gap_pp'], None, None, 'percentage_points')
                row.update(estimate_type='saved_exploratory_gap_contrast', contrast_direction='outside_minus_college_connection_gap', denominator_reason='contrast_has_no_single_denominator')
                _interval(row, row['normal_approx_95_low_pp'], row['normal_approx_95_high_pp'], 'saved_independent_record_HC3_normal_approx_95')
            elif table == 'DEP4_destination_sector_standardization':
                _point(row, row['standardized_difference_pp'], None, None, 'percentage_points')
                row.update(estimate_type='saved_sector_standardized_contrast', contrast_direction='connected_minus_no_identified_connection', denominator_reason='standardized_contrast_has_no_single_empirical_denominator')
            elif table == 'DEP4_scientific_rd_manufacturing':
                paired_base = canonical_json({'connected_observations': row['connected_observations'], 'no_identified_connection_observations': row['no_identified_connection_observations']})
                _point(row, row['difference_percentage_points'], None, paired_base, 'percentage_points')
                row.update(estimate_type='saved_subset_proportion_contrast', contrast_direction='connected_minus_no_identified_connection')
            else:
                raise ValueError('Unexpected destination contrast source: ' + table)
            rows.append(row)
    results['destination_saved_contrasts'] = _result(rows, ['source_table_id', 'specification'], canonical_measure='source_family_difference', paired_measures_retained=True)

    keys = _keys(ctx, 'employment_sensitivities')
    context_table = OUTSIDE + 'sensitivity_definition_bases.csv'
    contexts = _index(ctx.tables[context_table], ['degree_group', 'definition'])
    rows = []
    for table, key in keys.items():
        for source in ctx.tables[table]:
            row = _base(table, source, key)
            if table == 'DEP4_specification_transition_summary':
                _point(row, row['pct_observed_joint_state_changed'], row['joint_state_changed_n'], row['observed_n'])
                row.update(definition=None, specification=None, state=None, result_family='specification_transition')
            else:
                context = contexts[(source['degree_group'], source['definition'])]
                _require(source['subset_n'] == context['subset_n'] and source['observed_degree_n'] == context['observed_degree_n'], 'Sensitivity coverage mismatch')
                _point(row, row['pct_subset'], row['n'], row['subset_n'])
                row.update(from_specification=None, to_specification=None, definition_label=context['definition_label'], result_family='outside_definition')
                row['definition_context'] = canonical_json({k: int(v) if _is_count(k) and v else v for k, v in context.items()})
            rows.append(row)
    results['employment_sensitivities'] = _result(rows, ['source_table_id', 'degree_group', 'from_specification', 'to_specification', 'definition', 'specification', 'state'], catalog_only=True, canonical_measures={'specification_transition': 'pct_observed_joint_state_changed', 'outside_definition': 'pct_subset'})

    keys = _keys(ctx, 'outside_occupation_breakdowns')
    rows = []
    for table, key in keys.items():
        for source in ctx.tables[table]:
            if source['occupation_row_type'] == 'named':
                _require(bool(source['soc_code']) and int(source['n']) >= 5, 'Named occupation below released threshold')
            else:
                _require(source['occupation_row_type'] in ('pooled_small', 'unavailable') and source['soc_code'] == '', 'Invalid pooled occupation key')
            row = _base(table, source, key)
            _point(row, row['pct_breakdown'], row['n'], row['breakdown_n'])
            row.update(category=canonical_json([source['occupation_row_type'], source['soc_code']]), category_label=source['occupation_title'], reporting_status=source['occupation_row_type'])
            rows.append(row)
    results['outside_occupation_breakdowns'] = _result(rows, ['source_table_id'], catalog_only=True, canonical_measure='pct_breakdown', other_measure='pct_outside')
    return results
