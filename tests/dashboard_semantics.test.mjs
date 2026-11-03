// SPDX-License-Identifier: MIT
// Regressions for the populations, scenarios and uncertainty missed by the first UI audit.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {createDataClient} from '../dashboard/assets/data-client.mjs';
import {VIEWS,valueLabel} from '../dashboard/assets/view-specs.mjs';
import {makeDisplayRows,downloadRows,chartScale,warningMessages,readableValue,formatNumber,compactDownloadFields,unitLabel} from '../dashboard/assets/ui-model.mjs';

const root=new URL('../dashboard/',import.meta.url);
const client=createDataClient(root,async url=>({ok:true,status:200,json:async()=>JSON.parse(await readFile(new URL(url),'utf8'))}));

test('all released row labels distinguish populations and overlapping scenarios',async()=>{
  for(const [id,spec] of Object.entries(VIEWS)){
    const result=await client.load(id);
    const display=makeDisplayRows(result,spec);
    assert.equal(new Set(display.map(row=>row.label)).size,display.length,`${id}: ambiguous labels`);
  }
  const content=makeDisplayRows(await client.load('content_observed',{outcome:'C3'}),VIEWS.content_observed);
  assert.ok(content.some(row=>/Continuing institutions/.test(row.label)));
  assert.ok(content.some(row=>/Primary population/.test(row.label)));
  const awards=makeDisplayRows(await client.load('award_search_capture',{mechanism_group:'all_mechanisms',completion_period:'all',measure:'search_capture'}),VIEWS.award_search_capture);
  assert.equal(awards.length,6);
  assert.ok(awards.every(row=>/year award window/.test(row.label)));
});

test('source sparse flags and small bases remain visible without suppressing points',async()=>{
  assert.match(warningMessages({sparse_flag:'True'})[0],/Source sparse-group flag/);
  assert.match(warningMessages({denominator:8},'percent')[0],/Small base/);
  const result=await client.load('destination_connection');
  const available=result.rows.filter(row=>row.value_status==='available');
  assert.equal(available.length,99);
  assert.equal(available.filter(row=>warningMessages(row).some(s=>s.startsWith('Source sparse'))).length,66);
  const hospital=available.find(row=>row.group==='Hospitals'&&row.value==='-37.5');
  assert.ok(hospital);
  const shown=makeDisplayRows({...result,rows:[hospital]},VIEWS.destination_connection)[0];
  assert.equal(shown.value,'-37.5');
  assert.match(shown.warnings.join(' '),/n = 8/);
  assert.match(shown.warnings.join(' '),/n = 6/);
  const outside=await client.load('outside_roles');
  assert.equal(outside.rows.filter(row=>warningMessages(row).some(s=>s.startsWith('Small base'))).length,576);
});

test('fitted percentages are a display conversion; exact probability CSV remains unchanged',async()=>{
  const result=await client.load('institution_profiles',VIEWS.institution_profiles.defaultFilters);
  const before=JSON.stringify(result.rows),display=makeDisplayRows(result,VIEWS.institution_profiles),downloads=downloadRows(result);
  for(const row of display){
    assert.equal(row.displayUnit,'percent');
    assert.equal(row.displayValue,Number(row.value)*100);
    assert.equal(row.displayLower,row.lower===null?null:Number(row.lower)*100);
    const saved=downloads.find(record=>record.row_id===row.rowId);
    assert.equal(saved.value,row.value);
    assert.equal(saved.units,'probability');
  }
  assert.equal(JSON.stringify(result.rows),before);
  assert.equal(formatNumber(48.356,'percent'),'48.4');
  assert.equal(formatNumber(-37.5,'percentage_points'),'-37.5');
  assert.equal(formatNumber(1.1349096075322134,'rate_ratio'),'1.135');
});

