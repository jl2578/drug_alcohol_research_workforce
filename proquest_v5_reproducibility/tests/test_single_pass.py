"""Offline known-answer and invocation checks for the integrated scope workflow.

Run from an extracted package: python tests/test_single_pass.py.
All evidence, identities and responses below are invented at runtime.
"""
from pathlib import Path
from collections import Counter
from unittest import mock
import ast
import contextlib
import copy
import csv
import hashlib
import inspect
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/coding'))
import public_workflow as workflow
import reviewer_scope_single_pass as scope_rules
import run_v5_rev14_hybrid_production as runner
from normalize_v5_rev13 import normalize_content
from validate_v5_rev14_pilot import (
    CONTENT_FIELDS, SCOPE_FIELDS, check_content, check_content_hard_rules,
    check_scope, derive_unit, load_schema, schema_errors,
)


def coded(value, confidence='high'):
    return {'value': value, 'coding_status': 'coded', 'confidence': confidence}


def state(status='cannot_determine'):
    return {'value': None, 'coding_status': status, 'confidence': None}


def aim(roles, labels=None, purposes=None, aid='a1', sid='s2'):
    substantive = bool(set(roles or []) & {
        'object_of_study', 'use_as_outcome', 'use_as_exposure', 'treatment_target',
        'therapeutic_agent', 'substance_related_systems_responses',
    })
    applicable = substantive or 'endogenous_system_only' in (roles or [])
    return {
        'aim_id': aid, 'source_sentence_ids': [sid],
        'substance_roles': coded(roles) if roles is not None else state(),
        'stated_purposes': coded(purposes) if purposes else state(
            'cannot_determine' if substantive else 'not_applicable'),
        'unrelated_therapeutic_indication_tested': coded('yes') if substantive else state('not_applicable'),
        'substance_all': coded(labels) if labels else state(
            'cannot_determine' if applicable else 'not_applicable'),
        'substance_primary': coded(labels[0]) if labels else state(
            'cannot_determine' if applicable else 'not_applicable'),
        'substance_assignment_basis': coded('target_system_mapping') if labels else state(
            'cannot_determine' if applicable else 'not_applicable'),
    }


def scope(record_id, units):
    return {'record_id': record_id, 'scope_units': units, 'add_su_focus': coded(3)}


def content(record_id, targets, mixed='only_qualifying_described', sparse=False):
    result = {
        'record_id': record_id, 'target_aim_ids': targets,
        'mixed_purpose': coded(mixed), 'dissertation_type': coded('empirical_research'),
        'study_design': coded('experimental_nonrandomized'),
        'level_of_analysis': coded('molecular_cellular'),
        'research_objective': coded('other_stated_objective'),
        'intervention_continuum': state('not_applicable'),
        'explanatory_domain': state('not_applicable'),
        'data_type': coded(['biological_physiological']),
        'data_source_origin': coded('primary_generated'),
    }
    if sparse:
        for name in CONTENT_FIELDS[1:]:
            result[name] = state()
    return result


cases = [
    (aim(['endogenous_system_only']), 'in_scope'),
    (aim(['endogenous_system_only'], ['opioids']), 'in_scope'),
    (aim(['endogenous_system_only', 'context_only']), 'in_scope'),
    (aim(['endogenous_system_only', 'therapeutic_agent'], ['caffeine'], ['outside_study_scope']), 'in_scope'),
    (aim(['endogenous_system_only'], ['behavioral_addiction']), 'in_scope'),
    (aim(['use_as_outcome'], ['alcohol'], ['use_or_misuse']), 'in_scope'),
    (aim(['object_of_study'], ['caffeine'], ['mechanism_of_action']), 'out_of_scope'),
    (aim(['none']), 'out_of_scope'),
    (aim(['context_only']), 'out_of_scope'),
    (aim(['instrument_only']), 'out_of_scope'),
    (aim(['behavioral_addiction']), 'out_of_scope'),
    (aim(['therapeutic_agent'], ['opioids'], ['outside_study_scope']), 'out_of_scope'),
    (aim(None), 'undetermined'),
    (aim(['use_as_outcome']), 'undetermined'),
]
for unit, expected in cases:
    normalized, _, _ = scope_rules.normalize_scope(scope('200', [unit]), 'scope_full')
    errors, status, targets = check_scope(normalized, arm='scope_full', record_id='200', sentence_ids={'s2'})
    assert not errors, errors
    assert derive_unit(normalized['scope_units'][0], 'scope_full') == expected
    assert scope_rules.derive_unit(normalized['scope_units'][0], 'scope_full') == expected
    assert status == expected
    assert targets == (['a1'] if expected == 'in_scope' else [])

