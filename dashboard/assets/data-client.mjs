// SPDX-License-Identifier: MIT
// Static-data client. It never runs ProQuest retrieval, model calls or scoring.
function require(ok, message) { if (!ok) throw new Error(message); }

export function validateSelection(spec, selection = {}) {
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
      require(spec.fields.includes(key), `Unknown or forbidden selector: ${key}`);
      require(values.every(v => spec.domains[key].includes(v)), `Unknown selector value: ${key}`);
      filters[key] = values;
    }
  }
  const matches = spec.tuples.map(t => Object.fromEntries(spec.fields.map((f, i) => [f, spec.domains[f][t[i]]])))
    .filter(r => Object.entries(filters).every(([k, vs]) => vs.includes(r[k])));
  require(matches.length > 0, 'Unsupported combination');
  for (const [key, values] of Object.entries(filters))
    require(values.every(v => matches.some(r => r[key] === v)), `Unsupported value within combination: ${key}`);
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
  const rest = Object.fromEntries(Object.entries(selection).filter(([k]) => (spec.aliases[k] ?? k) !== field));
  const normalized = validateSelection(spec, rest).filters;
  const witnesses = new Map(), col = spec.fields.indexOf(field);
  for (const tuple of spec.tuples) {
    const row = Object.fromEntries(spec.fields.map((f, i) => [f, spec.domains[f][tuple[i]]]));
    if (!Object.entries(normalized).every(([k, vs]) => vs.includes(row[k]))) continue;
    const candidate = spec.domains[field][tuple[col]];
    if (!witnesses.has(candidate)) witnesses.set(candidate, new Map(Object.keys(normalized).map(k => [k, new Set()])));
    for (const key of Object.keys(normalized)) witnesses.get(candidate).get(key).add(row[key]);
  }
  return spec.domains[field].filter(v => typeof v === 'string' && witnesses.has(v) &&
    Object.entries(normalized).every(([k, values]) => values.every(value => witnesses.get(v).get(k).has(value))));
}

export function toCSV(rows, fields) {
  const cell = v => { const s = v == null ? '' : String(v); return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s; };
  return [fields.map(cell).join(','), ...rows.map(r => fields.map(f => cell(r[f])).join(','))].join('\n') + '\n';
}

export function decodeShard(part, columns) {
  return part.rows.map(values => Object.fromEntries(columns.map((field, i) => [field,
    Object.hasOwn(part.dictionaries, String(i)) && values[i] !== null ? part.dictionaries[String(i)][values[i]] : values[i]])));
}

export function createDataClient(baseURL, fetcher = globalThis.fetch) {
  const base = new URL(baseURL, globalThis.location?.href ?? import.meta.url);
  const cache = new Map();
  async function read(path) {
    require(!path.startsWith('/') && !path.includes('..'), 'Unsafe data path');
    const url = new URL(path, base).href;
    if (!cache.has(url)) cache.set(url, (async () => {
      const response = await fetcher(url);
      require(response.ok, `Cannot load ${path}: ${response.status}`);
      return response.json();
    })().catch(error => { cache.delete(url); throw error; }));
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
          filters: async dataset => { const i = await read('metadata/index.json'); require(Object.hasOwn(i.datasets, dataset), 'Unknown dataset'); return read(i.datasets[dataset].filters); }};
}
