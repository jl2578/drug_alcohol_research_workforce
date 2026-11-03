import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';

// Tests exercise the rendered interface and real, pinned dataset exports.
// Network interception below injects transport failures only, never study data.
async function loaded(page) {
  await expect(page.locator('#status')).toContainText('Selection loaded');
  await expect(page.locator('#error-panel')).toBeHidden();
  await expect(page.locator('#download-csv')).toBeEnabled();
}
async function openView(page,id) {
  await page.goto('./');
  await loaded(page);
  if (id!=='population_composition') {
    await page.locator('#dataset-select').selectOption(id);
    await loaded(page);
  }
}
async function rowTokens(page,selector) {
  return page.locator(selector).evaluateAll(nodes=>nodes.map(n=>[n.dataset.rowId,n.dataset.value]));
}
async function alignedReference(page,reference) {
  await expect.poll(async()=>page.evaluate(reference=>{
    const axis=document.querySelector(`.chart-axis text[data-tick="${reference}"]`);
    if(!axis)return Infinity;
    const point=(el,attribute)=>new DOMPoint(Number(el.getAttribute(attribute)),0).matrixTransform(el.getScreenCTM()).x;
    const x=point(axis,'x'),marks=[...document.querySelectorAll(`.chart-row [data-reference="${reference}"]`)];
    return marks.length?Math.max(...marks.map(mark=>Math.abs(point(mark,'x1')-x))):Infinity;
  },reference)).toBeLessThan(1);
}
function parseCSV(text) {
  const rows=[]; let row=[],value='',quoted=false;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(c==='"') {if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){row.push(value);value='';}
    else if(c==='\n'&&!quoted){row.push(value.replace(/\r$/,''));rows.push(row);row=[];value='';}
    else value+=c;
  }
  if(value||row.length){row.push(value);rows.push(row);}
  const fields=rows.shift();return rows.map(cells=>Object.fromEntries(fields.map((f,i)=>[f,cells[i]??''])));
}

test('content dimension changes retain primary population and applied labels until Apply',async({page})=>{
  await openView(page,'content_observed');
  await expect(page.locator('#filter-population')).toHaveValue('primary');
  const before=await rowTokens(page,'#table-body tr');
  const applied=await page.locator('#selection-summary').innerText();
  expect(applied).toMatch(/primary/i);
  await page.locator('#filter-outcome').selectOption('C4');
  await expect(page.locator('#filter-population')).toHaveValue('primary');
  await expect(page.locator('#filter-group_id')).toHaveValue('Research doctorate|BF01');
  await expect(page.locator('#filter-period')).toHaveValue('2017-2023');
  await expect(page.locator('#status')).toContainText(/pending/i);
  expect(await page.locator('#selection-summary').innerText()).toBe(applied);
  expect(await rowTokens(page,'#table-body tr')).toEqual(before);
  await page.locator('#apply-filters').click();await loaded(page);
  await expect(page.locator('#selection-summary')).toContainText(/primary/i);
  await expect(page.locator('#selection-summary')).toContainText(/C4|Level of analysis/i);
  for(const text of await page.locator('.chart-label').allTextContents())expect(text).toMatch(/primary/i);
  await expect(page.locator('#table-body')).not.toContainText(/continuing institutions/i);
});

test('award timing and match scenarios are explicit, required and uniquely labeled',async({page})=>{
  await openView(page,'award_search_capture');
  await expect(page.locator('#filter-extension_years')).toHaveValue('3');
  await expect(page.locator('#filter-match_definition')).toHaveValue('clear');
  const labels=await page.locator('.chart-label').allTextContents();
  expect(labels.length).toBeGreaterThan(0);
  expect(new Set(labels).size).toBe(labels.length);
  for(const label of labels){expect(label).toMatch(/3.*year|year.*3/i);expect(label).toMatch(/clear/i);}
  await page.goto('?dataset=award_search_capture&mechanism_group=all_mechanisms&completion_period=all&measure=search_capture');
  await expect(page.locator('#error-panel')).toBeVisible();
  await expect(page.locator('#error-panel')).toContainText(/choose|select|required|scenario/i);
  await expect(page.locator('#table-body tr')).toHaveCount(0);
});

