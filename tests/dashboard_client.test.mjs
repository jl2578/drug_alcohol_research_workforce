// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';
import {createDataClient, validateQuery, availableOptions, decodeShard} from '../dashboard/assets/data-client.mjs';

const root = new URL('../dashboard/', import.meta.url);
const read = async rel => JSON.parse(await readFile(new URL(rel, root), 'utf8'));
function client() {
  const calls = [];
  return {calls, client: createDataClient(root, async url => {
    calls.push(fileURLToPath(url));
    return {ok:true, status:200, json:async () => JSON.parse(await readFile(url.startsWith('file:') ? new URL(url) : url, 'utf8'))};
  })};
}

test('entrypoint loads only a small index and selected-view shards', async () => {
  const {client:c, calls} = client();
  await c.index(); assert.equal(calls.length,1);
  const spec = await c.filters('rc_rmi_lookup');
  const selection = {specification:'inclusive',soc_code_canonical:spec.domains.soc_code_canonical[0],naics_code_canonical:spec.domains.naics_code_canonical[0]};
  const result = await c.load('rc_rmi_lookup',selection);
  assert.equal(result.rows.length,1);
  assert.ok(calls.every(p => !p.includes('content_fitted')));
  assert.ok(calls.filter(p => /rc_rmi_lookup[\\/]\d+\.json$/.test(p)).length < 4);
  assert.equal(result.rows[0].specification,'inclusive');
});

test('shared URLs reject unknown/deferred filters and unsupported real tuples', async () => {
  const spec = await read('metadata/filters/employment_connection_profiles.json');
  assert.throws(() => validateQuery(spec,'?dataset=employment_connection_profiles&specification=no_hospital_override'));
  assert.throws(() => validateQuery(spec,'?dataset=employment_connection_profiles&period=late'));
  assert.throws(() => validateQuery(spec,'?dataset=employment_connection_profiles&dataset=employment_connection_profiles'));
  const institutional = await read('metadata/filters/institution_profiles.json');
  assert.throws(() => validateQuery(institutional,'?dataset=institution_profiles&period=early'));
  const {client:c} = client();
  await assert.rejects(c.load('employment_training_linked'));
});

test('category selection keeps denominators and exact CSV values', async () => {
  const {client:c} = client();
  const all = await c.load('population_composition');
  const first = all.rows[0];
  const selected = await c.load('population_composition',{degree_group:first.degree_group,field_code:first.field_code});
  assert.equal(selected.rows.length,1);
  assert.equal(selected.rows[0].denominator,13227);
  assert.equal(selected.rows[0].value,first.value);
  assert.deepEqual(selected.rows[0],first);
  assert.ok(selected.csv().includes(String(first.denominator)));
});

test('institution aliases work and fixed benchmark ignores selection', async () => {
  const {client:c} = client();
  const spec = await c.filters('institution_profiles');
  const selected = await c.load('institution_profiles', {outcome:'C3', institution_selection:spec.domains.institution_id[0]});
  assert.ok(selected.rows.length > 0);
  const a = await c.load('institution_benchmark',{outcome:'C3'});
  await c.load('institution_profiles',{outcome:'C3',institution_selection:spec.domains.institution_id.at(-1)});
  const b = await c.load('institution_benchmark',{outcome:'C3'});
  assert.deepEqual(a.rows,b.rows);
  await assert.rejects(c.load('institution_benchmark',{institution_selection:spec.domains.institution_id[0]}));
});

test('dependent options are actual tuples and interval selector names saved fields', async () => {
  const spec = {fields:['a','b'],aliases:{},virtual_filters:{},domains:{a:['x','y'],b:['1','2']},tuples:[[0,0],[1,1]]};
  assert.deepEqual(availableOptions(spec,{a:'x'},'b'),['1']);
  const {client:c} = client();
  const result = await c.load('institutional_count_associations',{interval_family:'familywise'});
  assert.equal(result.activeFields.lower,'lower_familywise');
  assert.equal(result.activeFields.upper,'upper_familywise');
  for (const row of result.rows) {
    assert.equal(result.measure(row).lower,row.lower_familywise);
    assert.equal(result.measure(row).upper,row.upper_familywise);
  }
});

test('dictionary decoding keeps null, empty, numeric zero and U distinct', () => {
  assert.deepEqual(decodeShard({dictionaries:{'0':['U','']},rows:[[0,null,0],[1,null,0]]},['state','missing','zero']),
    [{state:'U',missing:null,zero:0},{state:'',missing:null,zero:0}]);
});
