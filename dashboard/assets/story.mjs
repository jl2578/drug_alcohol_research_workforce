// SPDX-License-Identifier: MIT
// Plain-language front pages. They read the released datasets and verbatim source tables;
// they never refit, reweight or rebase an estimate. The full explorer is explore.html.
import {createDataClient} from './data-client.mjs';
import {VALUE_LABELS} from './view-specs.mjs';

const client = createDataClient(new URL('./', location.href));
const OUTCOMES = [['C3', 'Study design'], ['C4', 'Level of analysis'], ['C5', 'Research objective'], ['C8', 'Data type']];
const DEGREE = {Masters: 'Master’s', "Master's": 'Master’s', 'Research doctorate': 'Research doctorate', DrPH: 'DrPH', PsyD: 'PsyD'};
const DEGREE_ORDER = ['Masters', 'Research doctorate', 'PsyD', 'DrPH'];
const ROLE_STATES = ['research_likely_only', 'both', 'clinical_likely_only', 'neither', 'unclassifiable', 'unscored'];
const ROLE = {research_likely_only: ['Research only', '#256abf', '#ffffff'], both: ['Both research and clinical care', '#1baf7a'],
  clinical_likely_only: ['Clinical care only', '#eb6834'], neither: ['Neither', '#b5b3aa'],
  unclassifiable: ['Insufficient information (U)', '#d6d4cc'], unscored: ['Not scored', '#ebe9e2']};
const EMPLOYMENT = 'DEP4/rc_rmi/evidence/employment/outside_university_20261016/';

// ---------- small helpers ----------
function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'style') node.style.cssText = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  node.append(...kids.flat(Infinity).filter(kid => kid != null && kid !== false));
  return node;
}
const num = value => value == null || value === '' ? null : Number(value);
const round1 = x => Math.round(x * 10) / 10;
const f1 = x => Math.abs(round1(x)).toFixed(1);
const plain = x => (round1(x) < 0 ? '−' : '') + f1(x);
const signed = x => (round1(x) > 0 ? '+' : round1(x) < 0 ? '−' : '') + f1(x);
const whole = x => Number(x).toLocaleString('en-US');
const share = (n, d) => 100 * n / d;
const joinWords = xs => xs.length > 1 ? xs.slice(0, -1).join(', ') + ' and ' + xs.at(-1) : xs[0];
const groupBy = (xs, key) => xs.reduce((map, x) => map.set(key(x), [...(map.get(key(x)) ?? []), x]), new Map());

// Redraws a region; keeps the old content while loading and offers a retry on failure.
async function panel(box, render) {
  const token = (box.drawToken = (box.drawToken ?? 0) + 1);
  box.setAttribute('aria-busy', 'true');
  try {
    const nodes = [await render()].flat();
    if (box.drawToken === token) box.replaceChildren(...nodes);
  } catch (error) {
    console.error(error);
    if (box.drawToken === token) box.replaceChildren(el('div', {class: 'error', role: 'alert'},
      el('span', {}, 'These numbers could not be loaded. Check the connection or the preview server, then try again.'),
      el('button', {type: 'button', onclick: () => panel(box, render)}, 'Try again')));
  } finally {
    if (box.drawToken === token) box.removeAttribute('aria-busy');
  }
}

// Segmented buttons sit outside redrawn regions so keyboard focus survives a redraw.
function segmented(label, options, value, onChange) {
  const id = 'control-' + Math.random().toString(36).slice(2, 9);
  const group = el('div', {class: 'segmented', role: 'group', 'aria-labelledby': id});
  for (const [optionValue, text] of options) {
    const button = el('button', {type: 'button', 'aria-pressed': String(optionValue === value)}, text);
    button.addEventListener('click', () => {
      for (const other of group.children) other.setAttribute('aria-pressed', String(other === button));
      onChange(optionValue);
    });
    group.append(button);
  }
  return el('div', {class: 'control'}, el('span', {class: 'control-label', id}, label), group);
}

const tag = (kind, code, label, count, title) => el('span', {class: kind === 'soc' ? 'tag soc' : 'tag', title},
  el('span', {class: 'code'}, code), label ? el('span', {}, label) : null, count != null ? el('span', {class: 'count'}, '· ' + count) : null);

function barRows(items) {
  return el('div', {class: 'rows plain'}, items.map(item => el('div', {class: 'row', title: item.title},
    el('div', {class: 'row-label'},
      el('span', {class: 'name'}, item.code ? tag(item.kind, item.code) : null, el('span', {}, item.label)),
      item.sub ? el('span', {class: 'small'}, item.sub) : null),
    el('div', {class: 'row-plot'},
      el('div', {class: 'track'}, el('div', {class: 'bar', style: `width:${(100 * item.frac).toFixed(2)}%;background:${item.color ?? 'var(--blue)'}`})),
      el('span', {class: 'value'}, item.value)),
    item.tags?.length ? el('div', {class: 'tags'}, item.tags) : null)));
}

function axisRow(ticks, valueHeader) {
  return el('div', {class: 'axis', 'aria-hidden': 'true'}, el('div', {class: 'row-label'}, '.'),
    el('div', {class: 'row-plot'}, el('div', {class: 'track'}, ticks.map(t => el('span', {class: 'tick', style: `left:${t.x}%`}, t.label))),
      el('span', {class: 'value'}, valueHeader)));
}

function numbersTable(head, rows) {
  return el('details', {class: 'numbers'}, el('summary', {}, 'Show numbers'),
    el('div', {class: 'table-wrap'}, el('table', {},
      el('thead', {}, el('tr', {}, head.map(h => el('th', {scope: 'col'}, h)))),
      el('tbody', {}, rows.map(r => el('tr', {}, r.map((cell, i) => i === 0 ? el('th', {scope: 'row'}, cell) : el('td', {}, cell))))))));
}

