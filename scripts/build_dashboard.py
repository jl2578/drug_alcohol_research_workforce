# SPDX-License-Identifier: MIT
"""Build local static dashboard data from pinned packages. No network or model calls.

python -B scripts/build_dashboard.py          # generate managed data files
python -B scripts/build_dashboard.py --check  # rebuild in a temporary directory and compare
"""
import argparse
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from dashboard_common import (REPO, canonical_json, code_provenance, csv_bytes, csv_cell,
                              finalize, load_context, protected_hashes, require, sha256, source_export_path)
from dashboard_filters import compile_filters, validate_selection

MAX_SHARD_ROWS = 1500
MAX_SHARD_BYTES = 1_000_000


def write(root, rel, raw):
    target = root / rel
    require(target.resolve().is_relative_to(root.resolve()), 'Unsafe output path')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {'path': rel, 'sha256': sha256(raw), 'bytes': len(raw)}


def write_json(root, rel, obj):
    return write(root, rel, (canonical_json(obj) + '\n').encode('utf-8'))


def split_rows(rows, fields):
    batch, size = [], 0
    for row in rows:
        values = [row[f] for f in fields]
        n = len(canonical_json(values).encode('utf-8')) + 1
        if batch and (len(batch) >= MAX_SHARD_ROWS or size + n > MAX_SHARD_BYTES):
            yield batch
            batch, size = [], 0
        batch.append(row); size += n
    if batch:
        yield batch


def encode_shard(batch, fields):
    """Dictionary-encode repeated strings only when it saves bytes; retain exact tokens."""
    matrix = [[r[f] for f in fields] for r in batch]
    dictionaries = {}
    for col, field in enumerate(fields):
        values = [r[field] for r in batch if r[field] is not None]
        if not values or not all(isinstance(v, str) for v in values):
            continue
        domain = sorted(set(values))
        if len(domain) == len(values):
            continue
        codes = {v: i for i, v in enumerate(domain)}
        raw_size = sum(len(canonical_json(v).encode('utf-8')) for v in values)
        encoded_size = len(canonical_json(domain).encode('utf-8')) + sum(len(str(codes[v])) for v in values) + 20
        if encoded_size >= raw_size:
            continue
        dictionaries[str(col)] = domain
        for row in matrix:
            if row[col] is not None:
                row[col] = codes[row[col]]
    return {'dictionaries': dictionaries, 'rows': matrix}


def decode_shard(shard, fields):
    return [{f: (shard['dictionaries'][str(i)][v] if str(i) in shard['dictionaries'] and v is not None else v)
             for i, (f, v) in enumerate(zip(fields, values))} for values in shard['rows']]


