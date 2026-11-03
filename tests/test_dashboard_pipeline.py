# SPDX-License-Identifier: MIT
"""Serialization, release integrity, and unsupported-combination regressions."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dashboard_common import canonical_json, csv_cell, protected_hashes, row_id, sha256
from dashboard_filters import compile_filters, validate_query, validate_selection
from build_dashboard import decode_shard, encode_shard


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.spec = compile_filters('test', {'filter_fields': ['degree','period','category'], 'rows': [
            {'degree':'A','period':'early','category':'yes','support_status':'supported'},
            {'degree':'B','period':'late','category':'no','support_status':'supported'},
            {'degree':'A','period':'late','category':'yes','support_status':'unsupported'}]},
            {'filter_contract': {'forbidden':['person'],'combination_rule':'released tuples','category_selection_rule':'fixed bases'}})

    def test_no_cartesian_or_unsupported_url_selection(self):
        self.assertEqual(validate_query(self.spec, '?dataset=test&degree=A&period=early')['matching_tuple_count'], 1)
        for query in ('?dataset=test&degree=A&period=late','?dataset=test&person=1','?dataset=test&degree=A&degree=B&period=early','?dataset=test&dataset=test','?degree=A'):
            with self.assertRaises(ValueError):
                validate_query(self.spec, query)

    def test_dictionary_roundtrip_distinguishes_zero_empty_null_and_u(self):
        rows = [{'key':str(i),'token':'1.2300e-05','state':'U','blank':'','missing':None,'zero':0,'flag':False} for i in range(50)]
        encoded = encode_shard(rows, list(rows[0]))
        self.assertTrue(encoded['dictionaries'])
        self.assertEqual(decode_shard(encoded, list(rows[0])), rows)

    def test_interface_only_edits_do_not_change_data_provenance(self):
        import dashboard_common
        with tempfile.TemporaryDirectory(prefix='.dashboard-build-test-', dir=REPO) as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to(REPO.resolve()))
            (root/'scripts').mkdir()
            (root/'dashboard/assets').mkdir(parents=True)
            (root/'scripts/build_dashboard.py').write_text('# pipeline\n')
            client = root/'dashboard/assets/data-client.mjs'
            interface = root/'dashboard/assets/dashboard.mjs'
            client.write_text('// shared data client\n')
            interface.write_text('// first presentation\n')
            with patch.object(dashboard_common, 'REPO', root):
                before = dashboard_common.code_provenance()['transformation_code_sha256']
                interface.write_text('// revised presentation\n')
                self.assertEqual(dashboard_common.code_provenance()['transformation_code_sha256'], before)
                client.write_text('// changed selection logic\n')
                self.assertNotEqual(dashboard_common.code_provenance()['transformation_code_sha256'], before)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = REPO / 'dashboard'
        cls.build = json.loads((cls.root/'metadata/build.json').read_text(encoding='utf-8'))
        cls.index = json.loads((cls.root/'metadata/index.json').read_text(encoding='utf-8'))
        cls.contract = json.loads((REPO/'docs/dashboard_data_contract.json').read_text(encoding='utf-8'))

    def test_every_artifact_hash_and_package_byte(self):
        for rel, digest in self.build['files'].items():
            self.assertEqual(sha256((self.root/rel).read_bytes()), digest, rel)
        self.assertEqual(protected_hashes(), json.loads((REPO/'docs/preserved_components.sha256.json').read_text(encoding='utf-8')))

    def test_all_csv_json_records_keys_statuses_and_routes(self):
        for dataset, info in self.index['datasets'].items():
            meta = json.loads((self.root/info['manifest']).read_text(encoding='utf-8'))
            manifest = json.loads((self.root/info['json']).read_text(encoding='utf-8'))
            rows = []
            for shard in manifest['shards']:
                rows.extend(decode_shard(json.loads((self.root/shard['path']).read_text(encoding='utf-8')), manifest['columns']))
            self.assertEqual(len(rows), info['row_count'], dataset)
            self.assertEqual(len({r['row_id'] for r in rows}), len(rows), dataset)
            with (self.root/info['csv']).open(encoding='utf-8', newline='') as stream:
                for r, saved in zip(rows, csv.DictReader(stream), strict=True):
                    self.assertEqual(saved, {k: csv_cell(v) for k,v in r.items()}, dataset)
                    self.assertEqual(r['row_id'], row_id(dataset,r,meta['output_key']))
            for path in meta['source_download_routes'].values():
                self.assertTrue((REPO/path).is_file(), path)
            for path in meta['reuse_notices']:
                self.assertTrue((REPO/path).is_file(), path)

    def test_coverage_small_entrypoint_and_full_source_catalog(self):
        self.assertEqual(set(self.index['datasets']), {d['id'] for d in self.contract['datasets']})
        self.assertEqual(len(self.index['datasets']),26)
        self.assertLess((self.root/'metadata/index.json').stat().st_size, 15000)
        self.assertEqual(set(self.index['deferred_views']), set(self.contract['deferred_view_ids']))
        source = json.loads((self.root/'metadata/source_exports.json').read_text(encoding='utf-8'))
        self.assertEqual(len(source),246)
        for entry in source.values():
            self.assertEqual(sha256((self.root/entry['path']).read_bytes()), entry['sha256'])


if __name__ == '__main__':
    unittest.main()