# Unknown labels govern their dependent scope cells in this pass, including a
# legacy inapplicable placeholder; normalization cannot invent a substance.
for label_status in ['cannot_determine', 'not_applicable']:
    raw_scope = scope('204', [aim(['endogenous_system_only'])])
    raw_scope['scope_units'][0].update({
        'substance_all': state(label_status),
        'substance_primary': coded('opioids'),
        'substance_assignment_basis': coded('target_system_mapping'),
    })
    raw_before = copy.deepcopy(raw_scope)
    normalized, fills, _ = scope_rules.normalize_scope(raw_scope, 'scope_full')
    assert raw_scope == raw_before and fills
    unit = normalized['scope_units'][0]
    assert all(unit[name] == state() for name in (
        'substance_all', 'substance_primary', 'substance_assignment_basis'))
    assert all(unit[name] == state('not_applicable') for name in (
        'stated_purposes', 'unrelated_therapeutic_indication_tested'))
    assert check_scope(normalized, arm='scope_full', record_id='204', sentence_ids={'s2'}) == ([], 'in_scope', ['a1'])
for label, expected_basis in [('opioids', 'target_system_mapping'),
                              ('general_drug_unspecified', 'general_substance_construct')]:
    raw_scope = scope('205', [aim(['endogenous_system_only'], [label])])
    raw_scope['scope_units'][0]['substance_all'] = coded([label], confidence='medium')
    raw_scope['scope_units'][0]['substance_primary'] = state()
    normalized, _, _ = scope_rules.normalize_scope(raw_scope, 'scope_full')
    assert normalized['scope_units'][0]['substance_primary'] == coded(label, confidence='medium')
    assert normalized['scope_units'][0]['substance_assignment_basis']['value'] == expected_basis

# A noncoded role cannot activate admission, and invalid structure must never
# bypass validation merely because an endogenous string appears in a field.
unknown_role = scope('201', [aim(None)])
unknown_role['scope_units'][0]['substance_roles'] = {
    'value': ['endogenous_system_only'], 'coding_status': 'cannot_determine', 'confidence': None,
}
assert check_scope(unknown_role, arm='scope_full', record_id='201', sentence_ids={'s2'})[0]
# Null is a schema sentinel, not a valid coded parent. These malformed response
# shapes must survive normalization as invalid fields rather than crash or
# become a scientific in-scope/uncertain assessment.
for field_name in ['substance_roles', 'substance_all']:
    coded_null = scope('206', [aim(['endogenous_system_only'])])
    coded_null['scope_units'][0][field_name] = coded(None)
    assert not schema_errors(coded_null, load_schema('scope_full'))
    normalized, _, _ = scope_rules.normalize_scope(coded_null, 'scope_full')
    assert normalized['scope_units'][0][field_name] == coded(None)
    errors, status, targets = check_scope(normalized, arm='scope_full', record_id='206', sentence_ids={'s2'})
    assert errors and status == 'invalid' and targets == []
valid_scope, _, _ = scope_rules.normalize_scope(scope('202', [aim(['endogenous_system_only'])]), 'scope_full')
# Applicability is a semantic validation requirement even where the permissive
# wire sentinel schema accepts the raw field's shape.
inapplicable_role = scope('207', [aim(['none'])])
inapplicable_role['scope_units'][0]['substance_roles'] = state('not_applicable')
errors, status, targets = check_scope(inapplicable_role, arm='scope_full', record_id='207', sentence_ids={'s2'})
assert errors and status == 'invalid' and targets == []
assert any('substance_roles' in error for error in errors)
for child in ['substance_primary', 'substance_assignment_basis']:
    known_labels = scope('208', [aim(['endogenous_system_only'], ['opioids', 'alcohol'])])
    known_labels['scope_units'][0][child] = state('not_applicable')
    errors, status, targets = check_scope(known_labels, arm='scope_full', record_id='208', sentence_ids={'s2'})
    assert errors and status == 'invalid' and targets == []
    assert any(child in error for error in errors)
