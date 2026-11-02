"""Portable orchestration for the SM1 public reproduction candidate.

This module is copied to src/coding/public_workflow.py in the package.
All evidence and outputs supplied by readers remain in private/.
"""
import csv
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/coding'))
from html import unescape
from extract_v5_rev13_pilot_from_xml import PREFIX, TextOnly, evidence_hash, loose_text, plain_text, sha256

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def verify_package():
    manifest = json.loads((ROOT/'manifest/files.json').read_text(encoding='utf-8'))
    for rel, expected in manifest.items():
        if rel == 'START_HERE.ipynb':
            continue  # Saved execution outputs are not notebook source changes.
        if digest(ROOT/rel) != expected:
            raise ValueError(f'Package file changed: {rel}')
    notebook=json.loads((ROOT/'START_HERE.ipynb').read_text())
    sources=[{'cell_type':c['cell_type'],'source':''.join(c['source'])} for c in notebook['cells']]
    matches = sources == json.loads((ROOT/'manifest/release.json').read_text())['notebook_sources']
    return {'verified_files': len(manifest)-1, 'notebook_matches_distributed_cells': matches,
            'notebook_note': 'unchanged' if matches else 'Notebook cells/settings were edited; review changes before continuing'}

def prepare(reference_csv, folder, workers=1, *, synthetic=False, reference_rows=None):
    """Freeze a new evidence reference; never call this to approve changed old evidence."""
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError('Preserve the existing plan; resume it or choose a new folder')
    rows = reference_rows if reference_rows is not None else read_csv(reference_csv)
    if not rows or workers < 1:
        raise ValueError('A nonempty reference and positive worker count are required')
    ids = [r['GOID'] for r in rows]
    if len(set(ids)) != len(ids) or any(not g.isdigit() for g in ids):
        raise ValueError('IDs must be unique numeric strings')
    allowed = {'present', 'blank', 'placeholder'}
    if any(r.get('abstract_input_status') not in allowed for r in rows):
        raise ValueError('Explicit present/blank/placeholder abstract status is required')
    assessed = [r for r in rows if r['abstract_input_status']=='present']
    if len(assessed)<workers or any(not r['title'].strip() or not r['abstract'].strip() for r in assessed):
        raise ValueError('Each worker needs assessable evidence with title and abstract')
    if any(r['abstract'].strip() for r in rows if r['abstract_input_status']=='blank'):
        raise ValueError('Blank status contains abstract text')
    freeze=json.loads((ROOT/'config/coding/reviewer_single_pass_v15_freeze.json').read_text())
    folder.mkdir(parents=True)
    if reference_rows is not None:
        reference_csv = folder/'reference_PRIVATE.csv'
        write_csv(reference_csv,['GOID','title','abstract','abstract_input_status'],rows)
    write_csv(folder/'roster.csv',['GOID'],[{'GOID':g} for g in ids])
    exceptions=[{k:r[k] for k in ['GOID','abstract_input_status']} for r in rows if r['abstract_input_status']!='present']
    source=folder/'source_partition'
    write_json(source/'unassessable_goids.json',exceptions)
    write_json(source/'partition_options_manifest.json',{'files':{'unassessable_goids.json':{'sha256':digest(source/'unassessable_goids.json')}}})
    plan={'purpose':'public_reproduction_rerun','synthetic':synthetic,
          'stage_models':freeze['stage_models'],'codebook_sha256':freeze['files_sha256']['config/coding/dissertation_codebook_v5_rev15_reproduction.md'],
          'roster_count':len(rows),'assessable_count':len(assessed),'worker_count':workers,
          'reference_csv_sha256':digest(reference_csv),'source_partition_manifest_sha256':digest(source/'partition_options_manifest.json'),'files':{}}
    for worker in range(1,workers+1):
        part=assessed[worker-1::workers]
        assignment=f'{workers}_workbenches_worker_{worker}_goids.json'
        write_json(folder/assignment,[r['GOID'] for r in part])
        hashes=[]
        for r in part:
            t,a=r['title'],r['abstract']
            hashes.append({'GOID':r['GOID'],'reference_exact_sha256':evidence_hash(t,a,loose=False),
                           'reference_loose_sha256':evidence_hash(t,a,loose=True),
                           'reference_title_loose_sha256':sha256(loose_text(t)),
                           'reference_abstract_loose_sha256':sha256(loose_text(a))})
        hashfile=f'hybrid_worker_{worker}_reference_hashes.csv'
        write_csv(folder/hashfile,list(hashes[0]),hashes)
        for name in [assignment,hashfile]:
            plan['files'][name]={'sha256':digest(folder/name),'count':len(part)}
    write_json(folder/'hybrid_production_plan.json',plan)
    return plan


