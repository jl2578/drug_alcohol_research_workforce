# SPDX-License-Identifier: MIT
"""Shared exact arithmetic, pinned inputs and canonical dashboard rows (stdlib)."""
import csv
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
PROTECTED = ('training_workforce_evidence', 'proquest_v5_reproducibility', 'rc_rmi_scorer')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def decimal_ratio(n, d, multiplier=100):
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        require(Decimal(str(d)) != 0, 'Zero denominator')
        return str(Decimal(str(n)) / Decimal(str(d)) * Decimal(str(multiplier)))


def source_row(table_id, row, key_fields):
    return {'source_table_id': table_id,
            'source_key': canonical_json([row[k] for k in key_fields])}


def read_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    rows = list(reader)
    require(bool(reader.fieldnames) and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Duplicate/missing columns')
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'Malformed CSV')
    return rows


def protected_hashes(repo=REPO):
    return {p.relative_to(repo).as_posix(): sha256(p.read_bytes())
            for folder in PROTECTED for p in sorted((repo / folder).rglob('*')) if p.is_file()}


def load_context():
    expected = json.loads((REPO / 'docs/preserved_components.sha256.json').read_text(encoding='utf-8'))
    require(protected_hashes() == expected, 'Protected component membership or bytes changed')
    contract = json.loads((REPO / 'docs/dashboard_data_contract.json').read_text(encoding='utf-8'))
    for rel, digest in contract['input_documents'].items():
        require(sha256((REPO / rel).read_bytes()) == digest, 'Changed pinned document: ' + rel)
    sys.path.insert(0, str(REPO / 'training_workforce_evidence/code'))
    import verify_all as core
    import table_access
    entries = {r['table']: r for r in core.index()}
    stacks = core.load_stacks(entries.values())
    raw_tables = {key: table_access.content(core, entry, entries, stacks) for key, entry in entries.items()}
    tables = {key: read_csv(raw) for key, raw in raw_tables.items() if not key.endswith('.json')}
    for key, meta in contract['source_registry'].items():
        require(sha256(raw_tables[key]) == meta['restored_table_sha256'], 'Changed source table: ' + key)
        require(sha256((REPO / meta['source_file']).read_bytes()) == meta['source_file_sha256'], 'Changed source container: ' + key)
    for rel, meta in contract['file_registry'].items():
        require(sha256((REPO / rel).read_bytes()) == meta['sha256'], 'Changed source file: ' + rel)
    return SimpleNamespace(repo=REPO, contract=contract,
                           scope=json.loads((REPO / 'docs/dashboard_scope.json').read_text(encoding='utf-8')),
                           tables=tables, raw_tables=raw_tables, entries=entries,
                           contracts={d['id']: d for d in contract['datasets']}, table_access=table_access)


def row_id(dataset, row, keys):
    return dataset + ':' + sha256(canonical_json([[k, row[k]] for k in keys]).encode('utf-8'))


def finalize(dataset, payload, contract):
    """Fail on ambiguous statuses/keys; sort without rounding or modifying source tokens."""
    rows = payload['rows']
    keys = contract['output_key']
    require(bool(rows), 'Empty dataset: ' + dataset)
    seen = set()
    for row in rows:
        require(all(k in row and row[k] is not None for k in keys), 'Missing key: ' + dataset)
        for key in keys:
            require(isinstance(row[key], str), 'Key must remain a source string: ' + dataset + '/' + key)
        rid = row_id(dataset, row, keys)
        require(rid not in seen, 'Duplicate output key: ' + dataset + ':' + repr([row[k] for k in keys]))
        seen.add(rid)
        row['row_id'] = rid
        require(any(k in row for k in ('source_key', 'source_keys', 'source_keys_json', 'contributing_source_keys', 'source_reference', 'benchmark_id')),
                'Missing row lineage: ' + dataset)
        row.setdefault('support_status', 'not_applicable')
        row.setdefault('value_status', 'available' if row.get('value') is not None else 'not_applicable')
        row.setdefault('interval_status', 'not_applicable')
        for name, allowed in [('support_status', ('supported','unsupported','not_applicable','not_evaluated')),
                              ('value_status', ('available','missing','unavailable','suppressed','not_applicable')),
                              ('interval_status', ('available','not_computed','unavailable','not_applicable'))]:
            require(row[name] in allowed, 'Noncanonical ' + name + ': ' + dataset + ' ' + str(row[name]))
        for name, value in row.items():
            require(value is None or isinstance(value, (str, int, bool)), 'Nonflat/inexact value: ' + dataset + '/' + name)
            if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9007199254740991:
                row[name] = str(value)
    fields = ['row_id'] + keys + sorted(set().union(*(set(r) for r in rows)) - {'row_id', *keys})
    rows = [{f: r.get(f) for f in fields} for r in rows]
    rows.sort(key=lambda r: tuple(r[k] for k in keys))
    for field in payload['filter_fields']:
        require(field in fields, 'Missing filter field: ' + dataset + '/' + field)
    return {**payload, 'rows': rows, 'fields': fields}


def csv_cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: csv_cell(v) for k, v in r.items()} for r in rows)
    return stream.getvalue().encode('utf-8')


def source_export_path(key):
    return 'sources/' + sha256(key.encode('utf-8'))[:20] + ('.json' if key.endswith('.json') else '.csv')


def code_provenance():
    files = sorted((REPO / 'scripts').glob('*.py')) + sorted((REPO / 'dashboard/assets').glob('*.mjs'))
    hashes = {p.relative_to(REPO).as_posix(): sha256(p.read_bytes()) for p in files}
    args = ['git', 'log', '-1', '--format=%H', '--', *hashes]
    try:
        commit = subprocess.check_output(args, cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', *hashes], cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit, dirty = None, True
    return {'transformation_code_commit': None if dirty else commit,
            'transformation_code_sha256': sha256(canonical_json(hashes).encode('utf-8')),
            'transformation_files': hashes, 'uncommitted_transformation_code': bool(dirty)}