const roleLegend = () => el('ul', {class: 'legend', 'aria-label': 'Role legend'},
  ROLE_STATES.map(s => el('li', {}, el('span', {class: 'swatch', style: `background:${ROLE[s][1]}`}), ROLE[s][0])));

// groups: [{label, N, states: {state: [count, percent]}}]
function roleStacks(groups) {
  const rows = groups.map(group => {
    const parts = ROLE_STATES.map(s => [s, ...(group.states[s] ?? [0, 0])]);
    const summary = parts.filter(p => p[2] > 0).map(([s, , p]) => `${ROLE[s][0]} ${f1(p)}%`).join(', ');
    return el('div', {class: 'row'},
      el('div', {class: 'row-label'}, el('span', {}, group.label),
        el('span', {class: 'small'}, `n = ${whole(group.N)}${group.N < 30 ? ' · small sample' : ''}`)),
      el('div', {class: 'stack', role: 'img', 'aria-label': `${group.label}, ${whole(group.N)} authors: ${summary}`},
        parts.map(([s, n, p]) => el('div', {class: 'seg', title: `${ROLE[s][0]}: ${f1(p)}% (${whole(n)} of ${whole(group.N)})`,
          style: `width:${p.toFixed(2)}%;background:${ROLE[s][1]};color:${ROLE[s][2] ?? 'var(--ink)'}`}, p >= 7 ? Math.round(p) + '%' : ''))));
  });
  const table = numbersTable(['Group', 'n', ...ROLE_STATES.map(s => ROLE[s][0])],
    groups.map(g => [g.label, whole(g.N), ...ROLE_STATES.map(s => g.states[s] ? `${f1(g.states[s][1])}% (${whole(g.states[s][0])})` : '0.0% (0)')]));
  return [el('div', {class: 'rows'}, rows), table];
}
const stateRows = (rows, key) => Object.fromEntries(rows.map(r => [r[key], [num(r.numerator) ?? 0, num(r.value) ?? 0]]));

// Verbatim restored source tables (CSV) for the few facts no dataset carries.
const sourceCache = new Map();
async function fetchWithRetry(path) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const response = await fetch(new URL(path, new URL('./', location.href)));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.text();
    } catch (error) { lastError = error; await new Promise(resolve => setTimeout(resolve, 150 * attempt)); }
  }
  throw lastError;
}
function parseCSV(text) {
  const rows = []; let row = [], value = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { if (quoted && text[i + 1] === '"') { value += '"'; i++; } else quoted = !quoted; }
    else if (c === ',' && !quoted) { row.push(value); value = ''; }
    else if (c === '\n' && !quoted) { row.push(value.replace(/\r$/, '')); rows.push(row); row = []; value = ''; }
    else value += c;
  }
  if (value || row.length) { row.push(value); rows.push(row); }
  const [head, ...body] = rows;
  return body.filter(r => r.length === head.length).map(r => Object.fromEntries(head.map((h, i) => [h.replace(/^﻿/, ''), r[i]])));
}
function sourceTable(table) {
  if (!sourceCache.has(table)) sourceCache.set(table, (async () => {
    const exports = JSON.parse(await fetchWithRetry('metadata/source_exports.json'));
    if (!exports[table]) throw new Error('Unknown source table ' + table);
    return parseCSV(await fetchWithRetry(exports[table].path));
  })().catch(error => { sourceCache.delete(table); throw error; }));
  return sourceCache.get(table);
}

// ---------- Overview ----------
async function overview() {
  await panel(document.getElementById('findings'), async () => {
    const [reach, roles] = await Promise.all([
      client.load('funding_reach', {ownership: ['full'], connection_definition: ['combined_clear'], institute: ['NIDA/NIAAA']}),
      client.load('employment_roles', {degree_group: ['PhD/ScD and equivalent'], specification: ['inclusive'], basis: ['observed']})]);
    const r = Object.fromEntries(reach.rows.map(x => [x.population, x]));
    const rd = r['Research doctorate'], ma = r.Masters;
    const st = stateRows(roles.rows, 'joint_state'), N = num(roles.rows[0].denominator);
    const research = st.research_likely_only[0] + st.both[0];
    const card = (href, kicker, headline, detail, more) => el('a', {class: 'finding', href},
      el('span', {class: 'kicker'}, kicker), el('span', {class: 'headline'}, headline), el('span', {class: 'detail'}, detail), el('span', {class: 'more'}, more));
    return [
      card('content.html', 'Research content', 'Compare any two groups',
        'Study design, level of analysis, research objective and data type across 16 degree–field groups, two completion periods and 50 institutions.', 'Explore content →'),
      card('funding.html', 'NIH connections', `${Math.round(num(rd.value))}% of research-doctorate works had an identified NIDA/NIAAA connection`,
        `${whole(rd.numerator)} of ${whole(rd.denominator)} research-doctorate works, compared with ${Math.round(num(ma.value))}% of master’s works (${whole(ma.numerator)} of ${whole(ma.denominator)}).`, 'See funding links →'),
      card('careers.html', 'Careers', `${Math.round(share(research, N))}% of sampled research-doctorate authors held jobs that suggest research`,
        `${whole(research)} of ${whole(N)} authors with observed employment, including ${whole(st.both[0])} whose jobs suggest both research and clinical care.`, 'See careers →')];
  });

  const box = document.getElementById('composition');
  let by = 'degree';
  document.getElementById('composition-controls').append(segmented('Group works by', [['degree', 'By degree'], ['field', 'By field']], by, value => { by = value; draw(); }));
  const draw = () => panel(box, async () => {
    const rows = (await client.load('population_composition')).rows;
    const total = num(rows[0].denominator);
    const key = by === 'degree' ? r => r.degree_group : r => r.field_label;
    const sums = [...groupBy(rows, key)].map(([label, rs]) => [label, rs.reduce((s, r) => s + num(r.numerator), 0)]).sort((a, b) => b[1] - a[1]);
    const max = sums[0][1];
    const rd = sums.find(s => s[0] === 'Research doctorate'), ma = sums.find(s => s[0] === "Master's");
    document.getElementById('composition-lead').textContent = rd && ma
      ? `Research doctorates make up ${Math.round(share(rd[1], total))}% of the ${whole(total)} works; master’s theses ${Math.round(share(ma[1], total))}%.` : '';
    return barRows(sums.map(([label, n]) => ({label: label.replace("Master's", 'Master’s'), frac: n / max, value: `${whole(n)} · ${f1(share(n, total))}%`,
      title: `${label}: ${whole(n)} works (${f1(share(n, total))}%)`})));
  });
  draw();
}

