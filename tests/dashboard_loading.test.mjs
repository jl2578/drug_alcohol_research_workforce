// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {createDataClient, NetworkError, availableOptions, validateSelection} from '../dashboard/assets/data-client.mjs';

const base = new URL('../dashboard/',import.meta.url);
const response = body => ({ok:true,status:200,json:async () => body});
const options = {retryDelayMs:0,timeoutMs:1000};

test('transient transport, server, and interrupted body errors retry and then cache only successful data',async () => {
  for (const failure of [() => {throw new TypeError('connection dropped');},
    () => ({ok:false,status:503}),
    () => ({ok:true,status:200,json:async () => {throw new SyntaxError('Truncated JSON');}})]) {
    let calls=0;
    const client=createDataClient(base,async () => ++calls < 3 ? failure() : response({datasets:{}}),options);
    assert.deepEqual(await client.index(),{datasets:{}});
    assert.equal(calls,3);
    await client.index(); assert.equal(calls,3,'A successful response is cached');
  }
});

test('exhausted transport failures are distinct from invalid selections and allow a later retry',async () => {
  let failing=true,calls=0;
  const client=createDataClient(base,async () => {calls++; if(failing)throw new TypeError('Offline'); return response({datasets:{}});},options);
  await assert.rejects(client.index(),error => error instanceof NetworkError && error.attempts===3 && error.path==='metadata/index.json');
  assert.equal(calls,3);
  failing=false;
  assert.deepEqual(await client.index(),{datasets:{}});
  assert.equal(calls,4,'A rejected promise must not poison the cache');
  await assert.rejects(client.load('not_a_dataset'),error => !(error instanceof NetworkError) && /Unknown/.test(error.message));
});

test('missing files fail immediately with a load error, while timeouts are bounded and retryable',async () => {
  let calls=0;
  const missing=createDataClient(base,async () => {calls++;return {ok:false,status:404};},options);
  await assert.rejects(missing.index(),error => error instanceof NetworkError && error.status===404 && error.attempts===1);
  assert.equal(calls,1);
  const stalled=createDataClient(base,async () => {calls++;return new Promise(() => {});},{retryAttempts:2,retryDelayMs:0,timeoutMs:5});
  await assert.rejects(stalled.index(),error => error instanceof NetworkError && error.attempts===2 && /timed out/.test(error.cause.message));
  assert.equal(calls,3);
});

test('metadata uses the shared retry path and in-flight requests are deduplicated',async () => {
  const calls=[];
  const client=createDataClient(base,async url => {
    calls.push(url);
    if(url.endsWith('index.json'))return response({datasets:{example:{manifest:'metadata/datasets/example.json'}}});
    if(calls.filter(value => value===url).length===1)throw new TypeError('Connection dropped');
    return response({population_definition:'Released population'});
  },options);
  const [a,b]=await Promise.all([client.metadata('example'),client.metadata('example')]);
  assert.deepEqual(a,b);assert.equal(a.population_definition,'Released population');
  assert.equal(calls.filter(url => url.endsWith('index.json')).length,1);
  assert.equal(calls.filter(url => url.endsWith('example.json')).length,2);
});

test('indexed options preserve multi-selection witnesses, aliases, virtual selectors and missing-code choices',() => {
  const spec={fields:['population','category','code'],aliases:{pop:'population'},virtual_filters:{interval:{values:['pointwise','familywise']}},
    domains:{population:['primary','continuing'],category:['A','B'],code:['','x']},
    tuples:[[0,0,0],[1,0,0],[0,1,1]]};
  assert.deepEqual(availableOptions(spec,{pop:['primary','continuing'],interval:'pointwise'},'category'),['A']);
  assert.deepEqual(availableOptions(spec,{population:'primary',category:'B'},'category'),['A','B']);
  assert.deepEqual(availableOptions(spec,{category:'A'},'code'),['']);
  assert.throws(() => validateSelection(spec,{population:['primary','continuing'],category:'B'}),/Unsupported value/);
  assert.throws(() => availableOptions(spec,{population:'primary',pop:'continuing'},'category'),/Duplicate/);
  assert.throws(() => validateSelection(spec,{population:'continuing',category:'B'}),/Unsupported combination/);
  assert.equal(validateSelection(spec,{pop:'primary',code:''}).matching_tuple_count,1);
});

test('cached tuple index agrees with a direct oracle on the 61,812-row occupation lookup',async () => {
  const spec=JSON.parse(await readFile(new URL('metadata/filters/rc_rmi_lookup.json',base),'utf8'));
  const selection={specification:'inclusive',naics_code_canonical:spec.domains.naics_code_canonical[0]};
  const column=spec.fields.indexOf('soc_code_canonical');
  const matching=spec.tuples.filter(tuple => Object.entries(selection).every(([key,value]) => spec.domains[key][tuple[spec.fields.indexOf(key)]]===value));
  const expected=spec.domains.soc_code_canonical.filter((value,i) => typeof value==='string' && matching.some(tuple => tuple[column]===i));
  assert.deepEqual(availableOptions(spec,selection,'soc_code_canonical'),expected);
  assert.equal(validateSelection(spec,selection).matching_tuple_count,matching.length);
  // Reusing the same immutable specification must not read/rebuild every tuple.
  const originalMap=spec.tuples.map;
  spec.tuples.map=() => {throw new Error('Rebuilt tuple index during a selector change');};
  try {assert.deepEqual(availableOptions(spec,selection,'soc_code_canonical'),expected);}
  finally {spec.tuples.map=originalMap;}
});
