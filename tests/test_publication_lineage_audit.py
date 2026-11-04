# SPDX-License-Identifier: MIT
"""Audit every persisted row's source closure and the scorer's full saved domain."""
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/'scripts'))
from dashboard_common import load_context, protected_hashes


def read_rows(root, entry):
    manifest = json.loads((root/entry['json']).read_text(encoding='utf-8'))
    rows = []
    for part in manifest['shards']:
        block = json.loads((root/part['path']).read_text(encoding='utf-8'))
        for values in block['rows']:
            rows.append({field: block['dictionaries'][str(i)][values[i]]
                         if str(i) in block['dictionaries'] and values[i] is not None else values[i]
                         for i,field in enumerate(manifest['columns'])})
    return rows


class LineageAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = load_context()
        cls.root = REPO/'dashboard'
        cls.index = json.loads((cls.root/'metadata/index.json').read_text(encoding='utf-8'))
        cls.data = {key: read_rows(cls.root, entry) for key,entry in cls.index['datasets'].items()}
        cls.keysets = {}
        for contract in cls.ctx.contract['datasets']:
            for source in contract['primary_sources']:
                table, fields = source['table_id'], source['key']
                cls.keysets.setdefault(table, set()).update(tuple(r[f] for f in fields) for r in cls.ctx.tables[table])

    def test_all_130103_rows_have_resolvable_source_records_or_instrument_inputs(self):
        checked = 0
        for dataset,rows in self.data.items():
            for row in rows:
                if dataset == 'rc_rmi_lookup':
                    self.assertEqual(json.loads(row['source_key']),[row['specification'],row['soc_code_canonical'],row['naics_code_canonical']])
                    self.assertTrue((REPO/row['source_reference']).is_file())
                elif dataset == 'table_catalog':
                    self.assertIn(row['table'],self.ctx.entries)
                    self.assertEqual(json.loads(row['source_key']),[row['table']])
                elif dataset == 'institution_benchmark':
                    refs = json.loads(row['member_source_rows'])
                    self.assertEqual(len(refs),50)
                    for ref in refs:
                        self.assertIn(tuple(json.loads(ref['source_key'])),self.keysets[ref['source_table_id']])
                elif dataset == 'content_observed_difference':
                    refs = json.loads(row['source_key'])
                    self.assertEqual(len(refs),2)
                    for ref in refs:
                        self.assertIn(tuple(json.loads(ref)),self.keysets[row['source_table_id']])
                else:
                    self.assertIn(tuple(json.loads(row['source_key'])),self.keysets[row['source_table_id']])
                if row.get('contributing_source_keys'):
                    for ref in json.loads(row['contributing_source_keys']):
                        self.assertIn(tuple(json.loads(ref)),self.keysets[row['source_table_id']])
                checked += 1
        self.assertEqual(checked,130103)

    def test_all_scorer_fields_and_three_frozen_fingerprints(self):
        sys.path.insert(0,str(REPO/'rc_rmi_scorer'))
        import scorer
        scorer.verify_files()
        expected = json.loads((REPO/'rc_rmi_scorer/expected_domain_fingerprints.json').read_text(encoding='utf-8'))
        actual = {(r['specification'],r['pair_id']):r for r in self.data['rc_rmi_lookup']}
        self.assertEqual(len(actual),61812)
        for spec in scorer.SPECS:
            domain = scorer.domain(spec)
            self.assertEqual(scorer.fingerprint(domain),expected['score_fingerprints'][spec])
            self.assertEqual(len(domain),20604)
            for source in domain:
                row = actual[spec,source['pair_id']]
                for field,value in source.items():
                    if field in ('research_likely','clinical_likely'):
                        self.assertEqual(row['source_'+field],value)
                        self.assertEqual(row[field],value=='yes')
                    else:
                        self.assertEqual(row[field],value)
                for field in ('research_axis','clinical_axis'):
                    self.assertIn(row[field],('0','1','2','3','4','U'))

    def test_asset_membership_excludes_mockups_and_synthetic_study_sources(self):
        build = json.loads((self.root/'metadata/build.json').read_text(encoding='utf-8'))
        actual = {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file()}
        ui_assets = {'data-client.mjs', 'dashboard.css', 'dashboard.mjs', 'view-specs.mjs', 'ui-model.mjs', 'story.css', 'story.mjs', 'rarc-logo.svg'}
        pages = {'index.html', 'content.html', 'funding.html', 'careers.html', 'data.html', 'explore.html'}
        allowed = set(build['files']) | {'metadata/build.json', 'README.md', '.gitkeep'} | pages | {'assets/' + name for name in ui_assets}
        self.assertEqual(actual,allowed)
        self.assertEqual({p.name for p in (self.root/'assets').iterdir()},ui_assets)
        for dataset, entry in self.index['datasets'].items():
            meta = json.loads((self.root/entry['manifest']).read_text(encoding='utf-8'))
            self.assertEqual(meta['source_table_ids_or_files'],
                             sorted({s['table_id'] for s in self.ctx.contracts[dataset]['primary_sources']+self.ctx.contracts[dataset]['support_sources']})
                             + self.ctx.contracts[dataset].get('source_files',[]))
            self.assertFalse(any('synthetic' in source.lower() or 'mockup' in source.lower() for source in meta['source_table_ids_or_files']))
        self.assertEqual(protected_hashes(),json.loads((REPO/'docs/preserved_components.sha256.json').read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