behavioral_basis = scope('209', [aim(['endogenous_system_only'], ['behavioral_addiction'])])
behavioral_basis['scope_units'][0]['substance_assignment_basis'] = state('not_applicable')
assert check_scope(behavioral_basis, arm='scope_full', record_id='209', sentence_ids={'s2'}) == ([], 'in_scope', ['a1'])
for malformed in [
    dict(valid_scope, scope_units=[]),
    dict(valid_scope, scope_units=[valid_scope['scope_units'][0], copy.deepcopy(valid_scope['scope_units'][0])]),
    dict(valid_scope, record_id='999'),
]:
    assert check_scope(malformed, arm='scope_full', record_id='202', sentence_ids={'s2'})[0]
for refs in [['s2', 's2'], ['s99']]:
    malformed = copy.deepcopy(valid_scope)
    malformed['scope_units'][0]['source_sentence_ids'] = refs
    assert check_scope(malformed, arm='scope_full', record_id='202', sentence_ids={'s2'})[0]
missing_field = copy.deepcopy(valid_scope)
del missing_field['scope_units'][0]['substance_all']
assert schema_errors(missing_field, load_schema('scope_full'))
for field_name in ['substance_all', 'substance_primary', 'substance_assignment_basis']:
    missing_field = copy.deepcopy(valid_scope)
    del missing_field['scope_units'][0][field_name]
    errors, status, targets = check_scope(missing_field, arm='scope_full', record_id='202', sentence_ids={'s2'})
    assert errors and status == 'invalid' and targets == []
try:
    scope_rules.target_aim_ids([valid_scope['scope_units'][0], valid_scope['scope_units'][0]])
except ValueError:
    pass
else:
    raise AssertionError('Duplicate aim IDs accepted by the target helper')

# Both admission routes occur in the same response; target ordering follows the
# units, including a retained uncertain unit that must not become a target.
mixed_scope = scope('203', [
    aim(['use_as_outcome'], ['alcohol'], ['use_or_misuse']),
    aim(None, aid='a2', sid='s3'),
    aim(['endogenous_system_only'], aid='a3', sid='s4'),
])
mixed_scope, _, _ = scope_rules.normalize_scope(mixed_scope, 'scope_full')
errors, status, targets = check_scope(mixed_scope, arm='scope_full', record_id='203', sentence_ids={'s2', 's3', 's4'})
assert not errors and status == 'in_scope' and targets == ['a1', 'a3']
assert scope_rules.target_aim_ids(mixed_scope['scope_units']) == ['a1', 'a3']
assert list(inspect.signature(scope_rules.target_aim_ids).parameters) == ['units']
try:
    scope_rules.target_aim_ids(mixed_scope['scope_units'], ['a2'])
except TypeError:
    pass
else:
    raise AssertionError('Scope API accepted an external target list')
scope_source = ast.parse(inspect.getsource(scope_rules))
scope_imports = {
    node.module if isinstance(node, ast.ImportFrom) else alias.name
    for node in ast.walk(scope_source) if isinstance(node, (ast.Import, ast.ImportFrom))
    for alias in node.names
}
assert scope_imports <= {'__future__', 'copy', 'hashlib', 'json', 'normalize_v5_rev13'}, 'Unexpected scope processor dependency'

# Content has no output channel for any scope field or later S4 enrichment.
assert set(load_schema('content')['properties']) == {'record_id', 'target_aim_ids', *CONTENT_FIELDS}
valid_content = content('202', ['a1'])
assert not check_content(valid_content, record_id='202', target_aim_ids=['a1'])
for changed in [
    dict(valid_content, substance_by_aim=[]),
    dict(valid_content, substance_all=coded(['opioids'])),
    dict(valid_content, scope_units=[]),
    dict(valid_content, add_su_focus=coded(1)),
    dict(valid_content, target_aim_ids=['a1', 'a2']),
    dict(valid_content, target_aim_ids=['a1', 'a1']),
    dict(valid_content, record_id='999'),
]:
    assert check_content(changed, record_id='202', target_aim_ids=['a1'])
