// SPDX-License-Identifier: MIT
// Scientific UI regression tests use the actual released dataset artifacts.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {createDataClient, toCSV, validateQuery} from '../dashboard/assets/data-client.mjs';
import {selectedRows, makeDisplayRows, downloadRows, formatNumber, selectionQuery} from '../dashboard/assets/ui-model.mjs';
import {VIEWS} from '../dashboard/assets/view-specs.mjs';

const root = new URL('../dashboard/', import.meta.url);
const client = createDataClient(root, async url => ({ok:true, status:200,
  json:async () => JSON.parse(await readFile(new URL(url),'utf8'))}));
const read = async rel => JSON.parse(await readFile(new URL(rel,root),'utf8'));

test('every configured view opens a valid released selection with stable exact display tokens', async () => {
  const index = await client.index();
  assert.deepEqual(Object.keys(VIEWS).sort(),Object.keys(index.datasets).sort());
  for (const [dataset, spec] of Object.entries(VIEWS)) {
    const result = await client.load(dataset,spec.defaultFilters ?? {});
    const snapshot = JSON.stringify(result.rows);
    const display = makeDisplayRows(result,spec);
    assert.equal(display.length,result.rows.length,dataset);
    for (const row of display) {
      assert.equal(typeof row.label,'string',dataset);
      assert.ok(row.label.trim(),dataset);
      assert.equal(row.rowId,row.source.row_id,dataset);
      assert.equal(row.value ?? null,result.measure(row.source).value ?? null,dataset);
      assert.equal(row.lower ?? null,result.measure(row.source).lower ?? null,dataset);
      assert.equal(row.upper ?? null,result.measure(row.source).upper ?? null,dataset);
      assert.ok(row.value == null || typeof row.value === 'string' || Number.isFinite(row.value),dataset);
    }
    assert.equal(JSON.stringify(result.rows),snapshot,dataset+' mutated source records');
  }
});

test('true zero stays distinct from null and category selection does not rebase counts', async () => {
  const result = await client.load('population_composition');
  const zero = result.rows.find(row => row.value_status==='available' && Number(row.value)===0);
  assert.ok(zero);
  const selected = await client.load('population_composition',{degree_group:zero.degree_group,field_code:zero.field_code});
  const displayed = makeDisplayRows(selected,VIEWS.population_composition);
  assert.equal(displayed.length,1);
  assert.equal(displayed[0].value,zero.value);
  assert.equal(displayed[0].source.denominator,13227);
  assert.notEqual(formatNumber(zero.value),formatNumber(null));
  assert.equal(formatNumber('U'),'U');
  assert.notEqual(formatNumber('0.0000000123'),formatNumber('0'));
  assert.notEqual(formatNumber('-0.0000000123'),formatNumber('0'));
  assert.deepEqual(downloadRows(selected),selected.rows);
});

test('selected familywise bounds agree across display and download without mutating archived rows', async () => {
  const result = await client.load('institutional_count_associations',{interval_family:'familywise'});
  const snapshot = JSON.stringify(result.rows);
  const display = makeDisplayRows(result,VIEWS.institutional_count_associations);
  const downloaded = downloadRows(result);
  assert.equal(display.length,6);
  assert.equal(downloaded.length,6);
  for (let i=0; i<display.length; i++) {
    assert.equal(display[i].lower,display[i].source.lower_familywise);
    assert.equal(display[i].upper,display[i].source.upper_familywise);
    assert.equal(downloaded[i].lower,display[i].lower);
    assert.equal(downloaded[i].upper,display[i].upper);
    assert.equal(downloaded[i].interval_family,'familywise');
    assert.equal(downloaded[i].lower_pointwise,display[i].source.lower_pointwise);
    assert.equal(downloaded[i].upper_pointwise,display[i].source.upper_pointwise);
  }
  assert.equal(JSON.stringify(result.rows),snapshot);
});

test('valid institutional points survive missing intervals and profiles retain probability units', async () => {
  const result = await client.load('institution_profiles');
  const display = makeDisplayRows(result,VIEWS.institution_profiles);
  const missingIntervals = display.filter(row => row.source.value_status==='available' && row.source.interval_status==='unavailable');
  assert.equal(missingIntervals.length,60);
  for (const row of missingIntervals) {
    assert.notEqual(row.value,null);
    assert.equal(row.lower,null);
    assert.equal(row.upper,null);
    assert.equal(row.intervalStatus,'unavailable');
    assert.match(row.unit,/probabilit/i);
  }
});

test('catalog search selects exactly the same ordered source records for display and download', async () => {
  const result = await client.load('table_catalog');
  const query = 'occupation';
  const selected = selectedRows(result,query);
  assert.ok(selected.length>0 && selected.length<result.rows.length);
  const display = makeDisplayRows(result,VIEWS.table_catalog,query);
  const downloaded = downloadRows(result,query);
  assert.deepEqual(display.map(row => row.rowId),selected.map(row => row.row_id));
  assert.deepEqual(downloaded.map(row => row.row_id),selected.map(row => row.row_id));
  const csv = toCSV(downloaded,Object.keys(downloaded[0]));
  assert.ok(csv.includes(selected[0].table));
  assert.equal(selectedRows(result,'no-matching-study-table-123456').length,0);
  const population = await client.load('population_composition');
  assert.equal(selectedRows(population,'occupation').length,population.rows.length,'Catalog search leaked into a scientific population view');
});

test('shared links retain multi-selection, legitimate blanks and reject invalid controls', async () => {
  const filters={degree_group:["Field-specific master's"],occupation_status:['aggregate_residual'],soc_unit_code:['']};
  const query=selectionQuery('employment_occupations',filters);
  const spec=await client.filters('employment_occupations');
  const checked=validateQuery(spec,query);
  assert.deepEqual(checked.filters.soc_unit_code,['']);
  assert.deepEqual(checked.filters.degree_group,filters.degree_group);
  const institution=await client.filters('institution_profiles');
  assert.throws(() => validateQuery(institution,selectionQuery('institution_profiles',{period:['2010-2016']})));
});

test('UI download preserves original decimal precision and row membership before display rounding', async () => {
  const result=await client.load('institution_profiles',VIEWS.institution_profiles.defaultFilters);
  const rows=downloadRows(result);
  const display=makeDisplayRows(result,VIEWS.institution_profiles);
  assert.equal(rows.length,display.length);
  const originalById=new Map(result.rows.map(row=>[row.row_id,row]));
  for(let i=0;i<rows.length;i++) {
    assert.equal(rows[i].row_id,display[i].rowId);
    assert.equal(rows[i].value,originalById.get(rows[i].row_id).value);
    assert.equal(rows[i].denominator,originalById.get(rows[i].row_id).denominator);
  }
  assert.ok(rows.some(row => typeof row.value==='string' && row.value.length>8));
});