def dataset_outputs(stage, dataset, payload, ctx, code):
    contract = ctx.contracts[dataset]
    payload = finalize(dataset, payload, contract)
    rows, fields = payload['rows'], payload['fields']
    filters = compile_filters(dataset, payload, contract)
    require(bool(filters['tuples']), 'Dataset has no eligible filter tuples: ' + dataset)
    validate_selection(filters, {})
    filter_file = write_json(stage, 'metadata/filters/' + dataset + '.json', filters)
    csv_file = write(stage, 'data/' + dataset + '.csv', csv_bytes(rows, fields))
    # CSV and browser JSON derive from these exact canonical records.
    parsed = list(csv.DictReader(io.StringIO((stage / csv_file['path']).read_text(encoding='utf-8'), newline='')))
    require(parsed == [{k: csv_cell(v) for k, v in r.items()} for r in rows], 'CSV round-trip mismatch')
    shards = []
    for number, batch in enumerate(split_rows(rows, fields)):
        shard = write_json(stage, f'data/{dataset}/{number:04}.json', encode_shard(batch, fields))
        shard['row_count'] = len(batch)
        shard['filter_values'] = {f: sorted({r[f] for r in batch}, key=canonical_json) for f in payload['filter_fields']}
        shards.append(shard)
        reread = json.loads((stage / shard['path']).read_text(encoding='utf-8'))
        require(decode_shard(reread, fields) == batch, 'JSON round-trip mismatch')
    json_file = write_json(stage, 'data/' + dataset + '.json', {
        'format': 'columnar-dictionary-shards-v1', 'dataset_id': dataset, 'columns': fields,
        'column_types': {f: sorted({type(r[f]).__name__ for r in rows}) for f in fields},
        'row_count': len(rows), 'shards': shards,
        'null_rule': 'JSON null differs from explicitly valid blank string keys; CSV blanks are interpreted with the contract/status fields.'})
    tables = sorted({s['table_id'] for s in contract['primary_sources'] + contract['support_sources']})
    files = contract.get('source_files', [])
    source_meta = {t: ctx.contract['source_registry'][t] for t in tables}
    file_meta = {f: ctx.contract['file_registry'][f] for f in files}
    metadata = {
        'contract_version': ctx.contract['contract_version'], 'dataset_id': dataset, 'view_ids': contract['view_ids'],
        'row_count': len(rows), 'output_key': contract['output_key'],
        'output_sha256': {csv_file['path']: csv_file['sha256'], json_file['path']: json_file['sha256'], filter_file['path']: filter_file['sha256'], **{s['path']: s['sha256'] for s in shards}},
        'source_table_ids_or_files': tables + files,
        'source_record_key_definition': contract['primary_sources'],
        'source_component_versions': sorted({m['component_version'] for m in [*source_meta.values(), *file_meta.values()]}),
        'source_checksums': {'tables': source_meta, 'files': file_meta},
        'transformation_id': contract['transformation']['id'], **code,
        'population_definition': contract['population'], 'period_definition': contract['period'],
        'units': contract['units'], 'numerator': contract['numerator'], 'denominator': contract['denominator'], 'weighting': contract['weighting'],
        'estimate_type': contract['estimate_type'], 'status_and_interval_definitions': {'statuses': ctx.contract['shared_contract']['availability'], 'dataset_rules': contract['status_rules'], 'interval': contract['interval']},
        'reuse_notices': sorted({m['rights_notice'] for m in [*source_meta.values(), *file_meta.values()]}),
        'source_download_routes': {t: 'dashboard/' + source_export_path(t) for t in tables} | {f: f for f in files},
        'filter_contract': contract['filter_contract'], 'adapter_metadata': payload.get('metadata', {}),
        'contract_path': 'docs/dashboard_data_contract.json', 'source_snapshot': 'ZENODO_SOURCE.json',
        'specification_sha256': sha256(canonical_json(contract).encode('utf-8')),
        'csv': csv_file['path'], 'json': json_file['path'], 'filters': filter_file['path']}
    require(set(ctx.contract['shared_contract']['required_manifest_fields']) <= set(metadata), 'Incomplete output manifest')
    manifest_file = write_json(stage, 'metadata/datasets/' + dataset + '.json', metadata)
    return {'row_count': len(rows), 'csv': csv_file['path'], 'json': json_file['path'],
            'filters': filter_file['path'], 'manifest': manifest_file['path'], 'view_ids': contract['view_ids'],
            'shards': len(shards), 'csv_bytes': csv_file['bytes']}