before_scope = copy.deepcopy(valid_scope)
normalized_content, _, _ = normalize_content(valid_content, valid_scope['scope_units'], derive_unit)
assert valid_scope == before_scope
assert not check_content_hard_rules(normalized_content, scope_units=valid_scope['scope_units'])
changed_s5 = copy.deepcopy(valid_scope)
changed_s5['add_su_focus'] = coded(1)
assert runner.scope_units_sha({'codes': changed_s5}) == runner.scope_units_sha({'codes': valid_scope})
assert scope_rules.scope_codes_sha(changed_s5) != scope_rules.scope_codes_sha(valid_scope)

artifacts = ROOT / 'config/coding/reviewer_single_pass_v15'
scope_prompt = (artifacts / 'scope_prompt.md').read_text(encoding='utf-8')
content_prompt = (artifacts / 'content_prompt.md').read_text(encoding='utf-8')
assert 'endogenous_system_only' in scope_prompt and 'substance_assignment_basis' in scope_prompt
assert 'C1–C9 only' in content_prompt and 'Do not return substance fields' in content_prompt
assert 'adopted_targets' not in scope_prompt
assert runner.RUNNER_VERSION == 'v5_rev15_single_scope_public_rerun_v1'
assert [stage[0] for stage in runner.STAGES] == ['scope_full', 'content']

(ROOT / 'private').mkdir(exist_ok=True)
TEST = Path(tempfile.mkdtemp(prefix='single_pass_', dir=ROOT / 'private')).resolve()
assert TEST.is_relative_to((ROOT / 'private').resolve())
fixtures = TEST / 'responses'
fixtures.mkdir()
xml = TEST / 'xml'
xml.mkdir()
units = {
    '101': [aim(['endogenous_system_only'])],
    '102': [aim(['endogenous_system_only', 'context_only'])],
    '103': [aim(['object_of_study'], ['caffeine'], ['outside_study_scope'])],
    '104': [aim(['use_as_outcome'], ['alcohol'], ['use_or_misuse'])],
    '105': [aim(['none'])],
    '106': [aim(None)],
    '107': [aim(['endogenous_system_only']), aim(['none'], aid='a2', sid='s3')],
    '108': [aim(['endogenous_system_only'], ['opioids'])],
    '109': [aim(['use_as_outcome'], ['alcohol'], ['use_or_misuse']),
            aim(['endogenous_system_only'], aid='a2', sid='s3')],
}
abstracts = {g: 'We studied receptor signaling in cultured cells. We also measured a separately described outcome.' for g in units}
abstracts.update({'103': 'We studied caffeine consumption.',
                  '104': 'We measured adult alcohol use in a survey.',
                  '105': 'We studied leaf growth.',
                  '106': 'An unspecified subject was studied.',
                  '110': '', '111': 'Abstract unavailable.'})
metadata = TEST / 'metadata.csv'
with metadata.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.writer(handle)
    writer.writerow(['GOID', 'Title', 'Authors', 'Date', 'Degree Date', 'Language', 'School Location', 'Source Type'])
    for goid, abstract in abstracts.items():
        title = 'Invented single-pass case ' + goid
        writer.writerow([goid, title, 'Example ' + goid, '2018-01-01', '2018', 'English', 'United States -- Ohio', 'Dissertations & Theses'])
        node = ET.Element('Record')
        ET.SubElement(node, 'GOID').text = goid
        obj = ET.SubElement(node, 'Obj')
        title_att = ET.SubElement(obj, 'TitleAtt')
        ET.SubElement(title_att, 'Title').text = title
        ET.SubElement(obj, 'Abstract').text = abstract
        (xml / (goid + '.xml')).write_bytes(ET.tostring(node, encoding='utf-8', xml_declaration=True))
        if goid in units:
            (fixtures / ('scope_full_' + goid + '.json')).write_text(json.dumps(scope(goid, units[goid])), encoding='utf-8')
