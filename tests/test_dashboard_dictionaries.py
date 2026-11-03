# SPDX-License-Identifier: MIT
"""Every CSV column has a resolvable dictionary without changing source lexemes."""
import csv
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'dashboard'


class DictionaryTests(unittest.TestCase):
    def test_all_26_dictionaries_match_csv_columns_and_nonempty_counts(self):
        index = json.loads((ROOT / 'metadata/index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(index['datasets']), 26)
        for dataset, entry in index['datasets'].items():
            with self.subTest(dataset=dataset):
                meta = json.loads((ROOT / entry['manifest']).read_text(encoding='utf-8'))
                path = ROOT / entry['data_dictionary']
                self.assertEqual(meta['data_dictionary'], entry['data_dictionary'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), meta['data_dictionary_sha256'])
                dictionary = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual((path.parent / dictionary['url']).resolve(), (ROOT / entry['csv']).resolve())
                with (ROOT / entry['csv']).open(encoding='utf-8', newline='') as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames
                    counts = dict.fromkeys(fields, 0)
                    for row in reader:
                        for field in fields:
                            counts[field] += row[field] != ''
                columns = dictionary['tableSchema']['columns']
                self.assertEqual([column['name'] for column in columns], fields)
                for column in columns:
                    self.assertGreater(len(column['dc:description']), 25)
                    self.assertEqual(column['schema:additionalProperty']['schema:value'], counts[column['name']])
                    self.assertEqual(column['datatype'], 'string')
                    self.assertEqual(column['null'], [])
                self.assertEqual(dictionary['tableSchema']['primaryKey'], 'row_id')


if __name__ == '__main__':
    unittest.main()
