# SPDX-License-Identifier: MIT
"""Independent scientific checks on generated publication artifacts, not adapters."""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dashboard_common import load_context
from dashboard_filters import validate_selection
from build_dashboard import decode_shard

OUTSIDE = 'DEP4/rc_rmi/evidence/employment/outside_university_20261016/'
COUNTS = 'DEP3/other_rq3/reach_content/data/NA38_T4_D_observed_counts.csv'
COVERAGE = 'DEP3/other_rq3/reach_content/data/NA39_T4_D_observed_coverage.csv'
DATASETS = (
    'employment_roles', 'employment_occupations', 'outside_destinations',
    'outside_roles', 'employment_connection_profiles', 'destination_connection',
    'destination_saved_contrasts', 'employment_sensitivities', 'outside_occupation_breakdowns',
    'funding_reach', 'funding_content_profiles', 'funding_content_contrasts',
    'institutional_count_associations', 'within_pi_participation',
    'award_frame_disposition', 'award_search_capture',
)


def groups(rows, fields):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row[f] for f in fields)].append(row)
    return result


class PublicationEmploymentFundingAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.rows, cls.filters, cls.metadata, cls.sources = {}, {}, {}, {}
        for dataset in DATASETS:
            manifest = json.loads((REPO / 'dashboard/data' / (dataset + '.json')).read_text(encoding='utf-8'))
            cls.rows[dataset] = [row for shard in manifest['shards'] for row in decode_shard(
                json.loads((REPO / 'dashboard' / shard['path']).read_text(encoding='utf-8')), manifest['columns'])]
            cls.filters[dataset] = json.loads((REPO / 'dashboard/metadata/filters' / (dataset + '.json')).read_text(encoding='utf-8'))
            cls.metadata[dataset] = json.loads((REPO / 'dashboard/metadata/datasets' / (dataset + '.json')).read_text(encoding='utf-8'))
            for source in cls.ctx.contracts[dataset]['primary_sources']:
                cls.sources[source['table_id']] = {
                    tuple(r[k] for k in source['key']): r for r in cls.ctx.tables[source['table_id']]
                }

    def source(self, row):
        return self.sources[row['source_table_id']][tuple(json.loads(row['source_key']))]

    def assert_partition(self, rows, keys):
        for key, members in groups(rows, keys).items():
            with self.subTest(group=key):
                self.assertEqual(len({r['denominator'] for r in members}), 1)
                self.assertEqual(sum(r['numerator'] or 0 for r in members), members[0]['denominator'])

    def test_role_masses_and_exact_saved_shares(self):
        for dataset in ('employment_roles', 'outside_roles'):
            for row in self.rows[dataset]:
                src = self.source(row)
                state = src.get('joint_state', src.get('state'))
                if dataset == 'employment_roles':
                    value_field, base_field = ('pct_observed', 'observed_n') if row['basis'] == 'observed' else ('pct_scored', 'scored_n')
                elif row['source_table_id'].endswith('/outside_role_profiles.csv'):
                    value_field, base_field = ('pct_outside', 'outside_n') if row['basis'] == 'observed' else ('pct_scored_outside', 'outside_scored_n')
                else:
                    value_field, base_field = ('pct_within_destination', 'destination_n') if row['basis'] == 'observed' else ('pct_scored_within_destination', 'destination_scored_n')
                self.assertEqual(row['denominator'], int(src[base_field]))
                if row['basis'] == 'scored' and state == 'unscored':
                    self.assertIsNone(row['value'])
                    self.assertIsNone(row['numerator'])
                    self.assertEqual(row['value_status'], 'not_applicable')
                    self.assertEqual(row['unavailable_reason'], 'unscored_state_excluded_from_scored_basis')
                else:
                    self.assertEqual(row['value'], src[value_field])
                    self.assertEqual(row['numerator'], int(src['n']))
                    self.assertEqual(row['value_status'], 'available')
            partition = ['degree_group', 'specification', 'basis']
            if dataset == 'outside_roles':
                partition += ['source_table_id', 'destination_dimension', 'destination']
            self.assert_partition(self.rows[dataset], partition)

    def test_occupation_pooling_has_no_lost_or_double_counted_records(self):
        rows = self.rows['employment_occupations']
        self.assert_partition(rows, ['degree_group'])
        self.assertEqual({r['occupation_status'] for r in rows}, {'coded', 'aggregate_residual', 'unavailable'})
        for row in rows:
            src = self.source(row)
            self.assertEqual(row['value'], src['percent_within_degree'])
            self.assertEqual(row['numerator'], int(src['n']))
            if row['occupation_status'] == 'coded':
                self.assertTrue(row['soc_unit_code'])
                self.assertGreaterEqual(row['n'], 5)
            else:
                self.assertEqual(row['soc_unit_code'], '')
                self.assertEqual(row['value_status'], 'available')
        for table, members in groups(self.rows['outside_occupation_breakdowns'], ['source_table_id']).items():
            source = next(s for s in self.ctx.contracts['outside_occupation_breakdowns']['primary_sources'] if s['table_id'] == table[0])
            keys = [k for k in source['key'] if k not in ('occupation_row_type', 'soc_code')]
            self.assert_partition(members, keys)
            for row in members:
                src = self.source(row)
                self.assertEqual(row['value'], src['pct_breakdown'] or None)
                self.assertEqual(row['denominator'], int(src['breakdown_n']))
                self.assertEqual(row['pct_outside'], src['pct_outside'])
                if row['occupation_row_type'] == 'named':
                    self.assertTrue(row['soc_code'])
                    self.assertGreaterEqual(row['n'], 5)
                else:
                    self.assertIn(row['occupation_row_type'], ('pooled_small', 'unavailable'))
                    self.assertEqual(row['soc_code'], '')
                    self.assertEqual(row['value_status'], 'available' if src['pct_breakdown'] else 'unavailable')
                if row['denominator'] == 0:
                    self.assertIsNone(row['value'])
                    self.assertEqual(row['numerator'], 0)
                    self.assertEqual(row['pct_outside'], '0.0')

    def test_destination_totals_not_multiplied_by_states_or_specifications(self):
        self.assert_partition(self.rows['outside_destinations'], ['degree_group', 'destination_dimension'])
        bases = {r['degree_group']: r for r in self.ctx.tables[OUTSIDE + 'observation_bases.csv']}
        for row in self.rows['outside_destinations']:
            src = self.source(row)
            self.assertEqual(row['numerator'], int(src['destination_n']))
            self.assertEqual(row['denominator'], int(bases[row['degree_group']]['outside_n']))
            self.assertEqual(row['value'], src['destination_pct_outside'])
            keys = [json.loads(k) for k in json.loads(row['contributing_source_keys'])]
            self.assertEqual(len(keys), 6)
            self.assertEqual({k[1] for k in keys}, {'inclusive'})
            self.assertNotIn('specification', row)

    def test_saved_specification_and_population_filter_boundaries(self):
        for dataset in ('employment_roles', 'outside_roles', 'destination_connection', 'destination_saved_contrasts'):
            spec = self.filters[dataset]
            self.assertEqual(set(spec['domains']['specification']), {'inclusive', 'no_hospital_override', 'conservative'})
            for value in spec['domains']['specification']:
                validate_selection(spec, {'specification': value})
        spec = self.filters['employment_connection_profiles']
        self.assertEqual(set(spec['domains']['specification']), {'inclusive', 'conservative'})
        self.assertTrue(all(r['basis'] == 'observed' for r in self.rows['employment_connection_profiles']))
        for selection in ({'specification': 'no_hospital_override'}, {'basis': 'scored'}, {'training field': 'Psychology'}):
            with self.assertRaises(ValueError):
                validate_selection(spec, selection)
        self.assertEqual({r['degree_group'] for r in self.rows['destination_connection']}, {'Research doctorate'})
        with self.assertRaises(ValueError):
            validate_selection(self.filters['destination_connection'], {'degree_group': "Master's"})

    def test_connection_role_bases_and_saved_sensitivity_measures(self):
        rows = self.rows['employment_connection_profiles']
        self.assert_partition(rows, ['degree_group', 'connection_clear', 'specification'])
        for row in rows:
            src = self.source(row)
            self.assertEqual((row['value'], row['numerator'], row['denominator']), (src['width_pct'], int(src['n']), int(src['denominator_n'])))
        for row in self.rows['employment_sensitivities']:
            src = self.source(row)
            if row['result_family'] == 'specification_transition':
                expected = (src['pct_observed_joint_state_changed'], int(src['joint_state_changed_n']), int(src['observed_n']))
                self.assertIsNone(row['definition'])
                self.assertIsNone(row['specification'])
            else:
                expected = (src['pct_subset'], int(src['n']), int(src['subset_n']))
                self.assertIsNone(row['from_specification'])
                self.assertIsNone(row['to_specification'])
                self.assertEqual(json.loads(row['definition_context'])['subset_n'], row['denominator'])
            self.assertEqual((row['value'], row['numerator'], row['denominator']), expected)
            self.assertEqual(row['interval_status'], 'not_computed')

    def test_destination_saved_aliases_and_paired_bounds(self):
        for row in self.rows['destination_connection']:
            src = self.source(row)
            self.assertEqual(row['value'], src['difference_pp'] or None)
            self.assertEqual(row['lower'], src['newcombe_low_pp'] or None)
            self.assertEqual(row['upper'], src['newcombe_high_pp'] or None)
            self.assertEqual(row['connected_percent'], src['connected_pct'] or None)
            self.assertEqual(row['no_identified_connection_percent'], src['no_identified_connection_pct'] or None)
            self.assertEqual(json.loads(row['denominator']), {k: int(src[k]) for k in ('connected_observed_n', 'no_identified_connection_observed_n')})
            self.assertEqual(row['sparse_flag'], src['sparse_group_n_under_10'].lower() == 'true')
            definitions = json.loads(row['paired_measure_definitions'])
            self.assertEqual(definitions['connected_pct']['lower'], 'connected_wilson_low_pct')
            self.assertEqual(definitions['no_identified_connection_pct']['lower'], 'no_identified_connection_wilson_low_pct')
        for row in self.rows['destination_saved_contrasts']:
            src = self.source(row)
            if row['source_table_id'] == 'DEP4_destination_gap_contrast':
                self.assertEqual(row['value'], src['outside_minus_college_gap_pp'])
                self.assertEqual(row['lower'], src['normal_approx_95_low_pp'])
                self.assertEqual(row['upper'], src['normal_approx_95_high_pp'])
                self.assertEqual(row['n_known_industry'], int(src['n_known_industry']))
            elif row['source_table_id'] == 'DEP4_destination_sector_standardization':
                self.assertEqual(row['value'], src['standardized_difference_pp'])
                self.assertEqual(row['target'], src['target'])
                self.assertIsNone(row['lower'])
            else:
                self.assertEqual(row['value'], src['difference_percentage_points'])
                self.assertEqual(json.loads(row['denominator']), {k: int(src[k]) for k in ('connected_observations', 'no_identified_connection_observations')})
                self.assertIsNone(row['lower'])

    def test_funding_reach_saved_values_and_counts(self):
        for row in self.rows['funding_reach']:
            src = self.source(row)
            self.assertEqual((row['value'], row['probability']), (src['estimate_percent'], src['estimate_probability']))
            self.assertEqual((row['numerator'], row['denominator']), (int(src['numerator']), int(src['denominator'])))
            self.assertLessEqual(abs(Decimal(row['value']) - 100 * Decimal(row['numerator']) / Decimal(row['denominator'])), Decimal('1e-12'))
            self.assertEqual(row['source_base_status'], src['denominator_status'])
            self.assertEqual(row['interval_status'], 'not_computed')

    def test_funding_profile_bases_coverage_and_multiselect(self):
        base_fields = ['connection_definition', 'ownership', 'degree_target', 'outcome']
        coverage = {tuple(r[k] for k in base_fields): r for r in self.ctx.tables[COVERAGE]}
        for row in self.rows['funding_content_profiles']:
            src = self.source(row)
            connection = row['connection_status']
            base = coverage[tuple(row[k] for k in base_fields)]
            self.assertEqual(row['numerator'], int(src[connection + '_category_n']))
            self.assertEqual(row['denominator'], int(base['eligible_' + connection + '_n']))
            self.assertEqual(row['value'], src[connection + '_percent'])
            self.assertEqual(row['population_before_eligibility'], int(base['population_n_before_outcome_eligibility']))
        for members in groups(self.rows['funding_content_profiles'], base_fields + ['connection_status']).values():
            self.assertEqual(len({r['denominator'] for r in members}), 1)
        self.assertTrue(any(sum(Decimal(r['value']) for r in members) > 100
                            for key, members in groups(self.rows['funding_content_profiles'], base_fields + ['connection_status']).items()
                            if key[3] == 'C8'))
        crosswalk = self.metadata['funding_content_profiles']['adapter_metadata']['reach_to_content_connection_definition']
        self.assertEqual(crosswalk, {'combined_clear': 'primary_combined', 'PI_only': 'PI_component', 'combined_clear_or_possible': 'award_possible_sensitivity'})

    def test_funding_contrasts_have_canonical_compound_bases(self):
        for row in self.rows['funding_content_contrasts']:
            src = self.source(row)
            self.assertEqual(row['value'], src['estimate_percent_or_pp'])
            self.assertEqual(row['direction'], src['difference_orientation'])
            for field, alias in (('numerator', 'counts'), ('denominator', 'bases')):
                expected = json.dumps(json.loads(src[field], parse_float=str), ensure_ascii=False, sort_keys=True, separators=(',', ':')) if src[field] else None
                self.assertEqual(row[field], expected)
                self.assertEqual(row[alias], expected)
                self.assertEqual(row['source_' + field], src[field])
            self.assertIsNone(row['lower'])
            self.assertIsNone(row['upper'])
            self.assertEqual(row['interval_status'], 'not_applicable')

    def test_null_compound_numerator_has_its_own_status_and_retained_counts(self):
        missing = [r for r in self.rows['funding_content_contrasts'] if r['numerator'] is None]
        self.assertEqual(len(missing), 264)
        for row in missing:
            src = self.source(row)
            self.assertEqual(row['degree_target'], 'Masters minus research doctorate')
            self.assertEqual(row['value_status'], 'available')
            self.assertEqual(json.loads(row['category_counts_all_groups_json']), json.loads(src['category_counts_all_groups_json']))
            self.assertIn(row.get('numerator_status'), ('not_applicable', 'unavailable'))
            self.assertTrue(row.get('numerator_reason'))

    def test_count_association_aliases_support_and_interval_families(self):
        registry = {r['fit_id']: r for r in self.ctx.tables['DEP3_count_fit_registry']}
        aliases = {'value': 'rate_ratio', 'log_value': 'log_rate_ratio', 'lower_pointwise': 'pointwise95_lower',
                   'upper_pointwise': 'pointwise95_upper', 'lower_familywise': 'familywise95_lower',
                   'upper_familywise': 'familywise95_upper', 'family_adjusted_pvalue': 'bonferroni_family3_pvalue'}
        for row in self.rows['institutional_count_associations']:
            src = self.source(row)
            for target, field in aliases.items():
                self.assertEqual(row[target], src[field])
            self.assertIsNone(row['numerator'])
            self.assertIsNone(row['denominator'])
            self.assertEqual(row['denominator_status'], 'not_applicable')
            fit_ids = json.loads(row['fit_ids'])
            direct = row['degree_target'] == 'Masters minus research doctorate'
            self.assertEqual(len(fit_ids), 2 if direct else 1)
            for fit_id in fit_ids:
                self.assertIn('__common__' if direct else '__main__', fit_id)
                self.assertEqual(row['support_clusters'], int(registry[fit_id]['expected_clusters']))
            for family in ('pointwise', 'familywise'):
                self.assertLessEqual(Decimal(row['lower_' + family]), Decimal(row['value']))
                self.assertLessEqual(Decimal(row['value']), Decimal(row['upper_' + family]))
        filters = self.filters['institutional_count_associations']
        self.assertEqual(set(filters['virtual_filters']['interval_family']['values']), {'pointwise', 'familywise'})

    def test_equal_pi_means_keep_equal_weight_base_and_no_quantile_ci(self):
        aliases = {'funded_mean': 'mean_funded_works_per_year', 'unfunded_mean': 'mean_unfunded_works_per_year', 'paired_difference': 'mean_paired_difference_works_per_year'}
        different_from_pooled = False
        for row in self.rows['within_pi_participation']:
            src = self.source(row)
            self.assertEqual(row['value'], src[aliases[row['measure']]])
            self.assertEqual(row['denominator'], int(src['PIs']))
            self.assertEqual(row['denominator_role'], 'equal_PI_averaging_base')
            self.assertIsNone(row['numerator'])
            self.assertEqual(row['numerator_status'], 'not_applicable')
            self.assertIsNone(row['lower'])
            self.assertIsNone(row['upper'])
            self.assertEqual(row['interval_status'], 'not_computed')
            if row['measure'] == 'funded_mean':
                pooled = Decimal(src['funded_qualifying_PI_work_participations']) / Decimal(src['funded_years'])
                different_from_pooled |= abs(Decimal(row['value']) - pooled) > Decimal('0.0001')
        self.assertTrue(different_from_pooled)

    def test_award_disposition_partitions_and_saved_precision(self):
        rows = self.rows['award_frame_disposition']
        self.assert_partition(rows, ['extension_years', 'match_definition', 'mechanism_group', 'completion_period'])
        for row in rows:
            src = self.source(row)
            self.assertEqual(row['numerator'], int(src['n']))
            self.assertEqual(row['denominator'], int(src['N']))
            self.assertEqual(row['value'], src['percent'])
            self.assertLessEqual(abs(Decimal(row['value']) - 100 * Decimal(row['numerator']) / Decimal(row['denominator'])), Decimal('0.0001'))
            self.assertIsNone(row['lower'])

    def test_award_measures_keep_five_distinct_bases_and_only_capture_ci(self):
        fields = {'search_capture': ('candidate_frame_work_n', 'linked_work_N', 'search_capture_percent'),
                  'included_of_linked': ('included_work_n', 'linked_work_N', 'included_of_linked_percent'),
                  'included_of_retrieved': ('included_work_n', 'candidate_frame_work_n', 'included_of_retrieved_percent'),
                  'included_of_assessable_retrieved': ('included_work_n', 'assessable_candidate_work_n', 'included_of_assessable_retrieved_percent'),
                  'nonretrieval_share_of_noninclusion': ('not_retrieved_work_n', None, 'nonretrieval_share_of_noninclusion_percent')}
        self.assertEqual({r['measure'] for r in self.rows['award_search_capture']}, set(fields))
        for row in self.rows['award_search_capture']:
            src = self.source(row)
            numerator, denominator, value = fields[row['measure']]
            base = int(src[denominator]) if denominator else int(src['linked_work_N']) - int(src['included_work_n'])
            self.assertEqual(row['numerator'], int(src[numerator]))
            self.assertEqual(row['denominator'], base)
            if base:
                self.assertEqual(row['value'], src[value] or None)
            else:
                self.assertIsNone(row['value'])
                self.assertEqual(row['unavailable_reason'], 'zero_denominator')
            if row['measure'] == 'search_capture' and base:
                self.assertEqual(row['lower'], src['search_capture_wilson95_lower'] or None)
                self.assertEqual(row['upper'], src['search_capture_wilson95_upper'] or None)
            else:
                self.assertIsNone(row['lower'])
                self.assertIsNone(row['upper'])

    def test_unavailable_points_and_intervals_never_become_zero(self):
        state_counts = defaultdict(int)
        for dataset, rows in self.rows.items():
            for row in rows:
                state_counts[(dataset, row['value_status'])] += 1
                if row['value'] is None:
                    self.assertIn(row['value_status'], ('unavailable', 'not_applicable', 'missing', 'suppressed'))
                    self.assertTrue(row['unavailable_reason'])
                else:
                    self.assertEqual(row['value_status'], 'available')
                if row['lower'] is None or row['upper'] is None:
                    self.assertNotEqual(row['interval_status'], 'available')
                    self.assertTrue(row['interval_unavailable_reason'])
        self.assertGreater(state_counts[('employment_roles', 'not_applicable')], 0)
        self.assertGreater(state_counts[('outside_roles', 'not_applicable')], 0)


if __name__ == '__main__':
    unittest.main()