test('pagination keeps the full-selection scale and chart/table records agree',async({page})=>{
  await page.goto('?dataset=institution_profiles&outcome=C3&institution_id=U100663&institution_id=U104151&institution_id=U104179');
  await loaded(page);
  const scale=await page.locator('#chart').getAttribute('data-scale');
  expect(scale).toBeTruthy();
  expect(await page.locator('.chart-axis text').count()).toBeGreaterThan(1);
  expect(await rowTokens(page,'.chart-row')).toEqual(await rowTokens(page,'#table-body tr'));
  await page.locator('#page-next').click();
  await expect(page.locator('#page-label')).toContainText('21');
  expect(await page.locator('#chart').getAttribute('data-scale')).toBe(scale);
  expect(await rowTokens(page,'.chart-row')).toEqual(await rowTokens(page,'#table-body tr'));
  await alignedReference(page,0);
  await page.setViewportSize({width:390,height:1000});await alignedReference(page,0);
});

test('Hospitals keeps its -37.5 point and exposes source sparse-group bases 8 and 6',async({page},testInfo)=>{
  await openView(page,'destination_connection');
  const row=page.locator('.chart-row').filter({hasText:'Hospitals'});
  await expect(row).toHaveCount(1);
  await expect(row).toHaveAttribute('data-value','-37.5');
  await expect(row.locator('.warning-note')).toContainText(/sparse/i);
  await expect(row).toContainText(/n\s*=\s*8/);
  await expect(row).toContainText(/n\s*=\s*6/);
  const table=page.locator('#table-body tr').filter({hasText:'Hospitals'});
  await expect(table).toContainText(/sparse/i);
  await expect(table).not.toContainText('{"');
  await page.setViewportSize({width:390,height:1100});
  await row.scrollIntoViewIfNeeded();
  await page.screenshot({path:testInfo.outputPath('hospitals-narrow.png')});
});

test('small employment bases are cautioned without suppressing the values',async({page})=>{
  await openView(page,'outside_roles');
  await page.locator('#filter-destination_dimension').selectOption('grouped');
  const destination=page.locator('#filter-destination');
  const choices=await destination.locator('option').evaluateAll(options=>options.map(o=>({value:o.value,label:o.textContent})));
  const hospital=choices.find(o=>/hospital/i.test(o.label));
  expect(hospital).toBeTruthy();await destination.selectOption(hospital.value);
  await page.locator('#apply-filters').click();await loaded(page);
  await expect(page.locator('#chart')).toContainText(/small base.*n < 30/i);
  expect(await page.locator('.chart-row[data-value]:not([data-value=""])').count()).toBeGreaterThan(0);
});

test('rate ratios use a log forest plot, one reference and numerator/reference labels',async({page},testInfo)=>{
  await openView(page,'institutional_count_associations');
  await expect(page.locator('#view-description')).toContainText(/from one to four/i);
  await expect(page.locator('#chart')).toContainText(/Master.s\s*\/\s*doctorate/i);
  await expect(page.locator('#chart')).not.toContainText(/Masters minus research doctorate/i);
  await expect(page.locator('#chart-subtitle')).toContainText(/log/i);
  await expect(page.locator('.chart-row svg rect')).toHaveCount(0);
  expect(await page.locator('.chart-row svg circle').count()).toBeGreaterThan(0);
  expect(await page.locator('[data-reference="1"]').count()).toBeGreaterThan(0);
  await alignedReference(page,1);
  for(const text of await page.locator('.chart-value').allTextContents())expect(text).toMatch(/\d\.\d{3}/);
  await page.locator('#chart-section').screenshot({path:testInfo.outputPath('rate-ratios-desktop.png')});
  await page.setViewportSize({width:390,height:1000});await alignedReference(page,1);
});