responses = {
    '101': content('101', ['a1']), '102': content('102', ['a1']),
    '104': content('104', ['a1']),
    '107': content('107', ['a1'], mixed='mixed_prominence_unclear'),
    '108': content('108', ['a1'], sparse=True),
    '109': content('109', ['a1', 'a2']),
}
for goid, payload in responses.items():
    (fixtures / ('content_' + goid + '.json')).write_text(json.dumps(payload), encoding='utf-8')
expected = {'records': 11, 'scope_status_counts': {'in_scope': 6, 'out_of_scope': 2, 'undetermined': 1, 'not_assessable': 2},
            'content_completed': 6, 'counting_basis': 'records; work-level reconciliation is not inferred'}


def invented_search(plan, workers=1):
    workflow.prepare_from_search(xml, metadata, plan, workers=workers,
        search_executed_at='2026-10-29', interface_filters='invented offline inputs')
    path = plan / 'hybrid_production_plan.json'
    identity = json.loads(path.read_text(encoding='utf-8'))
    assert identity['synthetic'] is False
    identity['synthetic'] = True
    path.write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')


calls = Counter()
original_fixture = runner.invoke_fixture


def fixture_spy(directory, stage, goid, attempt):
    assert stage in {'scope_full', 'content'}, 'Unexpected extra coding stage'
    calls[stage, goid] += 1
    return original_fixture(directory, stage, goid, attempt)


def run_spied(plan, worker=1, release_content=False, response_dir=fixtures):
    args = workflow.command(plan, worker)[1:] + ['--fixture-dir', str(response_dir)]
    if release_content:
        args.append('--release-content')
    with mock.patch.object(sys, 'argv', args), mock.patch.object(runner, 'invoke_fixture', fixture_spy):
        with contextlib.redirect_stdout(io.StringIO()):
            return runner.main()