def reader_archive(ctx):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted((ctx.repo / 'proquest_v5_reproducibility').rglob('*')):
            if path.is_file():
                rel = path.relative_to(ctx.repo).as_posix()
                info = zipfile.ZipInfo(rel, date_time=(2026, 11, 2, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)
    raw = stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            require(archive.read(name) == (ctx.repo / name).read_bytes(), 'Reader ZIP changed a file')
        require(len(archive.namelist()) == 41, 'Reader ZIP membership mismatch')
    return raw


def generate(stage):
    ctx = load_context()
    import dashboard_content, dashboard_funding, dashboard_employment, dashboard_catalog_scorer
    datasets = {}
    for module in (dashboard_content, dashboard_funding, dashboard_employment, dashboard_catalog_scorer):
        result = module.build(ctx)
        require(not datasets.keys() & result.keys(), 'Adapters overlap')
        datasets.update(result)
    require(set(datasets) == set(ctx.contracts), 'Dataset contract coverage mismatch')
    code = code_provenance()
    index = {'format': 'dashboard-index-v1', 'contract_version': ctx.contract['contract_version'],
             'source_snapshot': 'ZENODO_SOURCE.json', 'datasets': {},
             'deferred_views': ctx.contract['deferred_view_ids'],
             'reader_workflow': 'downloads/proquest_v5_reproducibility.zip',
             'load_rule': 'Fetch this small index first, then only the selected dataset filters, manifest and matching shards.'}
    for dataset in sorted(datasets):
        index['datasets'][dataset] = dataset_outputs(stage, dataset, datasets[dataset], ctx, code)
    for key, raw in sorted(ctx.raw_tables.items()):
        write(stage, source_export_path(key), raw)
    write_json(stage, 'metadata/source_exports.json', {
        key: {'path': source_export_path(key), 'sha256': sha256(raw), 'table': key,
              'rights_scope': ctx.entries[key]['rights_scope'], 'rights_notice': 'training_workforce_evidence/DATA_AVAILABILITY.md'}
        for key, raw in sorted(ctx.raw_tables.items())})
    download = write(stage, index['reader_workflow'], reader_archive(ctx))
    write_json(stage, 'metadata/downloads.json', {'reader': {**download, 'component_version': '0.3.0-rc2',
        'files': 41, 'content_rule': 'Files are byte-identical to the pinned component; ZIP container is generated deterministically.',
        'requirements': 'Separately authorized ProQuest inputs; run the downloadable workflow outside the dashboard.',
        'notice': 'proquest_v5_reproducibility/NOTICE.md'}})
    write_json(stage, 'metadata/index.json', index)
    protected = protected_hashes()
    require(protected == json.loads((REPO / 'docs/preserved_components.sha256.json').read_text(encoding='utf-8')), 'Protected package changed during build')
    files = {p.relative_to(stage).as_posix(): sha256(p.read_bytes()) for p in sorted(stage.rglob('*')) if p.is_file()}
    write_json(stage, 'metadata/build.json', {'format': 'dashboard-build-v1', **code,
        'contract_sha256': sha256((REPO / 'docs/dashboard_data_contract.json').read_bytes()),
        'protected_manifest_sha256': sha256((REPO / 'docs/preserved_components.sha256.json').read_bytes()),
        'protected_files_verified': len(protected), 'datasets': len(datasets), 'catalog_entries': 246,
        'row_counts': {k: v['row_count'] for k, v in index['datasets'].items()}, 'files': files})
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare a fresh deterministic build with checked-in outputs; write no outputs')
    args = parser.parse_args()
    dashboard = REPO / 'dashboard'
    with tempfile.TemporaryDirectory(prefix='.dashboard-build-', dir=REPO) as temp:
        stage = Path(temp).resolve()
        require(stage.is_relative_to(REPO) and stage.name.startswith('.dashboard-build-'), 'Unsafe temporary build directory')
        index = generate(stage)
        files = {p.relative_to(stage).as_posix(): p for p in stage.rglob('*') if p.is_file()}
        existing_manifest = dashboard / 'metadata/build.json'
        previous = set(json.loads(existing_manifest.read_text(encoding='utf-8'))['files']) | {'metadata/build.json'} if existing_manifest.exists() else set()
        if args.check:
            changed = [rel for rel, p in files.items() if not (dashboard / rel).is_file() or (dashboard / rel).read_bytes() != p.read_bytes()]
            require(not changed and previous == set(files), 'Outputs differ: ' + repr(changed[:12]) + '; stale=' + repr(sorted(previous - set(files))[:12]))
        else:
            # Only paths in the preceding generated manifest may be replaced/removed.
            for rel in previous - set(files):
                p = (dashboard / rel).resolve()
                require(p.is_relative_to(dashboard.resolve()) and rel.startswith(('data/', 'metadata/', 'sources/', 'downloads/')), 'Unsafe stale output path')
                if p.is_file():
                    p.unlink()
            for rel, source in files.items():
                dest = dashboard / rel
                require(not dest.exists() or rel in previous or dest.read_bytes() == source.read_bytes(), 'Refusing to overwrite an unmanaged file: ' + rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
    print(json.dumps({'status': 'passed', 'mode': 'check' if args.check else 'build', 'datasets': len(index['datasets']),
                      'rows': sum(d['row_count'] for d in index['datasets'].values()), 'generated_files': len(files),
                      'protected_files_verified': 170, 'network_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