test('definitions, structured bases and in-scope participation units are readable',async({page})=>{
  for(const id of ['funding_content_contrasts','destination_connection','within_pi_participation']) {
    await openView(page,id);
    await page.locator('summary').filter({hasText:'Definitions & interpretation'}).click();
    const definitions=await page.locator('#definitions').innerText();
    expect(definitions).not.toMatch(/Numerator:\s*null|\{\s*"|\[\s*"/);
    expect(await page.locator('#table-body').innerText()).not.toContain('{"');
    expect(await page.locator('main').innerText()).not.toContain('qualifying_PI_work_participations_per_year');
  }
});

test('catalog has one source-download column and recognizable source filenames',async({page})=>{
  await openView(page,'table_catalog');
  await expect(page.locator('#table-head th').filter({hasText:/^Source download$/})).toHaveCount(1);
  const link=page.locator('#table-body a[download]').first();
  const filename=await link.getAttribute('download');
  expect(filename).toMatch(/\.(csv|json)$/);
  expect(filename).not.toMatch(/^[a-f0-9]{20,}\.csv$/);
  const pending=page.waitForEvent('download');await link.click();
  const download=await pending;expect(download.suggestedFilename()).toBe(filename);
  expect(await readFile(await download.path(),'utf8')).not.toHaveLength(0);
});

test('selection CSV preserves exact chart/table tokens and all pages',async({page})=>{
  await page.goto('?dataset=institution_profiles&outcome=C3&institution_id=U100663&institution_id=U104151&institution_id=U104179');
  await loaded(page);
  const visible=await rowTokens(page,'.chart-row');
  const pending=page.waitForEvent('download');await page.locator('#download-csv').click();
  const download=await pending;
  const rows=parseCSV(await readFile(await download.path(),'utf8'));
  expect(rows).toHaveLength(36);
  const byID=new Map(rows.map(r=>[r.row_id,r]));
  for(const [id,value]of visible)expect(byID.get(id).value).toBe(value);
  expect(Object.keys(rows[0]).length).toBeLessThan(196);
  expect(download.suggestedFilename()).toBe('institution_profiles-selection.csv');
  await page.locator('#dataset-select').selectOption('employment_occupations');await loaded(page);
  await page.locator('#filter-soc_unit_code').selectOption('');
  await page.locator('#apply-filters').click();await loaded(page);
  const occupationPending=page.waitForEvent('download');await page.locator('#download-csv').click();
  const occupationDownload=await occupationPending;
  const occupations=parseCSV(await readFile(await occupationDownload.path(),'utf8'));
  expect(occupations.length).toBeGreaterThan(0);
  for(const row of occupations){expect(row).toHaveProperty('soc_unit_code');expect(row.soc_unit_code).toBe('');}
});

test('transport failure is distinct from missing data and Retry recovers the initial load',async({page})=>{
  await page.route('**/dashboard/metadata/index.json',route=>route.abort('connectionfailed'));
  await page.goto('./');
  await expect(page.locator('#error-panel')).toContainText(/network|load|connection/i);
  await expect(page.locator('#error-panel')).not.toContainText('This selection is unavailable');
  await expect(page.locator('#dataset-select option')).toHaveCount(26);
  await expect(page.locator('#download-csv')).toBeDisabled();
  await page.unroute('**/dashboard/metadata/index.json');
  await page.locator('#retry-load').click();await loaded(page);
});

test('navigation remains usable after a failed first load',async({page})=>{
  await page.route('**/dashboard/metadata/filters/population_composition.json',route=>route.abort('connectionfailed'));
  await page.goto('./');
  await expect(page.locator('#error-panel')).toBeVisible();
  await page.locator('#dataset-select').selectOption('table_catalog');await loaded(page);
  await expect(page.locator('#view-title')).toHaveText('Complete evidence catalog');
});

test('Back restores a prior applied view and invalid links recover explicitly',async({page})=>{
  await openView(page,'employment_roles');
  const priorURL=page.url();
  await page.locator('#dataset-select').selectOption('funding_reach');await loaded(page);
  await page.goBack();await loaded(page);
  expect(page.url()).toBe(priorURL);
  await expect(page.locator('#dataset-select')).toHaveValue('employment_roles');
  await page.goto('?dataset=institution_benchmark&outcome=C3&institution_id=U100663');
  await expect(page.locator('#error-panel')).toBeVisible();
  await expect(page.locator('#table-body tr')).toHaveCount(0);
  await page.locator('#dataset-select').selectOption('population_composition');await loaded(page);
});

test('exact values are keyboard-accessible and charts do not re-announce every record',async({page})=>{
  await openView(page,'institution_profiles');
  const details=page.locator('.chart-row .exact-value').first();
  await details.locator('summary').focus();await page.keyboard.press('Enter');
  await expect(details).toHaveAttribute('open','');
  await expect(details).toContainText(/exact|source/i);
  await expect(page.locator('#chart')).not.toHaveAttribute('aria-live','polite');
  await expect(page.locator('#status')).toHaveAttribute('role','status');
});

test('fixed institution reference is unchanged after selecting different institutions',async({page})=>{
  await openView(page,'institution_benchmark');const before=await rowTokens(page,'#table-body tr');
  await page.locator('#dataset-select').selectOption('institution_profiles');await loaded(page);
  await page.locator('#filter-institution_id').selectOption(['U104151','U104179']);
  await page.locator('#apply-filters').click();await loaded(page);
  await page.locator('#dataset-select').selectOption('institution_benchmark');await loaded(page);
  expect(await rowTokens(page,'#table-body tr')).toEqual(before);
});

test('all 26 actual view selections load without page errors',async({page})=>{
  test.setTimeout(150000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await openView(page,'population_composition');
  const datasets=await page.locator('#dataset-select option').evaluateAll(options=>options.map(option=>option.value));
  expect(datasets).toHaveLength(26);
  for(const id of datasets)await test.step(id,async()=>{
    await page.locator('#dataset-select').selectOption(id);await loaded(page);
    await expect(page.locator('#dataset-select')).toHaveValue(id);
    expect(await page.locator('#table-body tr').count()).toBeGreaterThan(0);
  });
  expect(errors).toEqual([]);
});

test('occupation search and saved-comparison options identify their meaning',async({page})=>{
  await openView(page,'rc_rmi_lookup');
  const options=page.locator('#filter-soc_code_canonical option');
  const total=await options.count();expect(total).toBeGreaterThan(300);
  await page.locator('#occupation-search').fill('epidemiologist');
  expect(await options.count()).toBeLessThan(total);
  // The retained current choice, "Medical Scientists, Except Epidemiologists",
  // also contains this search token; check the intended SOC explicitly.
  await expect(page.locator('#filter-soc_code_canonical option[value="19-1041.00"]')).toHaveText(/epidemiologist/i);
  await page.locator('#filter-soc_code_canonical').selectOption('19-1041.00');
  await page.locator('#apply-filters').click();await loaded(page);
  await expect(page.locator('.lookup-card')).toContainText(/epidemiologist/i);
  await expect(page.locator('.lookup-card')).not.toContainText(/research_likely_only|clinical_likely_only/);
  await page.locator('#dataset-select').selectOption('content_fitted_contrasts');await loaded(page);
  const pairs=await page.locator('#filter-pair_id option').allTextContents();
  const identified=pairs.filter(text=>/P\d{3}/.test(text));
  expect(identified.length).toBeGreaterThan(0);
  for(const text of identified)expect(text.trim()).not.toMatch(/^P\d{3}$/);
});

test('hiding content categories preserves the original eligible denominator',async({page})=>{
  await openView(page,'content_observed');
  const first=await page.locator('#table-body tr').first().getAttribute('data-row-id');
  const canonical=parseCSV(await readFile(new URL('../../dashboard/data/content_observed.csv',import.meta.url),'utf8')).find(row=>row.row_id===first);
  expect(canonical).toBeTruthy();
  const headers=await page.locator('#table-head th').allTextContents();
  const baseIndex=headers.indexOf('Base / denominator');expect(baseIndex).toBeGreaterThan(-1);
  const before=await page.locator('#table-body tr').first().locator('td').nth(baseIndex).innerText();
  expect(before).toBe(canonical.denominator);
  await page.locator('#filter-category').selectOption(canonical.category);
  await page.locator('#apply-filters').click();await loaded(page);
  await expect(page.locator('#table-body tr')).toHaveCount(1);
  await expect(page.locator('#table-body tr')).toHaveAttribute('data-row-id',first);
  await expect(page.locator('#table-body tr')).toHaveAttribute('data-value',canonical.value);
  expect(await page.locator('#table-body tr td').nth(baseIndex).innerText()).toBe(before);
});

for(const [name,dataset,width]of [['default desktop','population_composition',1440],['rate ratios','institutional_count_associations',1440],['narrow layout','content_observed',390]]) {
  test(`axe WCAG A/AA checks: ${name}`,async({page})=>{
    await page.setViewportSize({width,height:1000});await openView(page,dataset);
    const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
    const small=await page.locator('main').evaluate(root=>[...root.querySelectorAll('*')].filter(el=>el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden'&&el.childNodes.length&&[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).filter(el=>parseFloat(getComputedStyle(el).fontSize)<12).map(el=>({tag:el.tagName,text:el.textContent.slice(0,50),font:getComputedStyle(el).fontSize})));
    expect(small).toEqual([]);
  });
}