def checkpoints(plan, worker):
    path = plan / f'worker_{worker}_output/production_checkpoints.jsonl'
    return path, [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


for workers in [1, 2]:
    calls.clear()
    plan = TEST / ('reader_' + str(workers))
    invented_search(plan, workers)
    frozen_scope = {}
    for worker in range(1, workers + 1):
        workflow.extract(xml, plan, worker)
        workflow.run(plan, worker, mode='preflight')
        assert run_spied(plan, worker) == 0
        _, events = checkpoints(plan, worker)
        for event in events:
            if event['event'] == 'validated':
                assert event['stage'] == 'scope_full'
                frozen_scope[event['GOID']] = copy.deepcopy(event)
        before_calls = calls.copy()
        assert run_spied(plan, worker, release_content=True) == 0
        assert {key: count for key, count in calls.items() if key[0] == 'scope_full'} == {
            key: count for key, count in before_calls.items() if key[0] == 'scope_full'}
    assert calls == Counter({**{('scope_full', goid): 1 for goid in units}, **{('content', goid): 1 for goid in responses}})
    workflow.merge(plan, synthetic=True)
    assert workflow.account(plan) == expected
    merged = {row['GOID']: row for row in map(json.loads, (plan / 'merged/v5_rev14_hybrid_merged_codes.jsonl').read_text(encoding='utf-8').splitlines())}
    for goid, event in frozen_scope.items():
        row = merged[goid]
        assert row['scope_codes'] == event['codes']
        assert row['record_status'] == event['record_status'] and row['target_aim_ids'] == event['target_aim_ids']
        assert 'current_scope_codes' not in row and 'substance_coding_source_by_aim' not in row
        if row['content_codes']:
            assert set(row['content_codes']) == {'record_id', 'target_aim_ids', *CONTENT_FIELDS}
            frozen_hash = hashlib.sha256(json.dumps(event['codes']['scope_units'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            assert row['content_frozen_scope_units_sha256'] == frozen_hash
            complete_hash = hashlib.sha256(json.dumps(event['codes'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            assert row['content_frozen_scope_sha256'] == complete_hash
    assert merged['101']['scope_codes']['scope_units'][0]['substance_all'] == state()
    assert merged['102']['record_status'] == 'in_scope'
    assert merged['108']['scope_codes']['scope_units'][0]['substance_all'] == coded(['opioids'])
    assert merged['109']['target_aim_ids'] == ['a1', 'a2']
    assert all(merged[goid]['scope_codes'] is None and merged[goid]['content_codes'] is None for goid in ['110', '111'])
    for worker in range(1, workers + 1):
        checkpoint, events = checkpoints(plan, worker)
        before = checkpoint.read_bytes()
        before_calls = calls.copy()
        assert run_spied(plan, worker, release_content=True) == 0
        assert checkpoint.read_bytes() == before and calls == before_calls
        assert all(event['stage'] in {'scope_full', 'content'} for event in events)
        for event in events:
            if event['event'] == 'validated' and event['stage'] == 'content':
                assert event['frozen_scope_sha256'] == scope_rules.scope_codes_sha(frozen_scope[event['GOID']]['codes'])

# S5 belongs to the frozen scope contract, even though changing it leaves all
# unit-level hashes and inclusion/target derivations unchanged. Exercise both
# resume and merger checks independently of the ZIP envelope's own checksum.
good_plan = TEST / 'reader_1'
good_checkpoint, checkpoint_events = checkpoints(good_plan, 1)
identity = checkpoint_events[0]['run_identity']
runner.load_checkpoint(good_checkpoint, identity, set(units))
tampered_events = copy.deepcopy(checkpoint_events)
for event in tampered_events:
    if event['stage'] == 'scope_full' and event['GOID'] == '101' and event['event'] == 'validated':
        event['codes']['add_su_focus'] = coded(1)
tampered_checkpoint = TEST / 's5_changed_checkpoint.jsonl'
tampered_checkpoint.write_text(''.join(json.dumps(event) + '\n' for event in tampered_events), encoding='utf-8')
try:
    runner.load_checkpoint(tampered_checkpoint, identity, set(units))
except ValueError as exc:
    assert 'Content complete scope differs from scope' in str(exc)
else:
    raise AssertionError('Resume accepted S5 changed after content coding')

source_package = good_plan / 'worker_1_output/production_export_package.zip'
with zipfile.ZipFile(source_package) as archive:
    package_members = {name: archive.read(name) for name in archive.namelist()}
export_rows = [json.loads(line) for line in package_members['production_codes.jsonl'].decode('utf-8').splitlines()]
for row in export_rows:
    if row['GOID'] == '101':
        row['scope_codes']['add_su_focus'] = coded(1)
changed_codes = ('\n'.join(json.dumps(row, separators=(',', ':')) for row in export_rows) + '\n').encode('utf-8')
export_manifest = json.loads(package_members['production_export_manifest.json'])
export_manifest['codes_sha256'] = hashlib.sha256(changed_codes).hexdigest()
package_members['production_codes.jsonl'] = changed_codes
package_members['production_export_manifest.json'] = json.dumps(export_manifest).encode('utf-8')
tampered_package = TEST / 's5_changed_export.zip'
with zipfile.ZipFile(tampered_package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name, body in package_members.items():
        archive.writestr(name, body)
from merge_v5_rev14_hybrid_production_exports import merge as merge_export
try:
    merge_export(packages=[tampered_package], worker_count=1, plan_dir=good_plan,
        roster=good_plan / 'roster.csv', freeze_path=ROOT / 'config/coding/reviewer_single_pass_v15_freeze.json',
        output_dir=TEST / 's5_changed_merge', production=False)
except ValueError as exc:
    assert 'Content used different complete scope' in str(exc)
else:
    raise AssertionError('Merger accepted S5 changed in a rehashed export container')

# A coded-null parent follows the ordinary bounded invalid-response path.
# Neither malformed scope form may escape as an exception/transient pause or
# silently reach content. Two attempts are the runner's default bounded repair.
for field_name in ['substance_roles', 'substance_all']:
    bad_scope = TEST / ('bad_scope_' + field_name)
    invented_search(bad_scope)
    workflow.extract(xml, bad_scope)
    bad_scope_responses = TEST / ('bad_scope_responses_' + field_name)
    shutil.copytree(fixtures, bad_scope_responses)
    malformed = scope('101', copy.deepcopy(units['101']))
    malformed['scope_units'][0][field_name] = coded(None)
    (bad_scope_responses / 'scope_full_101.json').write_text(json.dumps(malformed), encoding='utf-8')
    calls_before = calls.copy()
    # A first exhausted failure still awaits the separately authorized retry;
    # summary therefore remains incomplete and main returns an explicit 1.
    assert run_spied(bad_scope, response_dir=bad_scope_responses) == 1
    _, events = checkpoints(bad_scope, 1)
    invalid_events = [event for event in events if event['GOID'] == '101' and event['event'] == 'invalid']
    failed_events = [event for event in events if event['GOID'] == '101' and event['event'] == 'failed']
    assert [event['attempt'] for event in invalid_events] == [1, 2]
    assert len(failed_events) == 1 and failed_events[0]['failure_category'] == 'validation_exhausted'
    assert calls['scope_full', '101'] - calls_before['scope_full', '101'] == 2
    assert not any(event['event'] == 'paused_transient' or event['stage'] == 'content' for event in events)
    assert not any(event['GOID'] == '101' and event['event'] == 'validated' for event in events)
    assert not (bad_scope / 'worker_1_output/production_export_package.zip').exists()
    before_content = calls.copy()
    try:
        run_spied(bad_scope, release_content=True, response_dir=bad_scope_responses)
    except ValueError as exc:
        assert 'Content release requires every scope GOID validated' in str(exc)
    else:
        raise AssertionError('Content released despite unresolved failed scope')
    assert calls == before_content

# Attempts to add scope fields during content fail explicitly and withhold a
# completed package; they cannot silently enrich S4 or change inclusion.
bad = TEST / 'bad_content'
invented_search(bad)
workflow.extract(xml, bad)
assert run_spied(bad) == 0
bad_responses = TEST / 'bad_responses'
shutil.copytree(fixtures, bad_responses)
wrong = dict(responses['101'], substance_by_aim=[{'aim_id': 'a1', 'substance_all': coded(['opioids'])}])
(bad_responses / 'content_101.json').write_text(json.dumps(wrong), encoding='utf-8')
assert run_spied(bad, release_content=True, response_dir=bad_responses) == 1
progress = json.loads((bad / 'worker_1_output/production_progress.json').read_text(encoding='utf-8'))
assert progress['content_failed_n'] == 1 and progress['scope_status_counts']['in_scope'] == 6
assert not (bad / 'worker_1_output/production_export_package.zip').exists()
try:
    workflow.merge(bad, synthetic=True)
except (FileNotFoundError, ValueError):
    pass
else:
    raise AssertionError('Failed/partial coding accepted as a completed merge')

# Frozen instruments fail closed before an invocation when bytes drift.
active = artifacts / 'scope_prompt.md'
before = active.read_bytes()
try:
    active.write_bytes(before + b'\nchanged\n')
    stopped = subprocess.run(workflow.command(TEST / 'reader_1') + ['--preflight-only'], capture_output=True, text=True)
    assert stopped.returncode and 'Frozen file changed' in stopped.stderr
finally:
    active.write_bytes(before)

print(json.dumps({
    'known_answer_scope_cases': len(cases), 'endogenous_and_ordinary_same_scope_pass': 'passed',
    'scope_invocations_per_assessable_record': 1, 'later_S4_or_endogenous_stages': 0,
    'all_scope_fields_and_target_dependencies_immutable': 'passed',
    'S5_only_tampering_rejected_on_resume_and_rehashed_export_merge': 'passed',
    'unknown_S4_retained_without_enrichment': 'passed', 'content_rejects_scope_outputs': 'passed',
    'duplicate_unknown_and_missing_scope_structure_rejected': 'passed',
    'coded_null_scope_parents_fail_with_bounded_validation_attempts': 'passed',
    'one_and_two_worker_search_scope_content_merge': 'passed', 'missing_abstracts_make_no_calls': 'passed',
    'resume_makes_no_extra_calls': 'passed', 'failed_content_blocks_export': 'passed',
    'prompt_hash_drift_rejected': 'passed', 'synthetic_data_only': True,
}))
