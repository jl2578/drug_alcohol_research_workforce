// SPDX-License-Identifier: MIT
// Static-data client. It never runs ProQuest retrieval, model calls or scoring.
function require(ok, message) { if (!ok) throw new Error(message); }

// The released tuple specification is immutable. Build its inverted index once,
// rather than reconstructing every row for every selector on every change.
const tupleIndexes = new WeakMap();
function tupleIndex(spec) {
  if (tupleIndexes.has(spec)) return tupleIndexes.get(spec);
  const fields = new Map(spec.fields.map((field, column) => [field, {
    column, values:new Map(spec.domains[field].map((value, i) => [value, i])),
    postings:spec.domains[field].map(() => []),
  }]));
  spec.tuples.forEach((tuple, row) => {
    for (const entry of fields.values()) entry.postings[tuple[entry.column]].push(row);
  });
  const index = {fields, all:spec.tuples.map((_, i) => i)};
  tupleIndexes.set(spec,index);
  return index;
}
function normalizeSelection(spec, selection) {
  const index = tupleIndex(spec);
  const filters = Object.create(null), virtual = Object.create(null);
  for (const [rawKey, rawValues] of Object.entries(selection)) {
    const key = Object.hasOwn(spec.aliases, rawKey) ? spec.aliases[rawKey] : rawKey;
    require(!Object.hasOwn(filters, key) && !Object.hasOwn(virtual, key), `Duplicate/aliased selector: ${key}`);
    const values = [...new Set(Array.isArray(rawValues) ? rawValues : [rawValues])];
    require(values.length && values.every(v => typeof v === 'string'), 'Selectors require nonempty lists of strings');
    if (Object.hasOwn(spec.virtual_filters, key)) {
      require(values.length === 1 && spec.virtual_filters[key].values.includes(values[0]), `Invalid virtual selector: ${key}`);
      virtual[key] = values[0];
    } else {
      require(index.fields.has(key), `Unknown or forbidden selector: ${key}`);
      require(values.every(v => index.fields.get(key).values.has(v)), `Unknown selector value: ${key}`);
      filters[key] = values;
    }
  }
  return {filters, virtual};
}
function matchingRows(spec, filters) {
  const index = tupleIndex(spec);
  const constraints = Object.entries(filters).map(([key, values]) => {
    const entry = index.fields.get(key);
    return new Set(values.flatMap(value => entry.postings[entry.values.get(value)]));
  }).sort((a,b) => a.size-b.size);
  if (!constraints.length) return index.all;
  const remaining = constraints.slice(1);
  return [...constraints[0]].filter(row => remaining.every(set => set.has(row)));
}
function checkWitnesses(spec, filters, matches) {
  require(matches.length > 0, 'Unsupported combination');
  const index = tupleIndex(spec);
  for (const [key, values] of Object.entries(filters)) {
    const entry = index.fields.get(key), seen = new Set(matches.map(i => spec.tuples[i][entry.column]));
    require(values.every(v => seen.has(entry.values.get(v))), `Unsupported value within combination: ${key}`);
  }
}
export function validateSelection(spec, selection = {}) {
  const {filters, virtual} = normalizeSelection(spec,selection);
  const matches = matchingRows(spec,filters);
  checkWitnesses(spec,filters,matches);
  return {filters, virtual, matching_tuple_count: matches.length};
}

export function validateQuery(spec, query) {
  const params = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
  require(params.getAll('dataset').length === 1 && params.get('dataset') === spec.dataset_id, 'URL must identify exactly one dataset');
  params.delete('dataset');
  const values = Object.create(null);
  for (const [k, v] of params) (values[k] ??= []).push(v);
  return validateSelection(spec, values);
}

export function availableOptions(spec, selection = {}, field) {
  require(spec.fields.includes(field), 'Unknown filter');
  const rest = Object.fromEntries(Object.entries(selection).filter(([k]) => (Object.hasOwn(spec.aliases,k) ? spec.aliases[k] : k) !== field));
  const normalized = normalizeSelection(spec,rest).filters, matches = matchingRows(spec,normalized);
  checkWitnesses(spec,normalized,matches);
  const index = tupleIndex(spec), witnesses = new Map(), col = index.fields.get(field).column;
  const constraints = Object.entries(normalized).map(([key,values]) => {
    const entry = index.fields.get(key);
    return {column:entry.column, values:values.map(value => entry.values.get(value))};
  });
  for (const row of matches) {
    const tuple = spec.tuples[row], candidate = tuple[col];
    if (!witnesses.has(candidate)) witnesses.set(candidate,constraints.map(() => new Set()));
    constraints.forEach((entry,i) => witnesses.get(candidate)[i].add(tuple[entry.column]));
  }
  return spec.domains[field].filter((value,i) => typeof value === 'string' && witnesses.has(i) &&
    constraints.every((entry,j) => entry.values.every(v => witnesses.get(i)[j].has(v))));
}