// ---------- Research content ----------
async function content() {
  const box = document.getElementById('content-chart');
  const controls = document.getElementById('content-controls');
  const state = {pick: 'pair:Masters|BF01>Research doctorate|BF01', outcome: 'C3'};
  let groupLabel = g => g, fieldName = f => f;

  await panel(controls, async () => {
    const [fitSpec, instSpec, pop] = await Promise.all([client.filters('content_fitted'), client.filters('institution_profiles'), client.load('population_composition')]);
    const fields = Object.fromEntries(pop.rows.map(r => [r.field_code, r.field_label]));
    fieldName = f => fields[f] ?? f;
    groupLabel = g => { const [d, f] = g.split('|'); return `${DEGREE[d] ?? d} · ${fieldName(f)}`; };
    const groups = fitSpec.domains.group_id.filter(g => typeof g === 'string');
    const degreeRank = g => DEGREE_ORDER.indexOf(g.split('|')[0]);
    const pairs = gs => gs.flatMap((a, i) => gs.slice(i + 1).map(b => [a, b]));
    const byField = [...groupBy(groups, g => g.split('|')[1])].sort((a, b) => a[0].localeCompare(b[0]));
    const degreePairs = byField.flatMap(([, gs]) => pairs([...gs].sort((a, b) => degreeRank(a) - degreeRank(b))));
    const rdPairs = pairs(groups.filter(g => g.startsWith('Research doctorate|')).sort());
    const periodGroups = [...groups].sort((a, b) => degreeRank(a) - degreeRank(b) || a.localeCompare(b));
    const institutions = instSpec.domains.institution_id.filter(i => typeof i === 'string')
      .map(id => [id, VALUE_LABELS.institution_id?.[id] ?? id]).sort((a, b) => a[1].localeCompare(b[1]));
    const optgroup = (label, items) => el('optgroup', {label}, items.map(([value, text]) => el('option', {value, selected: value === state.pick}, text)));
    const select = el('select', {id: 'compare', class: 'select'},
      optgroup('Degrees within a field', degreePairs.map(([a, b]) => [`pair:${a}>${b}`, `${fieldName(a.split('|')[1])}: ${DEGREE[a.split('|')[0]] ?? a.split('|')[0]} vs ${DEGREE[b.split('|')[0]] ?? b.split('|')[0]}`])),
      optgroup('Fields among research doctorates', rdPairs.map(([a, b]) => [`pair:${a}>${b}`, `${fieldName(a.split('|')[1])} vs ${fieldName(b.split('|')[1])}`])),
      optgroup('Earlier vs later period', periodGroups.map(g => [`period:${g}`, `${groupLabel(g)}: 2017–2023 vs 2010–2016`])),
      optgroup('An institution vs the 50-institution average', institutions.map(([id, name]) => [`inst:${id}`, name])));
    select.addEventListener('change', () => { state.pick = select.value; draw(); });
    return [el('div', {class: 'control', style: 'flex:1 1 360px'}, el('label', {class: 'control-label', for: 'compare'}, 'Compare'), select),
      segmented('Content dimension', OUTCOMES, state.outcome, value => { state.outcome = value; draw(); })];
  });

  const draw = () => panel(box, async () => {
    const o = state.outcome, outcomeName = OUTCOMES.find(x => x[0] === o)[1].toLowerCase();
    const [kind, key] = [state.pick.slice(0, state.pick.indexOf(':')), state.pick.slice(state.pick.indexOf(':') + 1)];
    const byCategory = rows => new Map(rows.map(r => [r.category, r]));
    const point = r => r ? [num(r.value) * 100, num(r.lower) == null ? null : num(r.lower) * 100, num(r.upper) == null ? null : num(r.upper) * 100] : null;
    const periodN = rows => Object.fromEntries([...groupBy(rows, r => `${r.group_id}|${r.period}`)].map(([k, rs]) => [k, num(rs[0].denominator)]));
    let A, B, D, nameA, nameB, title, nText, note, href, diffHeader = 'Difference, points', categories;
    if (kind === 'pair') {
      const [ga, gb] = key.split('>');
      const [fit, contrasts, observed] = await Promise.all([
        client.load('content_fitted', {outcome: [o], group_id: [ga, gb], family: ['standardized_profile']}),
        client.load('content_fitted_contrasts', {outcome: [o]}),
        client.load('content_observed', {outcome: [o], population: ['primary'], group_id: [ga, gb]})]);
      A = byCategory(fit.rows.filter(r => r.group_id === ga)); B = byCategory(fit.rows.filter(r => r.group_id === gb));
      // Saved contrasts are A minus B as stored; a reversed pair flips the sign and swaps the bounds.
      D = new Map(contrasts.rows.filter(r => (r.group_a === ga && r.group_b === gb) || (r.group_a === gb && r.group_b === ga)).map(r => {
        const v = num(r.value), lo = num(r.lower), hi = num(r.upper), flip = r.group_a !== ga;
        return [r.category, flip ? [-v, hi == null ? null : -hi, lo == null ? null : -lo] : [v, lo, hi]];
      }));
      A = new Map([...A].map(([c, r]) => [c, {row: r, p: point(r)}])); B = new Map([...B].map(([c, r]) => [c, {row: r, p: point(r)}]));
      nameA = groupLabel(ga); nameB = groupLabel(gb); title = `${nameA} vs ${nameB}`;
      const n = periodN(observed.rows), total = g => (n[`${g}|2010-2016`] ?? 0) + (n[`${g}|2017-2023`] ?? 0);
      nText = `Works with this dimension coded: ${nameA} ${whole(total(ga))}; ${nameB} ${whole(total(gb))}.`;
      note = 'Model-based shares that weight 2010–2016 and 2017–2023 equally. Each difference has its own saved paired interval.';
      href = 'data/content_fitted_contrasts.csv';
    } else if (kind === 'period') {
      const [fit, change, observed] = await Promise.all([
        client.load('content_fitted', {outcome: [o], group_id: [key], family: ['early_profile', 'late_profile']}),
        client.load('content_temporal_changes', {outcome: [o], analysis_population: ['primary'], group_id: [key]}),
        client.load('content_observed', {outcome: [o], population: ['primary'], group_id: [key]})]);
      A = new Map(fit.rows.filter(r => r.family === 'late_profile').map(r => [r.category, {row: r, p: point(r)}]));
      B = new Map(fit.rows.filter(r => r.family === 'early_profile').map(r => [r.category, {row: r, p: point(r)}]));
      D = new Map(change.rows.map(r => [r.category, [num(r.value), num(r.lower), num(r.upper)]]));
      nameA = '2017–2023'; nameB = '2010–2016'; title = `${groupLabel(key)}: 2017–2023 vs 2010–2016`; diffHeader = 'Change, points';
      const n = periodN(observed.rows);
      nText = `Works with this dimension coded: ${whole(n[`${key}|2010-2016`] ?? 0)} in 2010–2016 and ${whole(n[`${key}|2017-2023`] ?? 0)} in 2017–2023.`;
      note = 'Model-based shares for each completion period. Each change has its own saved paired interval.';
      href = 'data/content_temporal_changes.csv';
    } else {
      const [inst, bench] = await Promise.all([
        client.load('institution_profiles', {outcome: [o], institution_id: [key]}),
        client.load('institution_benchmark', {outcome: [o]})]);
      A = new Map(inst.rows.map(r => [r.category, {row: r, p: point(r)}]));
      B = new Map(bench.rows.map(r => [r.category, {row: r, p: [num(r.value) * 100, null, null]}]));
      D = new Map([...A].filter(([c]) => B.has(c)).map(([c, a]) => [c, [a.p[0] - B.get(c).p[0], null, null]]));
      const first = inst.rows[0];
      nameA = first.institution_name; nameB = '50-institution average'; title = `${nameA} vs the 50-institution average`;
      nText = `${nameA}: ${whole(num(first.early_eligible_works) + num(first.late_eligible_works))} works with this dimension coded. The average gives each of the 50 institutions equal weight.`;
      note = 'Model-based shares that weight the two periods equally and keep each institution’s degree and field mix, so they are not quality rankings. The average and the difference have no interval.';
      href = 'data/institution_profiles.csv';
    }
    categories = [...A.values()].filter(a => B.has(a.row.category)).sort((x, y) => num(x.row.category_order) - num(y.row.category_order))
      .map(a => ({key: a.row.category, label: a.row.category_label.replace(/\s+/g, ' '), a: a.p, b: B.get(a.row.category).p, d: D.get(a.row.category) ?? [a.p[0] - B.get(a.row.category).p[0], null, null]}));

    const max = Math.max(...categories.flatMap(c => [c.a[0], c.a[2], c.b[0], c.b[2]]).filter(x => x != null));
    const top = [10, 20, 30, 40, 50, 60, 80, 100].find(t => max <= t) ?? 100;
    const x = v => Math.max(0, Math.min(100, 100 * v / top));
    const ticks = [0, 0.5, 1].map(f => ({x: (100 * f).toFixed(2), label: `${f * top}%`}));
    const ci = p => p[1] != null ? ` (${plain(p[1])} to ${plain(p[2])})` : '';
    let withInterval = 0, excluding = 0, best = null;
    const rows = categories.map(c => {
      const hasCI = c.d[1] != null && c.d[2] != null, excludesZero = hasCI && (c.d[1] > 0 || c.d[2] < 0);
      if (hasCI) withInterval++;
      if (excludesZero) excluding++;
      if (!best || Math.abs(c.d[0]) > Math.abs(best.d[0])) best = c;
      const whisker = (p, top, color) => p[1] != null ? el('div', {class: 'whisker', style: `top:${top}px;left:${x(p[1]).toFixed(2)}%;width:${(x(p[2]) - x(p[1])).toFixed(2)}%;background:${color}`}) : null;
      return el('div', {class: 'row', title: `${c.label}: ${nameA} ${f1(c.a[0])}%${ci(c.a)}; ${nameB} ${f1(c.b[0])}%${ci(c.b)}; difference ${signed(c.d[0])} points`},
        el('div', {class: 'row-label'}, c.label),
        el('div', {class: 'row-plot'},
          el('div', {class: 'track', style: 'height:32px'},
            ticks.map(t => el('div', {class: 'gridline', style: `left:${t.x}%`})),
            whisker(c.a, 9, 'var(--blue)'), el('div', {class: 'mark-a', style: `top:4px;left:${x(c.a[0]).toFixed(2)}%`}),
            whisker(c.b, 22, 'var(--orange)'), el('div', {class: 'mark-b', style: `top:18px;left:${x(c.b[0]).toFixed(2)}%`})),
          el('span', {class: excludesZero ? 'value strong' : 'value'}, signed(c.d[0]),
            el('span', {class: 'ci'}, hasCI ? `${plain(c.d[1])} to ${plain(c.d[2])}` : 'no interval'))));
    });
    const lead = best ? `Largest difference in ${outcomeName}: ${best.label}, ${f1(best.a[0])}% for ${nameA} vs ${f1(best.b[0])}% for ${kind === 'inst' ? 'the average' : nameB} (${signed(best.d[0])} points${best.d[1] != null ? `, 95% CI ${plain(best.d[1])} to ${plain(best.d[2])}` : ''}).` : '';
    document.getElementById('content-lead').textContent = lead;
    document.getElementById('content-count').textContent = withInterval
      ? `Intervals exclude zero for ${excluding} of ${rows.length} categories.` : 'Descriptive comparison: no intervals for the average or the differences.';
    return [
      el('div', {class: 'card-head'}, el('h2', {id: 'content-title'}, title),
        el('ul', {class: 'legend'}, el('li', {}, el('span', {class: 'dot-a', 'aria-hidden': 'true'}), nameA), el('li', {}, el('span', {class: 'dot-b', 'aria-hidden': 'true'}), nameB), el('li', {}, 'Lines: 95% intervals'))),
      el('div', {class: 'rows'}, axisRow(ticks, diffHeader), rows),
      o === 'C8' ? el('p', {class: 'note'}, 'Data-type categories can overlap, so a group’s shares can add to more than 100%.') : null,
      el('p', {class: 'note'}, `${note} Bold differences have intervals that exclude zero. ${nText}`),
      numbersTable(['Category', `${nameA} (95% CI)`, `${nameB} (95% CI)`, diffHeader],
        categories.map(c => [c.label, `${f1(c.a[0])}%${ci(c.a)}`, `${f1(c.b[0])}%${ci(c.b)}`, `${signed(c.d[0])}${c.d[1] != null ? ` (${plain(c.d[1])} to ${plain(c.d[2])})` : ''}`])),
      el('p', {class: 'note'}, el('a', {href, download: true}, 'Download the full dataset (CSV)'))];
  });
  draw();
}

