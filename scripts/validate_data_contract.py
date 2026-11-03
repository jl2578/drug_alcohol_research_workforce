# SPDX-License-Identifier: MIT
"""Check the dashboard specification against released sources; write no exports.

Run from any directory: python -B scripts/validate_data_contract.py
This validates inputs and declarations; test_dashboard_pipeline.py validates generated outputs.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'training_workforce_evidence/code'))
import verify_all as core
import table_access

def require(condition, message):
    if not condition:
        raise ValueError(message)

def load(relative):
    return json.loads((REPO / relative).read_text(encoding='utf-8-sig'))

def main():
    contract = load('docs/dashboard_data_contract.json')
    mapping = load('docs/dashboard_view_map.json')
    scope = load('docs/dashboard_scope.json')
    require(contract['contract_version'] == '1.0.0', 'Unsupported contract version')
    for path, expected in contract['input_documents'].items():
        require(hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected, 'Changed input document: ' + path)
    entries = {r['table']: r for r in core.index()}
    stacks = core.load_stacks(entries.values())
    cached = {}
    file_hashes = {}
    for key, meta in contract['source_registry'].items():
        require(key in entries, 'Unknown table: ' + key)
        raw = table_access.content(core, entries[key], entries, stacks)
        require(hashlib.sha256(raw).hexdigest() == meta['restored_table_sha256'], 'Changed table: ' + key)
        file = meta['source_file']
        if file not in file_hashes:
            file_hashes[file] = hashlib.sha256((REPO / file).read_bytes()).hexdigest()
        require(file_hashes[file] == meta['source_file_sha256'], 'Changed container: ' + file)
        require(meta['rights_scope'] == entries[key]['rights_scope'], 'Rights notice mismatch: ' + key)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        rows = list(reader)
        require(len(rows) == meta['rows'], 'Row count mismatch: ' + key)
        cached[key] = (reader.fieldnames, rows)
    for path, info in contract['file_registry'].items():
        require(hashlib.sha256((REPO / path).read_bytes()).hexdigest() == info['sha256'], 'Changed source file: ' + path)
        require((REPO / info['rights_notice']).is_file(), 'Missing source notice')

    required = {'id', 'view_ids', 'row_grain', 'output_key', 'primary_sources', 'support_sources', 'population', 'period', 'units', 'numerator', 'denominator', 'weighting', 'estimate_type', 'interval', 'status_rules', 'filter_contract', 'transformation', 'field_bindings', 'validation_rules', 'planned_outputs'}
    ids = set()
    covered = set()
    checks = set()
    blank_key_fields = []
    for d in contract['datasets']:
        require(required <= d.keys(), 'Incomplete contract: ' + d.get('id', 'unknown'))
        require(d['id'] not in ids, 'Duplicate dataset ID')
        ids.add(d['id']); covered.update(d['view_ids'])
        require(d['output_key'] and len(d['output_key']) == len(set(d['output_key'])), 'Invalid output key: ' + d['id'])
        require(d['transformation']['id'] and d['transformation']['steps'], 'Missing transformation: ' + d['id'])
        require(d['planned_outputs']['status'] == 'generated_by_build_dashboard', 'Unexpected output-state declaration')
        for s in d['primary_sources'] + d['support_sources']:
            require(s['table_id'] in cached, 'Missing registered source: ' + s['table_id'])
        for s in d['primary_sources']:
            key = s['table_id']; fields = s['key']; columns, rows = cached[key]
            require(fields and set(fields) <= set(columns), 'Unknown key field: ' + key)
            tuples = [tuple(r[f] for f in fields) for r in rows]
            require(len(tuples) == len(set(tuples)), 'Nonunique full-source key: ' + key)
            checks.add((key, tuple(fields)))
            for f in fields:
                empty_rows = [r for r in rows if r[f] == '']
                if empty_rows:
                    permissions = [p for p in d.get('allowed_blank_key_fields', []) if p['table_id'] == key and p['field'] == f]
                    require(bool(permissions), 'Undeclared empty key: ' + key + ':' + f)
                    for r in empty_rows:
                        require(any(all(r[k] in values for k, values in p['only_when'].items()) for p in permissions), 'Invalid empty-key category: ' + key)
                    blank_key_fields.append({'dataset': d['id'], 'table': key, 'field': f})
            for check in s.get('key_checks', []):
                require(check.get('unique', True), 'Unresolved key validation')
    expected = {v['id'] for v in mapping['views'] if v['first_release_scope'] != 'deferred'}
    require(covered == expected, 'View coverage mismatch: ' + repr(covered ^ expected))
    require(set(contract['deferred_view_ids']) == set(scope['deferred_views']), 'Deferral mismatch')
    require(not covered.intersection(scope['deferred_views']), 'Deferred view acquired a contract')
    roster = scope['institution_benchmark']['cohort']['institution_ids']
    require(len(roster) == len(set(roster)) == 50, 'Fixed cohort changed')
    require(hashlib.sha256(('\n'.join(sorted(roster))+'\n').encode()).hexdigest() == scope['institution_benchmark']['cohort']['roster_sha256'], 'Roster fingerprint mismatch')
    catalog = list(csv.DictReader((REPO / 'training_workforce_evidence/data/TABLE_INDEX.csv').open(encoding='utf-8-sig', newline='')))
    require(len(catalog) == len({r['table'] for r in catalog}) == 246, 'Catalog key/count mismatch')
    print(json.dumps({'status': 'passed', 'datasets': len(ids), 'included_views': len(covered), 'source_tables_hash_checked': len(cached), 'source_files_hash_checked': len(contract['file_registry']), 'distinct_primary_keys_checked': len(checks), 'declared_empty_key_fields_observed': blank_key_fields, 'catalog_entries': len(catalog), 'exports_generated': False}, indent=2))

if __name__ == '__main__':
    main()
