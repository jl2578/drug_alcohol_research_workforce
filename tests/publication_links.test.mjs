// SPDX-License-Identifier: MIT
// Serve only this curated repository on loopback at the GitHub Pages project prefix.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {readFile, stat} from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';
import {createDataClient, validateQuery} from '../dashboard/assets/data-client.mjs';

const repo = fileURLToPath(new URL('../', import.meta.url));
const prefix = '/drug_alcohol_research_workforce/';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const readJSON = async rel => JSON.parse(await readFile(path.join(repo, rel), 'utf8'));

async function localServer() {
  const server = http.createServer(async (request, response) => {
    try {
      const name = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
      if (!name.startsWith(prefix)) { response.writeHead(404).end(); return; }
      const target = path.resolve(repo, name.slice(prefix.length));
      const relative = path.relative(repo, target);
      if (relative.startsWith('..') || path.isAbsolute(relative) || !(await stat(target)).isFile()) {
        response.writeHead(404).end(); return;
      }
      const mime = {'.json':'application/json', '.csv':'text/csv', '.mjs':'text/javascript', '.pdf':'application/pdf', '.zip':'application/zip'};
      response.writeHead(200, {'Content-Type':mime[path.extname(target)] ?? 'application/octet-stream'});
      createReadStream(target).pipe(response);
    } catch { response.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}${prefix}`;
  return {base, close: () => new Promise(resolve => server.close(resolve))};
}

test('every generated file, download and frozen supplement resolves at the project prefix', async () => {
  const server = await localServer();
  try {
    const build = await readJSON('dashboard/metadata/build.json');
    let checked = 0;
    for (const [rel, digest] of Object.entries(build.files)) {
      const response = await fetch(new URL('dashboard/' + rel, server.base));
      assert.equal(response.status,200,rel);
      assert.equal(sha(Buffer.from(await response.arrayBuffer())),digest,rel);
      checked++;
    }
    const protectedFiles = await readJSON('docs/preserved_components.sha256.json');
    for (const rel of ['training_workforce_evidence/supplement/Supplement_S1_S4.pdf','training_workforce_evidence/supplement/Supplement_S1_S4.docx']) {
      const response = await fetch(new URL(rel,server.base));
      assert.equal(response.status,200,rel);
      assert.equal(sha(Buffer.from(await response.arrayBuffer())),protectedFiles[rel],rel);
    }
    assert.equal((await fetch(new URL('/dashboard/metadata/index.json',server.base))).status,404,
      'A root-relative URL must not accidentally pass the project-prefix test');
    console.log(JSON.stringify({project_prefix:prefix,generated_http_files_checked:checked,frozen_supplements_checked:2}));
  } finally { await server.close(); }
});

test('HTTP-loaded browser rows and full CSV agree for all 26 datasets', async () => {
  const server = await localServer();
  try {
    const index = await readJSON('dashboard/metadata/index.json');
    let rows = 0;
    for (const [dataset, entry] of Object.entries(index.datasets)) {
      // New client per view ensures no unrelated dataset must be loaded first.
      const client = createDataClient(new URL('dashboard/',server.base));
      const result = await client.load(dataset, {}, {includeUnsupported:true});
      const csv = await (await fetch(new URL('dashboard/' + entry.csv,server.base))).text();
      assert.equal(result.csv(),csv,dataset);
      assert.equal(result.rows.length,entry.row_count,dataset);
      rows += result.rows.length;
    }
    assert.equal(rows,130103);
    console.log(JSON.stringify({http_datasets_checked:26,exact_csv_browser_rows_checked:rows,rendered_interface_tested_separately:true}));
  } finally { await server.close(); }
});

test('real shared URLs reject unknown and unsupported selections across every dataset', async () => {
  const index = await readJSON('dashboard/metadata/index.json');
  let unsupportedPairs = 0;
  for (const [dataset, entry] of Object.entries(index.datasets)) {
    const spec = await readJSON('dashboard/' + entry.filters);
    for (const query of [`?dataset=${dataset}&__proto__=x`, `?dataset=${dataset}&renormalize_to_selection=true`, `?dataset=${dataset}&dataset=${dataset}`])
      assert.throws(() => validateQuery(spec,query), undefined, dataset + query);
    // One fully specified actual tuple must survive an encoded URL round trip.
    const params = new URLSearchParams({dataset});
    spec.fields.forEach((field,i) => { const v=spec.domains[field][spec.tuples[0][i]]; if (typeof v==='string') params.append(field,v); });
    assert.ok(validateQuery(spec,params.toString()).matching_tuple_count > 0,dataset);
    // Find a missing pair of levels without asserting that a full-domain lookup must have one.
    outer: for (let a=0; a<spec.fields.length; a++) for (let b=a+1; b<spec.fields.length; b++) {
      const observed = new Set(spec.tuples.map(tuple => `${tuple[a]}|${tuple[b]}`));
      for (let ai=0; ai<spec.domains[spec.fields[a]].length; ai++) for (let bi=0; bi<spec.domains[spec.fields[b]].length; bi++) {
        const av=spec.domains[spec.fields[a]][ai], bv=spec.domains[spec.fields[b]][bi];
        if (typeof av==='string' && typeof bv==='string' && !observed.has(`${ai}|${bi}`)) {
          assert.throws(() => validateQuery(spec,new URLSearchParams({dataset,[spec.fields[a]]:av,[spec.fields[b]]:bv}).toString()));
          unsupportedPairs++; break outer;
        }
      }
    }
  }
  const employment = await readJSON('dashboard/metadata/filters/employment_occupations.json');
  assert.deepEqual(validateQuery(employment,'?dataset=employment_occupations&soc_unit_code'),
                   validateQuery(employment,'?dataset=employment_occupations&soc_unit_code='));
  assert.ok(unsupportedPairs > 0);
  console.log(JSON.stringify({dataset_url_guards_checked:26,missing_real_tuple_pairs_rejected:unsupportedPairs}));
});