// ---------- NIH connections ----------
async function funding() {
  const reachBox = document.getElementById('reach');
  const countsBox = document.getElementById('counts');
  const connectedBox = document.getElementById('connected');
  const reachRows = client.load('funding_reach', {ownership: ['full'], connection_definition: ['combined_clear'], institute: ['NIDA/NIAAA']});
  const countRows = client.load('institutional_count_associations', {ownership: ['full']});

  panel(document.getElementById('funding-lead'), async () => {
    const r = Object.fromEntries((await reachRows).rows.map(x => [x.population, x]));
    const rr = (await countRows).rows.find(x => x.degree_target === 'Research doctorate');
    return [el('p', {class: 'lead'}, `${Math.round(num(r['Research doctorate'].value))}% of research-doctorate works and ${Math.round(num(r.Masters.value))}% of master’s works had an identified connection to NIDA or NIAAA funding through an advisor, committee member or award.`),
      el('p', {class: 'sub'}, `Institutions with more preceding NIDA/NIAAA funding produced more in-scope research-doctorate works: going from one to four funded projects per year was associated with about ${Math.round(100 * (num(rr.value) - 1))}% more works.`)];
  });

  panel(reachBox, async () => {
    const r = Object.fromEntries((await reachRows).rows.map(x => [x.population, x]));
    const order = [['Research doctorate', 'Research doctorate'], ['Masters', 'Master’s'], ['Other credentials', 'Other credentials'], ['All credentials', 'All credentials']];
    return [barRows(order.map(([key, label]) => {
      const x = r[key], p = num(x.value);
      return {label, frac: Math.min(1, p / 50), value: `${f1(p)}% · ${whole(x.numerator)} of ${whole(x.denominator)}`, title: `${label}: ${whole(x.numerator)} of ${whole(x.denominator)} works (${f1(p)}%)`};
    })), el('p', {class: 'note'}, 'Bars run from 0 to 50%. “Other credentials” are PsyD, DrPH, other named doctorates and unresolved credentials. ',
      el('a', {href: 'data/funding_reach.csv', download: true}, 'Download (CSV)'))];
  });

  panel(countsBox, async () => {
    const rows = (await countRows).rows;
    const lo = Math.log(0.7), hi = Math.log(1.6), x = v => 100 * (Math.log(v) - lo) / (hi - lo);
    const ticks = [0.75, 1, 1.25, 1.5].map(v => ({x: x(v).toFixed(2), label: String(v)}));
    const order = [['Research doctorate', 'Research-doctorate works'], ['Masters', 'Master’s works'], ['Masters minus research doctorate', 'Master’s ÷ research doctorate']];
    const fmt3 = v => num(v).toFixed(3);
    const marks = order.map(([key, label]) => {
      const r = rows.find(row => row.degree_target === key), v = num(r.value), l = num(r.lower_pointwise), u = num(r.upper_pointwise);
      return el('div', {class: 'row', title: `${label}: rate ratio ${fmt3(v)} (95% CI ${fmt3(l)} to ${fmt3(u)}); ${whole(r.cluster_count)} institutions`},
        el('div', {class: 'row-label'}, label),
        el('div', {class: 'row-plot'},
          el('div', {class: 'track', style: 'height:24px'}, ticks.map(t => el('div', {class: 'gridline', style: `left:${t.x}%`})),
            el('div', {class: 'refline', style: `left:${x(1).toFixed(2)}%`}),
            el('div', {class: 'whisker', style: `top:11px;left:${x(l).toFixed(2)}%;width:${(x(u) - x(l)).toFixed(2)}%;background:var(--blue)`}),
            el('div', {class: 'mark-a', style: `top:6px;left:${x(v).toFixed(2)}%`})),
          el('span', {class: 'value'}, el('strong', {}, fmt3(v)), ` (${fmt3(l)} to ${fmt3(u)})`)));
    });
    const familywise = order.map(([key, label]) => { const r = rows.find(row => row.degree_target === key); return `${label} ${fmt3(r.lower_familywise)} to ${fmt3(r.upper_familywise)}`; }).join('; ');
    return [el('div', {class: 'rows'}, axisRow(ticks, 'Rate ratio (95% CI)'), marks),
      el('p', {class: 'note'}, `The last row is a ratio of rate ratios, not a difference: below 1 means the master’s association was weaker. Intervals are pointwise; simultaneous intervals for the three estimates: ${familywise}. `,
        el('a', {href: 'data/institutional_count_associations.csv', download: true}, 'Download (CSV)'))];
  });

  const state = {degree: 'Research doctorate', outcome: 'C3'};
  document.getElementById('connected-controls').append(
    segmented('Degree', [['Research doctorate', 'Research doctorate'], ['Masters', 'Master’s']], state.degree, value => { state.degree = value; draw(); }),
    segmented('Content dimension', OUTCOMES, state.outcome, value => { state.outcome = value; draw(); }));
  const draw = () => panel(connectedBox, async () => {
    const filters = {connection_definition: ['primary_combined'], ownership: ['full'], degree_target: [state.degree], outcome: [state.outcome]};
    const [profiles, contrasts] = await Promise.all([client.load('funding_content_profiles', filters), client.load('funding_content_contrasts', filters)]);
    const diff = new Map(contrasts.rows.map(r => [r.category, num(r.value)]));
    const cats = [...groupBy(profiles.rows, r => r.category)].map(([category, rs]) => {
      const side = Object.fromEntries(rs.map(r => [r.connection_status, r]));
      return {category, label: side.connected.category_label.replace(/\s+/g, ' '), order: num(side.connected.category_order), connected: side.connected, remaining: side.remaining, d: diff.get(category)};
    }).filter(c => c.d != null).sort((a, b) => a.order - b.order);
    const max = Math.max(...cats.map(c => Math.abs(c.d)));
    const D = [5, 10, 15, 20, 25, 30, 40, 50].find(t => max <= t) ?? 50;
    const ticks = [-D, 0, D].map(v => ({x: (50 + 50 * v / D).toFixed(2), label: `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)} pts`}));
    const best = cats.reduce((a, b) => Math.abs(b.d) > Math.abs(a.d) ? b : a, cats[0]);
    const degreeWord = state.degree === 'Research doctorate' ? 'research-doctorate' : 'master’s';
    document.getElementById('connected-lead').textContent = `For ${degreeWord} works, the largest gap is in ${best.label}: ${f1(num(best.connected.value))}% of connected vs ${f1(num(best.remaining.value))}% of remaining works (${signed(best.d)} points).`;
    const rows = cats.map(c => {
      const w = 50 * Math.abs(c.d) / D, cv = num(c.connected.value), rv = num(c.remaining.value);
      return el('div', {class: 'row', title: `${c.label}: connected ${f1(cv)}% (${whole(c.connected.numerator)} of ${whole(c.connected.denominator)}), remaining ${f1(rv)}% (${whole(c.remaining.numerator)} of ${whole(c.remaining.denominator)})`},
        el('div', {class: 'row-label'}, c.label),
        el('div', {class: 'row-plot'},
          el('div', {class: 'track', style: 'height:22px'}, el('div', {class: 'zero', style: 'left:50%'}),
            el('div', {style: `position:absolute;top:4px;height:14px;border-radius:2px;left:${(c.d >= 0 ? 50 : 50 - w).toFixed(2)}%;width:${Math.max(w, 0.4).toFixed(2)}%;background:${c.d >= 0 ? 'var(--blue)' : 'var(--red)'}`})),
          el('span', {class: 'value'}, el('strong', {}, signed(c.d)), ` · ${f1(cv)}% vs ${f1(rv)}%`)));
    });
    const first = cats[0];
    return [el('ul', {class: 'legend'}, el('li', {}, el('span', {class: 'swatch', style: 'background:var(--blue)'}), 'More common among connected works'),
      el('li', {}, el('span', {class: 'swatch', style: 'background:var(--red)'}), 'Less common among connected works')),
    el('div', {class: 'rows'}, axisRow(ticks, 'Connected vs remaining'), rows),
    el('p', {class: 'note'}, `Differences in percentage points between connected and remaining works, each share using its own base. Descriptive, with no intervals. Works with this dimension coded: ${whole(first.connected.denominator)} connected and ${whole(first.remaining.denominator)} remaining. `,
      el('a', {href: 'data/funding_content_profiles.csv', download: true}, 'Download (CSV)'))];
  });
  draw();
}

