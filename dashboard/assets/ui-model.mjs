// SPDX-License-Identifier: MIT
import {labelFor, unitFor, VIEWS, fieldLabel, valueLabel} from './view-specs.mjs';

export function asNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
export function formatNumber(value, unit='') {
  if(value==='U')return 'U';
  const number = asNumber(value);
  if(number!==null&&number!==0&&Math.abs(number)<0.0001&&!unit)return number.toExponential(3);
  const digits=unit==='rate_ratio'?3:['percent','percentage_points'].includes(unit)?1:null;
  return number === null ? 'Unavailable' : new Intl.NumberFormat('en-US', digits===null?{maximumFractionDigits:4}:{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(number);
}
export function displayUnit(unit) {
  if(unit==='probability')return 'percent';
  if(unit==='qualifying_PI_work_participations_per_year')return 'in_scope_PI_work_participations_per_year';
  return unit;
}
export function displayValue(value,unit) {
  const number=asNumber(value);
  return number===null?null:unit==='probability'?number*100:number;
}
export function unitLabel(unit) {
  return ({percent:'Percent',percentage_points:'Percentage points',rate_ratio:'Rate ratio',probability:'Probability',in_scope_PI_work_participations_per_year:'In-scope PI–work participations per year',qualifying_PI_work_participations_per_year:'In-scope PI–work participations per year'})[unit]??fieldLabel(unit);
}
function structured(value) {
  if(typeof value==='string' && /^[\[{]/.test(value.trim())){try{return JSON.parse(value);}catch{}}
  return value;
}
export function readableValue(value,field='',dataset='') {
  const parsed=structured(value);
  if(parsed==null)return 'Not applicable';
  if(Array.isArray(parsed))return parsed.map(item=>readableValue(item,field,dataset)).join('; ');
  if(typeof parsed==='object') {
    const connectionCodes=Object.hasOwn(parsed,'0')&&Object.hasOwn(parsed,'1');
    return Object.entries(parsed).map(([key,item])=>`${connectionCodes?({'0':'Remaining','1':'Connected'}[key]??fieldLabel(key)):fieldLabel(key)}: ${readableValue(item,key,dataset)}`).join('; ');
  }
  if(typeof parsed==='boolean')return parsed?'Yes':'No';
  if(typeof parsed==='number')return String(parsed);
  return valueLabel(field,String(parsed),dataset).replaceAll('qualifying PI work participations per year','in-scope PI–work participations per year');
}
function baseEntries(row) {
  const bases=[];
  const add=(label,value)=>{const n=asNumber(value);if(n!==null)bases.push([label,n]);};
  if(asNumber(row.denominator)!==null)add('Base',row.denominator);
  else {
    const denominator=structured(row.denominator);
    const walk=(obj,prefix='')=>{if(!obj||typeof obj!=='object')return;for(const [key,v]of Object.entries(obj)){const name=({'0':'Remaining','1':'Connected',connected_observed_n:'Connected',no_identified_connection_observed_n:'No identified connection'})[key]??fieldLabel(key);if(v&&typeof v==='object')walk(v,`${prefix}${name} / `);else add(prefix+name,v);}};
    walk(denominator);
  }
  if(!bases.length)for(const key of ['denominator_a','denominator_b','connected_observed_n','no_identified_connection_observed_n'])if(row[key]!=null)add(fieldLabel(key),row[key]);
  return bases;
}
export function warningMessages(row,unit=row.units??row.unit) {
  const messages=[],bases=baseEntries(row);
  const sparse=[row.sparse_flag,row.sparse_group_n_under_10,row.source_sparse_group_n_under_10].some(value=>String(value).toLowerCase()==='true');
  if(sparse)messages.push('Source sparse-group flag (at least one n < 10)'+(bases.length?': '+bases.map(([label,n])=>`${label}: n = ${n}`).join('; ')+'.':'.'));
  const small=bases.filter(([,n])=>n>0&&n<30);
  if(['percent','percentage_points'].includes(unit)&&small.length)messages.push(sparse?'Small base (n < 30); interpret cautiously. Values are not suppressed.':'Small base (n < 30): '+small.map(([label,n])=>`${label}: n = ${n}`).join('; ')+'. Interpret cautiously. Values are not suppressed.');
  return messages;
}
function orderedRows(rows,dataset) {
  const spec=VIEWS[dataset];
  if(!spec||!rows.some(row=>asNumber(row.category_order)!==null))return rows;
  const identity=spec.labelFields.filter(field=>!['category','category_label'].includes(field));
  const groups=new Map;
  for(const row of rows){const key=JSON.stringify(identity.map(field=>row[field]??null));if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
  return [...groups.values()].flatMap(group=>group.toSorted((a,b)=>(asNumber(a.category_order)??Infinity)-(asNumber(b.category_order)??Infinity)));
}
export function selectedRows(result, search = '') {
  if(result.manifest?.dataset_id!=='table_catalog')return orderedRows(result.rows,result.manifest?.dataset_id);
  const words = search.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  if (!words.length) return result.rows;
  return result.rows.filter(row => words.every(word => ['table','title','description','backs_displays'].map(k => String(row[k] ?? '')).join(' ').toLocaleLowerCase().includes(word)));
}
export function makeDisplayRows(result, spec, search = '') {
  return selectedRows(result,search).map(source => {
    const measure = result.measure(source);
    const unit=unitFor(source,spec);
    return {source, rowId:source.row_id, label:labelFor(source,spec), value:measure.value,
      lower:measure.lower, upper:measure.upper, unit:unitFor(source,spec),
      displayValue:displayValue(measure.value,unit),displayLower:displayValue(measure.lower,unit),displayUpper:displayValue(measure.upper,unit),displayUnit:displayUnit(unit),
      warnings:warningMessages(source,unit),valueStatus:source.value_status, intervalStatus:measure.interval_status};
  });
}
export function compactDownloadFields(rows,fields,requiredFields=[]) {
  // Remove only columns that are empty in every selected record; zero and false
  // remain informative. Declared keys can contain legitimate blank codes and
  // must survive even when the selected records all use that blank code.
  // The complete canonical CSV remains a separate download.
  const required=new Set(requiredFields);
  return fields.filter(field=>required.has(field)||rows.some(row=>row[field]!==null&&row[field]!==undefined&&row[field]!==''));
}
export function chartScale(rows) {
  const units=[...new Set(rows.filter(row=>asNumber(row.displayValue)!==null).map(row=>row.displayUnit))];
  if(units.length!==1)return {min:0,max:1,kind:'linear',ticks:[0,1],unit:units[0]??'',mixed:units.length>1};
  const unit=units[0],kind=unit==='rate_ratio'?'log':'linear';
  const values=rows.flatMap(row=>[row.displayValue,...(row.intervalStatus==='available'?[row.displayLower,row.displayUpper]:[])]).map(asNumber).filter(n=>n!==null&&(kind!=='log'||n>0));
  if(kind==='log'){
    const low=Math.min(1,...values),high=Math.max(1,...values);
    const min=Math.exp(Math.log(low)-(Math.log(high/low)||Math.log(2))*0.08),max=Math.exp(Math.log(high)+(Math.log(high/low)||Math.log(2))*0.08);
    const logSpan=Math.log(max/min),ticks=[1];
    // The null value has priority. Keep endpoint labels only when at least one
    // fifth of the plotted log span separates their labels from every other tick.
    for(const endpoint of [min,max])if(ticks.every(tick=>Math.abs(Math.log(endpoint/tick))/logSpan>=0.2))ticks.push(endpoint);
    ticks.sort((a,b)=>a-b);
    return {min,max,kind,ticks,unit};
  }
  const rawMin=Math.min(0,...values),rawMax=Math.max(0,...values),span=rawMax-rawMin||1;
  const magnitude=10**Math.floor(Math.log10(span/4)),factor=(span/4)/magnitude;
  const step=(factor<=1?1:factor<=2?2:factor<=5?5:10)*magnitude;
  const min=Math.floor(rawMin/step)*step,max=Math.ceil((rawMax||1)/step)*step;
  const ticks=[];for(let n=min;n<=max+step/100;n+=step)ticks.push(Number(n.toPrecision(12)));
  return {min,max,kind,ticks,unit};
}
export function downloadRows(result, search = '') {
  return selectedRows(result,search).map(row => {
    if (!Object.keys(result.activeFields ?? {}).length) return {...row};
    const measure = result.measure(row);
    return {...row, lower:measure.lower, upper:measure.upper,
      interval_status:measure.interval_status, interval_family:measure.interval_family};
  });
}
export function selectionQuery(dataset, filters = {}, search = '') {
  const params = new URLSearchParams({dataset});
  for (const [field, values] of Object.entries(filters))
    for (const value of Array.isArray(values) ? values : [values]) params.append(field,value);
  if (search) params.set('q',search);
  return params.toString();
}