export function toCSV(rows, fields) {
  const cell = v => { const s = v == null ? '' : String(v); return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s; };
  return [fields.map(cell).join(','), ...rows.map(r => fields.map(f => cell(r[f])).join(','))].join('\n') + '\n';
}

export function decodeShard(part, columns) {
  return part.rows.map(values => Object.fromEntries(columns.map((field, i) => [field,
    Object.hasOwn(part.dictionaries, String(i)) && values[i] !== null ? part.dictionaries[String(i)][values[i]] : values[i]])));
}

export class NetworkError extends Error {
  constructor(path, {status=null, attempts=1, cause} = {}) {
    super(`Could not load ${path}${status ? ` (HTTP ${status})` : ''} after ${attempts} attempt${attempts === 1 ? '' : 's'}`, {cause});
    this.name = 'NetworkError';
    this.path = path; this.status = status; this.attempts = attempts;
  }
}

export function createDataClient(baseURL, fetcher = globalThis.fetch, {retryAttempts=3, retryDelayMs=150, timeoutMs=10000} = {}) {
  require(Number.isInteger(retryAttempts) && retryAttempts >= 1 && retryAttempts <= 5, 'Retries must allow 1–5 attempts');
  require(Number.isFinite(retryDelayMs) && retryDelayMs >= 0 && Number.isFinite(timeoutMs) && timeoutMs > 0, 'Invalid request timing');
  const base = new URL(baseURL, globalThis.location?.href ?? import.meta.url);
  const cache = new Map();
  async function request(path,url) {
    for (let attempt=1; attempt<=retryAttempts; attempt++) {
      const controller = new AbortController();
      let timer, status=null;
      try {
        const response = await Promise.race([
          (async () => {
            const response = await fetcher(url,{signal:controller.signal});
            status = response.status;
            if (!response.ok) throw new Error(`HTTP ${status}`);
            return await response.json();
          })(),
          new Promise((_,reject) => {timer=setTimeout(() => {
            controller.abort(); reject(new Error('Request timed out'));
          },timeoutMs);}),
        ]);
        return response;
      } catch (cause) {
        // A successful header followed by a truncated/failed body is retryable too.
        const transient = status == null || status < 400 || status === 408 || status === 429 || status >= 500;
        if (attempt === retryAttempts || !transient) throw new NetworkError(path,{status,attempts:attempt,cause});
      } finally {clearTimeout(timer);}
      if (retryDelayMs) await new Promise(resolve => setTimeout(resolve,retryDelayMs * attempt));
    }
  }
  async function read(path) {
    require(!path.startsWith('/') && !path.includes('..'), 'Unsafe data path');
    const url = new URL(path, base).href;
    if (!cache.has(url)) cache.set(url, request(path,url).catch(error => { cache.delete(url); throw error; }));
    return cache.get(url);
  }
  async function load(dataset, selection = {}, {includeUnsupported = false} = {}) {
    const index = await read('metadata/index.json');
    require(Object.hasOwn(index.datasets, dataset), 'Unknown or deferred dataset');
    const entry = index.datasets[dataset];
    const spec = await read(entry.filters);
    const validated = typeof selection === 'string' ? validateQuery(spec, selection) : validateSelection(spec, selection);
    const manifest = await read(entry.json);
    const parts = manifest.shards.filter(part => Object.entries(validated.filters).every(([k, values]) =>
      !Object.hasOwn(part.filter_values, k) || values.some(v => part.filter_values[k].includes(v))));
    const loaded = await Promise.all(parts.map(part => read(part.path)));
    const rows = loaded.flatMap(part => decodeShard(part, manifest.columns))
      .filter(r => Object.entries(validated.filters).every(([k, values]) => values.includes(r[k])) && (includeUnsupported || r.support_status !== 'unsupported'));
    // Filtering never rescales values, recomputes denominators or calculates contrasts.
    const activeFields = Object.assign({}, ...Object.entries(spec.virtual_filters).map(([key, config]) =>
      config.bindings?.[validated.virtual[key] ?? config.default] ?? {}));
    const measure = row => ({value: row.value, lower: row[activeFields.lower ?? 'lower'],
      upper: row[activeFields.upper ?? 'upper'], interval_family: validated.virtual.interval_family ?? spec.virtual_filters.interval_family?.default ?? null,
      interval_status: activeFields.lower ? (row[activeFields.lower] != null && row[activeFields.upper] != null ? 'available' : 'unavailable') : row.interval_status});
    return {rows, fields: manifest.columns, selection: validated, manifest, activeFields, measure,
            csv: () => toCSV(rows, manifest.columns)};
  }
  return {index: () => read('metadata/index.json'), load,
          metadata: async dataset => { const i = await read('metadata/index.json'); require(Object.hasOwn(i.datasets,dataset),'Unknown dataset'); return read(i.datasets[dataset].manifest); },
          filters: async dataset => { const i = await read('metadata/index.json'); require(Object.hasOwn(i.datasets, dataset), 'Unknown dataset'); return read(i.datasets[dataset].filters); }};
}
