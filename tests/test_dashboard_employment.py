"""Scientific boundary checks for the released employment data adapters."""
import copy
import json
import unittest
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dashboard_common import load_context
import dashboard_employment as employment


class EmploymentAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.output = employment.build(cls.ctx)

    def test_scored_unscored_is_not_zero_or_instrument_u(self):
        rows = self.output['employment_roles']['rows']
        unscored = [r for r in rows if r['basis'] == 'scored' and r['joint_state'] == 'unscored']
        self.assertTrue(unscored)
        self.assertTrue(all(r['value'] is None and r['numerator'] is None and r['value_status'] == 'not_applicable' for r in unscored))
        unknown = [r for r in rows if r['basis'] == 'scored' and r['joint_state'] == 'unclassifiable']
        self.assertTrue(unknown)
        self.assertTrue(all(r['value_status'] == 'available' for r in unknown))

    def test_role_selection_preserves_source_denominators(self):
        for row in self.output['employment_roles']['rows']:
            source_base = 'source_observed_n' if row['basis'] == 'observed' else 'source_scored_n'
            self.assertEqual(row['denominator'], int(row[source_base]))
            if row['value_status'] == 'available':
                source_value = 'source_pct_observed' if row['basis'] == 'observed' else 'source_pct_scored'
                self.assertEqual(row['value'], row[source_value])

    def test_destination_deduplication_and_bases(self):
        rows = self.output['outside_destinations']['rows']
        self.assertEqual(len(rows), len({(r['degree_group'], r['destination']) for r in rows}))
        for row in rows:
            self.assertEqual(row['value'], row['source_destination_pct_outside'])
            self.assertEqual(row['numerator'], int(row['source_destination_n']))
            self.assertEqual(row['denominator'], int(row['source_outside_n']))
            self.assertEqual(len(json.loads(row['contributing_source_keys'])), 6)

    def test_conflicting_repeated_destination_total_fails(self):
        ctx = copy.copy(self.ctx)
        ctx.tables = dict(self.ctx.tables)
        ctx.tables[employment.DESTINATION] = copy.deepcopy(ctx.tables[employment.DESTINATION])
        row = next(r for r in ctx.tables[employment.DESTINATION] if r['destination_dimension'] == 'grouped')
        row['destination_n'] = str(int(row['destination_n']) + 1)
        with self.assertRaisesRegex(ValueError, 'Destination totals vary'):
            employment.build(ctx)

    def test_no_hospital_not_in_connection_role_profiles(self):
        rows = self.output['employment_connection_profiles']['rows']
        self.assertEqual({r['specification'] for r in rows}, {'inclusive', 'conservative'})
        self.assertTrue(all(r['basis'] == 'observed' for r in rows))

    def test_saved_newcombe_limits_not_subtracted_wilson_limits(self):
        rows = self.output['destination_connection']['rows']
        self.assertTrue(all(r['degree_group'] == 'Research doctorate' for r in rows))
        self.assertTrue(all(r['lower'] == r['source_newcombe_low_pp'] and r['upper'] == r['source_newcombe_high_pp'] for r in rows if r['interval_status'] == 'available'))
        self.assertTrue(any(Decimal(r['lower']) != Decimal(r['source_connected_wilson_low_pct']) - Decimal(r['source_no_identified_connection_wilson_high_pct']) for r in rows if r['interval_status'] == 'available'))

    def test_pooled_and_unknown_occupations_remain_distinct(self):
        rows = self.output['outside_occupation_breakdowns']['rows']
        pooled = [r for r in rows if r['occupation_row_type'] == 'pooled_small']
        unknown = [r for r in rows if r['occupation_row_type'] == 'unavailable']
        self.assertTrue(pooled and unknown)
        self.assertTrue(all(r['soc_code'] == '' for r in pooled + unknown))
        self.assertTrue(any(r['n'] == 0 and r['value_status'] == 'available' for r in unknown))
        identities = [(r['source_table_id'], r['source_key']) for r in rows]
        self.assertEqual(len(identities), len(set(identities)))

    def test_reversed_input_keeps_same_rows_and_lineage(self):
        ctx = copy.copy(self.ctx)
        ctx.tables = {k: list(reversed(v)) for k, v in self.ctx.tables.items()}
        reversed_output = employment.build(ctx)
        for key in self.output:
            canonical = lambda rows: sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)
            self.assertEqual(canonical(self.output[key]['rows']), canonical(reversed_output[key]['rows']), key)


if __name__ == '__main__':
    unittest.main()