# Abstract statuses follow codebook A5: collapse whitespace, trim, case-fold and
# strip terminal full stops, then compare exactly with the versioned allowlist.
PLACEHOLDER_ABSTRACTS = {'abstract not available', 'no abstract available',
                         'no abstract provided', 'abstract unavailable'}
REQUIRED_COLUMNS = ('GOID', 'Title', 'Date', 'Degree Date', 'Language', 'School Location', 'Source Type')
DOCUMENT_TYPES = {'dissertationstheses', 'dissertationsthesis'}


def abstract_status(text):
    norm = unicodedata.normalize('NFKC', ' '.join((text or '').split())).casefold().rstrip('.').strip()
    return 'blank' if not norm else 'placeholder' if norm in PLACEHOLDER_ABSTRACTS else 'present'


def clean_markup(value):
    """Metadata text cleaned like XML evidence: entities decoded and markup tags removed."""
    parser = TextOnly()
    parser.feed(unescape(value or ''))
    parser.close()
    return ' '.join(parser.parts)


def match_key(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKC', value or '').casefold() if ch.isalnum())


def prepare_from_search(xml_dir, metadata_csv, folder, workers=1, *,
                        search_executed_at=None, interface_filters=None, search_result_count=None):
    """Build a new private rerun entirely from one reviewer's TDM search export.

    Both XML and Extended Metadata CSV must be from that search in the same
    Workbench. No historical roster or externally supplied GOID list is read.
    Searches return different records over time, so result counts and missing
    values are recorded, never enforced: a record without matching evidence or
    without the metadata a rule needs is excluded with a stated reason, and the
    remaining records continue. Preparation stops only if a required column is
    absent from the metadata export or no record remains.
    """
    xml_dir, metadata_csv, folder = Path(xml_dir), Path(metadata_csv), Path(folder)
    if not folder.resolve().is_relative_to((ROOT/'private').resolve()):
        raise ValueError('New reviewer plans must be created under this package\'s private/ folder')
    if folder.exists():
        raise FileExistsError('A frozen rerun already exists; resume it or choose a new private folder')
    if not xml_dir.is_dir() or not metadata_csv.is_file():
        raise FileNotFoundError('Provide this search\'s XML directory and Extended Metadata CSV')
    with metadata_csv.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        absent = [c for c in REQUIRED_COLUMNS if c not in columns]
        if not {'Authors', 'Author'} & columns:
            absent.append('Authors or Author')
        if absent:
            raise ValueError('Extended Metadata CSV lacks required columns: ' + ', '.join(absent))
        metadata = list(reader)

    counts, removed, flags = Counter(), [], []

    def exclude(goid, reason):
        counts['removed_' + reason] += 1
        removed.append({'GOID': goid, 'reason': reason})

    counts['metadata_rows'] = len(metadata)
    by_id, conflicting = {}, set()
    for row in metadata:
        goid = (row.get('GOID') or '').strip()
        if not goid.isdigit():
            counts['metadata_rows_without_valid_goid'] += 1
        elif goid in by_id:
            counts['metadata_repeated_rows'] += 1
            if row != by_id[goid]:
                conflicting.add(goid)
        else:
            by_id[goid] = row
    xml_paths = sorted(xml_dir.rglob('*.xml'))
    counts['xml_files'] = len(xml_paths)
    evidence, repeated_xml, unreadable = {}, set(), []
    for path in xml_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            unreadable.append(path.relative_to(xml_dir).as_posix())
            continue
        goid = (root.findtext('./GOID') or '').strip()
        if not goid.isdigit():
            counts['xml_files_without_valid_goid'] += 1
        elif goid in evidence:
            repeated_xml.add(goid)
        else:
            title = plain_text(root.find('./Obj/TitleAtt/Title'))
            abstract = PREFIX.sub('', plain_text(root.find('./Obj/Abstract')), count=1)
            evidence[goid] = (title, abstract)
    counts['xml_files_unreadable'] = len(unreadable)

    for goid in sorted(set(by_id) - set(evidence), key=int):
        exclude(goid, 'metadata_without_xml')
    for goid in sorted(set(evidence) - set(by_id), key=int):
        exclude(goid, 'xml_without_metadata')
    candidates = []
    for goid in sorted(set(by_id) & set(evidence), key=int):
        counts['matched_records'] += 1
        row, (title, abstract) = by_id[goid], evidence[goid]
        source = match_key(row['Source Type'])
        published = re.match(r'^\s*(\d{4})', row['Date'] or '')
        language = (row['Language'] or '').strip().casefold()
        year = re.match(r'^\s*(\d{4})', row['Degree Date'] or '')
        location = (row['School Location'] or '').strip().casefold()
        # Rules apply in the documented order; a missing value excludes the record
        # only when that rule needs it.
        if goid in conflicting: reason = 'conflicting_metadata_rows'
        elif goid in repeated_xml: reason = 'repeated_xml_record'
        elif not source: reason = 'missing_document_type'
        elif source not in DOCUMENT_TYPES: reason = 'document_type'
        elif not published: reason = 'missing_publication_date'
        elif not 2010 <= int(published.group(1)) <= 2023: reason = 'publication_year'
        elif not language: reason = 'missing_language'
        elif language != 'english': reason = 'language'
        elif not year: reason = 'missing_completion_year'
        elif not 2010 <= int(year.group(1)) <= 2023: reason = 'completion_year'
        elif not location: reason = 'missing_school_location'
        elif ('uk & ireland' in location or 'u.k. & ireland' in location
              or not location.startswith('united states')): reason = 'geography'
        else: reason = None
        status = abstract_status(abstract)
        if not reason and status == 'present' and not title:
            reason = 'missing_xml_title'
        if reason:
            exclude(goid, reason)
            continue
        if match_key(title) != match_key(clean_markup(row['Title'])):
            flags.append({'GOID': goid, 'flag': 'title_differs_between_xml_and_metadata'})
        author = match_key(clean_markup(row.get('Authors') or row.get('Author')))
        work_key = (match_key(title), author, year.group(1)) if match_key(title) and author else None
        if work_key is None:
            flags.append({'GOID': goid, 'flag': 'not_deduplicated_missing_title_or_author'})
        candidates.append((goid, work_key, {'GOID': goid, 'title': title,
                                            'abstract': abstract if status != 'blank' else '',
                                            'abstract_input_status': status}))
    # For repeated work keys, keep the most assessable evidence, then the lowest
    # numeric GOID, so the result does not depend on export row order.
    rank = {'present': 0, 'placeholder': 1, 'blank': 2}
    best = {}
    for goid, work_key, record in candidates:
        order = (rank[record['abstract_input_status']], int(goid))
        if work_key is not None and (work_key not in best or order < best[work_key][0]):
            best[work_key] = (order, goid)
    winners = {goid for _, goid in best.values()}
    selected = []
    for goid, work_key, record in candidates:
        if work_key is None or goid in winners:
            selected.append(record)
            counts['retained_' + record['abstract_input_status']] += 1
        else:
            exclude(goid, 'duplicate_work_key')
    for item in flags:
        counts['flag_' + item['flag']] += 1
    if not any(r['abstract_input_status'] == 'present' for r in selected):
        raise ValueError('No assessable record remains after the documented rules: ' + json.dumps(dict(counts)))
    plan = prepare(None, folder, workers=workers, reference_rows=selected)
    write_csv(folder/'search_removals_PRIVATE.csv', ['GOID', 'reason'], removed)
    write_csv(folder/'search_review_flags_PRIVATE.csv', ['GOID', 'flag'], flags)
    audit = {'source': 'reviewer_new_tdm_search', 'search_executed_at': search_executed_at,
             'interface_filters': interface_filters,
             'displayed_search_result_count': search_result_count,
             'count_policy': 'Recorded for provenance only; never compared with the exports',
             'metadata_sha256': digest(metadata_csv), 'query_sha256': digest(ROOT/'search/topical_query.txt'),
             'rules': 'XML and metadata matched by GOID; Dissertations & Theses; Date Published 2010-2023; '
                      'English; Degree Date 2010-2023; U.S. School Location excluding UK & Ireland; '
                      'a missing value excludes a record only where a rule needs it; codebook A5 abstract statuses; '
                      'normalized title-author-completion-year work key, keeping present abstracts first, then the '
                      'lowest GOID; records without a title or author are kept and not deduplicated',
             'counts': dict(sorted(counts.items())), 'unreadable_xml_files': unreadable,
             'roster_count': len(selected), 'plan_sha256': digest(folder/'hybrid_production_plan.json')}
    write_json(folder/'search_audit_PRIVATE.json', audit)
    return audit

def extract(xml_dir, plan_dir, worker=1):
    plan_dir=Path(plan_dir); p=json.loads((plan_dir/'hybrid_production_plan.json').read_text())
    output=plan_dir/f'worker_{worker}_input_PRIVATE.csv'
    if not output.exists():
        subprocess.run([sys.executable,str(ROOT/'src/coding/extract_v5_rev14_production_from_xml.py'),
            '--xml-dir',str(xml_dir),'--assignment',str(plan_dir/f"{p['worker_count']}_workbenches_worker_{worker}_goids.json"),
            '--reference-hashes',str(plan_dir/f'hybrid_worker_{worker}_reference_hashes.csv'),'--output',str(output)],check=True)
    return output

def command(plan_dir, worker=1):
    plan_dir=Path(plan_dir); p=json.loads((plan_dir/'hybrid_production_plan.json').read_text())
    return [sys.executable,str(ROOT/'src/coding/run_v5_rev14_hybrid_production.py'),
        '--input-csv',str(plan_dir/f'worker_{worker}_input_PRIVATE.csv'),
        '--assignment',str(plan_dir/f"{p['worker_count']}_workbenches_worker_{worker}_goids.json"),
        '--reference-hashes',str(plan_dir/f'hybrid_worker_{worker}_reference_hashes.csv'),
        '--plan-manifest',str(plan_dir/'hybrid_production_plan.json'),
        '--worker-count',str(p['worker_count']),'--worker-id',str(worker),
        '--output-dir',str(plan_dir/f'worker_{worker}_output')]

def run(plan_dir, worker=1, *, mode='preflight', release_content=False, base_url=None, key_file=None,
        pace_tpm=None, retry_failures_once=False, fixture_dir=None):
    cmd=command(plan_dir,worker)
    if mode=='preflight': cmd+=['--preflight-only']
    elif mode=='example':
        if not json.loads((Path(plan_dir)/'hybrid_production_plan.json').read_text())['synthetic']:
            raise ValueError('Saved synthetic responses cannot code real records')
        if fixture_dir is None:
            raise ValueError('Offline tests must create their own temporary response fixtures')
        cmd+=['--fixture-dir',str(fixture_dir)]
    elif mode=='live':
        if not base_url or not key_file or not pace_tpm:
            raise ValueError('Supply endpoint, key file and measured pacing for deliberate live calls')
        if json.loads((Path(plan_dir)/'hybrid_production_plan.json').read_text())['synthetic']:
            raise ValueError('Live calls are disabled for the bundled example')
        cmd+=['--run-live','--base-url',str(base_url),'--key-file',str(key_file),'--pace-tpm',str(pace_tpm)]
    else: raise ValueError('Unknown mode')
    if retry_failures_once:
        if mode != 'live': raise ValueError('The deliberate failure retry requires live mode')
        cmd+=['--retry-failures-once']
    if release_content: cmd+=['--release-content']
    result=subprocess.run(cmd,check=False)
    if result.returncode not in [0,75]: raise RuntimeError(f'Coding stopped with exit {result.returncode}; inspect the message and checkpoint')
    if result.returncode==75: print('Paused; preserve this plan and output and resume after resolving the cause.')
    return result.returncode

def merge(plan_dir, *, synthetic=False):
    from merge_v5_rev14_hybrid_production_exports import merge as merge_exports
    plan_dir=Path(plan_dir); p=json.loads((plan_dir/'hybrid_production_plan.json').read_text())
    if bool(p['synthetic']) != synthetic: raise ValueError('Example/live merger mode mismatch')
    return merge_exports(packages=[plan_dir/f'worker_{i}_output/production_export_package.zip' for i in range(1,p['worker_count']+1)],
        worker_count=p['worker_count'],plan_dir=plan_dir,roster=plan_dir/'roster.csv',
        freeze_path=ROOT/'config/coding/reviewer_single_pass_v15_freeze.json',output_dir=plan_dir/'merged',production=not synthetic)

def account(plan_dir):
    rows=[json.loads(s) for s in (Path(plan_dir)/'merged/v5_rev14_hybrid_merged_codes.jsonl').read_text().splitlines()]
    from collections import Counter
    result={'records':len(rows),'scope_status_counts':dict(Counter(r['record_status'] for r in rows)),
            'content_completed':sum(r['content_codes'] is not None for r in rows),
            'counting_basis':'records; work-level reconciliation is not inferred'}
    write_json(Path(plan_dir)/'population_accounting.json',result)
    return result