// ---------- Careers ----------
async function careers() {
  const bases = sourceTable(EMPLOYMENT + 'observation_bases.csv');
  const roleRows = client.load('employment_roles', {specification: ['inclusive'], basis: ['observed']});

  panel(document.getElementById('careers-lead'), async () => {
    const rd = (await bases).find(r => r.degree_group === 'Research doctorate');
    const roles = (await roleRows).rows.filter(r => r.degree_group === 'PhD/ScD and equivalent');
    const st = stateRows(roles, 'joint_state'), N = num(roles[0].denominator);
    // One denominator per degree group; all_observations is the released total.
    const degreeBases = new Map((await roleRows).rows.map(r => [r.degree_group, [r.degree_label.replace("'", '’'), num(r.denominator)]]));
    const total = degreeBases.get('all_observations')[1];
    const groups = [...degreeBases].filter(([g]) => g !== 'all_observations').map(([, b]) => b).sort((a, b) => b[1] - a[1]);
    return [el('p', {class: 'lead'}, `Of ${whole(N)} sampled research-doctorate authors, ${Math.round(share(num(rd.university_n), num(rd.observed_n)))}% worked at colleges and universities and ${Math.round(share(num(rd.outside_n), num(rd.observed_n)))}% elsewhere. ${Math.round(share(st.research_likely_only[0] + st.both[0], N))}% held jobs whose occupation and industry suggest research.`),
      el('p', {class: 'sub', id: 'careers-sample'}, `Total n = ${whole(total)}: employment was linked for ${whole(total)} of 325 authors selected by stratified random sampling of in-scope records (Supplement S4.1). By degree: ${groups.map(([label, n]) => `${label === 'PsyD' ? label : label[0].toLowerCase() + label.slice(1)} ${whole(n)}`).join(', ')}. Counts and percentages are unweighted.`)];
  });

  // Panel 1: occupations and industries by degree
  const degrees = [['PhD/ScD and equivalent', 'Research doctorate'], ["General master's", 'General master’s'], ["Field-specific master's", 'Field-specific master’s'], ['PsyD', 'PsyD'], ['Other named doctorate', 'Other named doctorate']];
  let jobDegree = degrees[0][0];
  document.getElementById('jobs-controls').append(segmented('Degree', degrees, jobDegree, value => { jobDegree = value; drawJobs(); }));
  const drawJobs = () => panel(document.getElementById('jobs'), async () => {
    const [occupations, baseRows] = await Promise.all([client.load('employment_occupations', {degree_group: [jobDegree]}), bases]);
    const rows = occupations.rows, N = num(rows[0].denominator);
    const named = rows.filter(r => r.occupation_status === 'coded').sort((a, b) => num(b.numerator) - num(a.numerator));
    const others = ['aggregate_residual', 'unavailable'].map(s => rows.find(r => r.occupation_status === s)).filter(r => r && num(r.numerator) > 0);
    const occ = [...named, ...others];
    const max = Math.max(...occ.map(r => num(r.numerator)));
    const label = degrees.find(d => d[0] === jobDegree)[1];
    const baseKey = jobDegree === 'PhD/ScD and equivalent' ? 'Research doctorate' : jobDegree.includes('master') ? "Master's" : null;
    const base = baseKey && baseRows.find(r => r.degree_group === baseKey);
    let lead;
    if (named.length) {
      const topN = num(named[0].numerator), tops = named.filter(r => num(r.numerator) === topN).map(r => r.occupation_title);
      lead = tops.length > 1 ? `Most common named occupations: ${joinWords(tops)} (${topN} each of ${whole(N)}).` : `Most common named occupation: ${tops[0]} (${topN} of ${whole(N)}).`;
    } else lead = `No occupation was held by 5 or more of the ${whole(N)} ${label === 'PsyD' ? label : label[0].toLowerCase() + label.slice(1)} authors, so none is named.`;
    if (base) lead += ` ${f1(share(num(base.university_n), num(base.observed_n)))}% ${baseKey === "Master's" ? 'of all master’s authors ' : ''}worked at colleges and universities.`;
    document.getElementById('jobs-lead').textContent = lead;
    const industry = base ? [
      {code: '6113', kind: 'naics', label: 'Colleges, universities and professional schools', n: num(base.university_n), color: 'var(--blue-dark)'},
      {code: 'other', kind: 'naics', label: 'Any other known industry (outside universities)', n: num(base.outside_n)},
      {label: 'Industry unknown', n: num(base.unknown_industry_n), color: 'var(--gray)'}] : [];
    const industryMax = Math.max(1, ...industry.map(r => r.n));
    return [
      el('div', {class: 'card-head'}, el('h3', {}, 'Industry ', el('span', {class: 'badge'}, 'NAICS'))),
      base ? barRows(industry.map(r => ({...r, frac: r.n / industryMax, value: `${whole(r.n)} · ${f1(share(r.n, num(base.observed_n)))}%`, title: `${r.label}: ${whole(r.n)} of ${whole(base.observed_n)} authors`}))) : null,
      baseKey === "Master's" ? el('p', {class: 'note'}, `Industry is released for general and field-specific master’s degrees combined (n = ${whole(base.observed_n)}).`) : null,
      base ? null : el('p', {class: 'note'}, 'An industry split is not released for this degree group.'),
      el('div', {class: 'section-rule'}, el('h3', {}, 'Occupation ', el('span', {class: 'badge soc'}, 'SOC')),
        barRows(occ.map(r => {
          const isNamed = r.occupation_status === 'coded', n = num(r.numerator);
          return {code: isNamed ? r.soc_unit_code : null, kind: 'soc', label: isNamed ? r.occupation_title : r.occupation_status === 'unavailable' ? 'Occupation unavailable' : 'Other occupations, each held by fewer than 5',
            frac: n / max, color: isNamed ? 'var(--blue)' : 'var(--gray)', value: `${whole(n)} · ${f1(share(n, N))}%`,
            title: `${isNamed ? 'SOC ' + r.soc_unit_code + ', ' : ''}${r.occupation_title}: ${whole(n)} of ${whole(N)} authors`};
        }))),
      el('p', {class: 'note'}, 'Shares of all authors in the group with observed employment. Occupations held by fewer than 5 authors are pooled and not named. Code lists: ',
        el('a', {href: 'https://www.bls.gov/soc/'}, 'SOC (BLS)'), ' · ', el('a', {href: 'https://www.census.gov/naics/'}, 'NAICS (Census Bureau)'), ' · ',
        el('a', {href: 'data/employment_occupations.csv', download: true}, 'Download (CSV)'))];
  });
  drawJobs();

  // Panel 2: research or clinical likelihood
  let roleView = 'degree';
  document.getElementById('roles-controls').append(segmented('Compare authors', [['degree', 'By degree'], ['connection', 'By NIH connection']], roleView, value => { roleView = value; drawRoles(); }));
  const drawRoles = () => panel(document.getElementById('roles'), async () => {
    let groups, note, href;
    if (roleView === 'degree') {
      const order = ['PhD/ScD and equivalent', "General master's", "Field-specific master's", 'PsyD', 'Other named doctorate', 'all_observations'];
      const rows = (await roleRows).rows;
      groups = order.map(g => { const rs = rows.filter(r => r.degree_group === g); return {label: rs[0].degree_label.replace("'", '’'), N: num(rs[0].denominator), states: stateRows(rs, 'joint_state')}; });
      note = 'Each bar is one degree group; percentages use every author with observed employment in that group.';
      href = 'data/employment_roles.csv';
    } else {
      const rows = (await client.load('employment_connection_profiles', {specification: ['inclusive']})).rows;
      groups = ['Research doctorate', "Master's"].flatMap(g => [['1', 'identified NIDA/NIAAA connection'], ['0', 'no identified connection']].map(([c, text]) => {
        const rs = rows.filter(r => r.degree_group === g && r.connection_clear === c);
        return {label: `${DEGREE[g]}, ${text}`, N: num(rs[0].denominator), states: stateRows(rs, 'state')};
      }));
      note = 'Authors are split by whether their dissertation or thesis had an identified NIDA/NIAAA connection.';
      href = 'data/employment_connection_profiles.csv';
    }
    return [roleLegend(), ...roleStacks(groups),
      el('p', {class: 'note'}, `${note} Groups under 30 authors are marked “small sample”: read their shares as rough. `, el('a', {href, download: true}, 'Download (CSV)'))];
  });
  drawRoles();

  // Panel 3: destinations outside universities
  const state = {degree: 'Research doctorate', view: 'jobs'};
  document.getElementById('outside-controls').append(
    segmented('Degree', [['Research doctorate', 'Research doctorate'], ["Master's", 'Master’s']], state.degree, value => { state.degree = value; drawOutside(); }),
    segmented('Show', [['jobs', 'Occupations and industries'], ['roles', 'Research or clinical likelihood']], state.view, value => { state.view = value; drawOutside(); }));
  const drawOutside = () => panel(document.getElementById('outside'), async () => {
    const [destinations, roles, breakdowns, classification] = await Promise.all([
      client.load('outside_destinations', {degree_group: [state.degree]}),
      client.load('outside_roles', {degree_group: [state.degree], specification: ['inclusive'], basis: ['observed']}),
      client.load('outside_occupation_breakdowns', {source_table_id: [EMPLOYMENT + 'occupation_by_destination.csv']}),
      sourceTable(EMPLOYMENT + 'destination_classification.csv')]);
    const dests = destinations.rows.map(r => ({label: r.destination_label, n: num(r.numerator), N: num(r.denominator)})).sort((a, b) => b.n - a.n);
    const outsideN = dests[0].N, topN = dests[0].n, tops = dests.filter(d => d.n === topN).map(d => d.label);
    const degreeWord = state.degree === 'Research doctorate' ? 'research-doctorate' : 'master’s';
    document.getElementById('outside-lead').textContent = `${whole(outsideN)} ${degreeWord} authors worked outside universities. The most common destination${tops.length > 1 ? `s were ${joinWords(tops)} (${topN} each)` : ` was ${tops[0]} (${topN}, ${f1(share(topN, outsideN))}%)`}.`;
    if (state.view === 'jobs') {
      const naics = groupBy([...classification].sort((a, b) => num(a.ordered_detail) - num(b.ordered_detail)), r => r.display_group_label);
      const named = breakdowns.rows.filter(r => r.degree_group === state.degree && r.destination_dimension === 'grouped' && r.occupation_row_type === 'named');
      return [
        el('ul', {class: 'legend'}, el('li', {}, tag('naics', 'NAICS'), 'industry codes that define the destination'), el('li', {}, tag('soc', 'SOC'), 'occupations held by 5 or more authors there')),
        barRows(dests.map(d => ({label: d.label, sub: d.n < 30 ? 'small sample' : null, frac: d.n / topN, value: `${whole(d.n)} · ${f1(share(d.n, outsideN))}%`,
          title: `${d.label}: ${whole(d.n)} of ${whole(outsideN)} authors outside universities`,
          tags: [...(naics.get(d.label) ?? []).map(r => {
            const prefixes = JSON.parse(r.ordered_naics_prefixes_json).filter(Boolean);
            return tag('naics', prefixes.length ? prefixes.join(', ') : 'any other', r.destination_detail, null, `NAICS ${prefixes.length ? prefixes.join(', ') : 'any other known code'}: ${r.destination_detail}`);
          }), ...named.filter(r => r.destination_label === d.label).map(r =>
            tag('soc', r.soc_code, r.occupation_title, whole(r.numerator), `SOC ${r.soc_code}, ${r.occupation_title}: ${whole(r.numerator)} of ${whole(r.denominator)} authors in this destination`))]}))),
        el('p', {class: 'note'}, 'Each author counts once, in the first destination whose NAICS codes match, in the order shown; a broad code covers only what earlier codes did not. Unknown industry is excluded. ',
          el('a', {href: 'data/outside_destinations.csv', download: true}, 'Download (CSV)'))];
    }
    const byDestination = groupBy(roles.rows, r => r.destination_label);
    const order = ['All outside', ...dests.map(d => d.label)];
    const groups = order.filter(label => byDestination.has(label)).map(label => {
      const rs = byDestination.get(label);
      return {label, N: num(rs[0].denominator), states: stateRows(rs, 'state')};
    });
    return [roleLegend(), ...roleStacks(groups),
      el('p', {class: 'note'}, 'Percentages use all authors in each destination. Most destinations have fewer than 30 authors, so read them as rough. ',
        el('a', {href: 'data/outside_roles.csv', download: true}, 'Download (CSV)'))];
  });
  drawOutside();
}

const pages = {overview, content, funding, careers};
pages[document.body.dataset.page]?.();