test('all-page scales retain later page points and ratio scale uses a positive log domain around one',async()=>{
  const result=await client.load('content_observed',{outcome:'C3'});
  const rows=makeDisplayRows(result,VIEWS.content_observed),scale=chartScale(rows);
  for(let offset=0;offset<rows.length;offset+=20){
    for(const row of rows.slice(offset,offset+20))if(row.displayValue!==null)assert.ok(row.displayValue>=scale.min&&row.displayValue<=scale.max);
  }
  assert.ok(scale.ticks.length>=3);
  const ratio=makeDisplayRows(await client.load('institutional_count_associations'),VIEWS.institutional_count_associations),log=chartScale(ratio);
  assert.equal(log.kind,'log');assert.ok(log.min>0&&log.min<1&&log.max>1);assert.ok(log.ticks.includes(1));
  assert.ok(log.ticks.length<=3);
  for(let i=1;i<log.ticks.length;i++)assert.ok(Math.log(log.ticks[i]/log.ticks[i-1])/Math.log(log.max/log.min)>=0.2);
  assert.ok(ratio.some(row=>row.label.includes('Master’s / doctorate')));
  assert.ok(ratio.every(row=>row.label.includes('Increase from one to four')));
});

test('signed contrasts and saved comparison choices name their subtraction direction',async()=>{
  for(const id of ['content_observed_difference','content_fitted_contrasts','content_temporal_changes','funding_content_contrasts','destination_connection']){
    const result=await client.load(id,VIEWS[id].defaultFilters);
    assert.ok(makeDisplayRows(result,VIEWS[id]).every(row=>row.label.includes('minus')),id);
  }
  const pairs=await client.load('content_fitted_contrasts');
  for(const row of pairs.rows){const title=valueLabel('pair_id',row.pair_id);assert.ok(title.includes(row.group_a_label)&&title.includes(row.group_b_label)&&title.includes(' minus '));}
  assert.equal(valueLabel('joint_role','research_likely_only'),'Research only');
  assert.equal(valueLabel('degree_target','Masters minus research doctorate','institutional_count_associations'),'Master’s / doctorate');
  assert.match(unitLabel('qualifying_PI_work_participations_per_year'),/^In-scope/);
});

test('source category order is shared by the chart/table rows and selection CSV',async()=>{
  const result=await client.load('content_observed',VIEWS.content_observed.defaultFilters);
  const display=makeDisplayRows(result,VIEWS.content_observed),csv=downloadRows(result);
  const orders=display.map(row=>row.source.category_order);
  assert.deepEqual(orders,[...orders].sort((a,b)=>a-b));
  assert.deepEqual(display.map(row=>row.rowId),csv.map(row=>row.row_id));
  assert.equal(display[0].source.category,'mixed_methods');
});

test('structured cells are readable and compact downloads retain all nonempty fields, zeros and false',async()=>{
  assert.equal(readableValue('{"connected":70,"remaining":88}'),'Connected: 70; Remaining: 88');
  assert.equal(readableValue(null),'Not applicable');
  assert.equal(readableValue('{"Masters":{"0":2364,"1":751}}'),'Masters: Remaining: 2364; Connected: 751');
  const result=await client.load('institution_profiles',VIEWS.institution_profiles.defaultFilters),rows=downloadRows(result);
  const fields=compactDownloadFields(rows,result.fields);
  assert.ok(fields.length<result.fields.length);
  for(const field of result.fields)assert.equal(fields.includes(field),rows.some(row=>row[field]!==null&&row[field]!==undefined&&row[field]!==''));
  assert.deepEqual(compactDownloadFields([{zero:0,no:false,empty:'',missing:null}],['zero','no','empty','missing']),['zero','no']);
});

test('compact downloads retain a declared blank SOC identifier while dropping unrelated empty columns',async()=>{
  const metadata=await client.metadata('employment_occupations');
  const result=await client.load('employment_occupations',{soc_unit_code:''});
  const rows=downloadRows(result),fields=compactDownloadFields(rows,result.fields,metadata.output_key);
  assert.ok(rows.length>0);
  assert.ok(rows.every(row=>row.soc_unit_code===''));
  for(const key of metadata.output_key)assert.ok(fields.includes(key),`Declared key omitted: ${key}`);
  assert.ok(fields.includes('row_id'));
  assert.ok(fields.includes('source_key'));
  assert.ok(result.fields.some(field=>!metadata.output_key.includes(field)&&!fields.includes(field)), 'Unused non-key columns should still be removed');
  assert.deepEqual(compactDownloadFields([{soc:'',empty:'',zero:0,missing:null,state:'U'}],['soc','empty','zero','missing','state'],['soc']),['soc','zero','state']);
});
