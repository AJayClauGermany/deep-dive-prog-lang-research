/* Language Literature Explorer — reads data.json (built by tools/build_explorer.py) and renders every view client-side.
   Routes are plain #names: home, languages, lang-<id>, concepts, concept-<id>, compare-<id>--<id>, lineage-<id>,
   sites, site-<slug>, people, person-<slug>, saved, search. */
(() => {
  'use strict';

  const PAGE = 150;
  const INVERSE = {
    'dialect-of': 'has dialect', 'superset-of': 'subset-of', 'subset-of': 'superset-of', 'successor-of': 'succeeded by',
    'compiles-to': 'compile target of', 'implemented-in': 'implements', 'embeds': 'embedded in', 'host-of': 'hosted by',
    'variant-of': 'has variant', 'formalizes': 'formalized by', 'family': 'family',
  };
  const LEVEL_SHORT = ['Source code', 'Primary', 'Secondary', 'Tertiary'];
  const STATUS_TEXT = { blocked: 'not verified: site blocks robots', error: 'link check failed', 'repo-only': 'repository verified, path not', dead: 'dead link', 'anchor-missing': 'section anchor missing', unchecked: 'not checked' };

  let D, L, C, R, SITES, COLLS, PEOPLE;
  const langIdx = {}, conceptIdx = {}, siteBySlug = {}, personBySlug = {}, sharedDocs = new Map(), byKey = new Map();
  const ui = { panels: {}, q: '', langs: { q: '', cat: '', status: '', def: '', typ: '', par: '', from: '', to: '', sort: 'name', dir: 1, sel: new Set() },
    compare: { mode: 'all', lv: [1, 1, 1, 1], open: new Set() }, lineage: { depth: 2, to: '' }, sites: { q: '', shown: PAGE }, people: { q: '', shown: PAGE }, concepts: { q: '' } };
  let saved = new Set();

  // ---------- tiny DOM helpers ----------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'class') el.className = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    el.append(...kids.flat(Infinity).filter(x => x != null && x !== false));
    return el;
  }
  const NS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, ...kids) {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs || {}) if (attrs[k] != null) el.setAttribute(k, attrs[k]);
    el.append(...kids.filter(x => x != null));
    return el;
  }
  const num = n => n.toLocaleString('en-US');
  const slug = t => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const plural = (n, w) => `${num(n)} ${w}${n === 1 ? '' : 's'}`;
  const ext = (url, text, cls) => h('a', { href: url, target: '_blank', rel: 'noopener noreferrer', class: cls }, text);
  const lv = (i, cls) => h('span', { class: `lv lv${i} ${cls || ''}`, title: `Level ${i}: ${D.meta.levels[i].name}` }, 'L' + i);
  const empty = text => h('div', { class: 'empty' }, text);
  const lang = id => L[langIdx[id]];
  const yearOf = id => (lang(id) && lang(id).year) || null;
  const byYear = (a, b) => (yearOf(a) || 9999) - (yearOf(b) || 9999) || a.localeCompare(b);
  function langLink(id, withYear) {
    const l = lang(id);
    if (!l) return h('span', { class: 'faint', title: 'Named as a connection, but has no entry in the catalog' }, id);
    return h('a', { href: '#lang-' + id }, l.name, withYear && l.year ? h('span', { class: 'faint small num' }, ' ' + l.year) : null);
  }
  const conceptChip = (i, extra) => h('a', { class: 'chip concept', href: '#concept-' + C[i].id, title: C[i].name + ' — ' + C[i].desc }, C[i].id, extra || null);
  function mix(counts, big) {
    const total = counts.reduce((a, b) => a + b, 0) || 1;
    return h('span', { class: 'mix' + (big ? ' big' : ''), role: 'img', 'aria-label': counts.map((n, i) => `L${i} ${n}`).join(', '), title: counts.map((n, i) => `L${i} ${LEVEL_SHORT[i]}: ${num(n)}`).join(' · ') },
      counts.map((n, i) => n ? h('i', { class: 's' + i, style: `flex:${n / total}` }) : null));
  }
  function toast(text) {
    const t = h('div', { class: 'toast', role: 'status' }, text);
    document.body.append(t);
    setTimeout(() => t.remove(), 2200);
  }
  function copy(text, what, host) {
    const fallback = () => {
      const box = h('textarea', { class: 'copybox', readonly: true, 'aria-label': 'Text to copy' });
      box.value = text;
      host.querySelectorAll('.copybox').forEach(x => x.remove());
      host.append(box);
      box.select();
      toast('Copying is blocked here. The text is selected below: copy it by hand.');
    };
    try { navigator.clipboard.writeText(text).then(() => toast(`Copied ${what}`), fallback); } catch (e) { fallback(); }
  }

  // ---------- data ----------
  function prepare(d) {
    D = d; L = d.langs; C = d.concepts;
    const E = d.enums;
    L.forEach((l, i) => { l.i = i; langIdx[l.id] = i; l.res = []; l.mentions = []; l.influenced = []; l.rels = []; l.lc = [0, 0, 0, 0]; });
    C.forEach((c, i) => { c.i = i; conceptIdx[c.id] = i; c.res = []; c.langs = new Set(); });
    SITES = d.sites.map((name, i) => ({ i, name, slug: slug(name), res: [], langs: new Set(), lc: [0, 0, 0, 0] }));
    SITES.forEach(x => { siteBySlug[x.slug] = x; });
    COLLS = d.collections.map((g, i) => ({ ...g, i, res: [] }));
    PEOPLE = new Map();
    const person = name => PEOPLE.get(name) || PEOPLE.set(name, { name, designed: [], authored: [] }).get(name);
    R = d.res.map((row, i) => {
      const [o, level, kind, t, u, site, cs, section, auth, fmt, acc, st, x] = row;
      const r = { i, o, lv: level, kind: E.kind[kind], t, u, site: SITES[site], c: cs, section, auth: E.authority[auth], fmt: E.format[fmt], acc: E.access[acc] || 'open', st: E.status[st], x: x || {} };
      r.key = (o >= 0 ? L[o].id : 'general/' + COLLS[-1 - o].id) + '|' + u;
      byKey.set(r.key, r);
      if (o >= 0) {
        L[o].res.push(r); L[o].lc[level]++; r.site.langs.add(o);
        const base = u.split('#')[0];
        (sharedDocs.get(base) || sharedDocs.set(base, new Set()).get(base)).add(o);
      } else {
        COLLS[-1 - o].res.push(r);
        (r.x.l || []).forEach(li => L[li].mentions.push(r));
      }
      r.site.res.push(r); r.site.lc[level]++;
      cs.forEach(ci => { C[ci].res.push(r); if (o >= 0) C[ci].langs.add(o); });
      (r.x.a || []).forEach(a => person(a).authored.push(r));
      return r;
    });
    L.forEach(l => {
      l.concepts = new Set(l.res.flatMap(r => r.c));
      l.des.forEach(n => person(n).designed.push(l.id));
      l.inf.forEach(id => { if (lang(id) && id !== l.id) lang(id).influenced.push(l.id); });
      l.rel.forEach(([id, rel]) => { if (id === l.id) return; l.rels.push([id, rel]); if (lang(id)) lang(id).rels.push([l.id, INVERSE[rel] || rel]); });
    });
    PEOPLE.forEach(p => { let sl = slug(p.name) || 'x'; while (personBySlug[sl]) sl += '-2'; p.slug = sl; personBySlug[sl] = p; });
    try { saved = new Set(JSON.parse(localStorage.getItem('lle-saved') || '[]').filter(k => byKey.has(k))); } catch (e) { saved = new Set(); }
  }
  const ownerName = r => r.o >= 0 ? L[r.o].name : COLLS[-1 - r.o].title;
  const hay = r => r.h || (r.h = [r.t, r.u, ownerName(r), r.o >= 0 ? L[r.o].id : '', r.kind, r.c.map(i => C[i].id).join(' '), (r.x.a || []).join(' '), r.x.i || '', r.x.n || ''].join(' ').toLowerCase());
  const terms = q => q.toLowerCase().split(/\s+/).filter(Boolean);
  function persist() { try { localStorage.setItem('lle-saved', JSON.stringify([...saved])); } catch (e) { /* storage unavailable: the list lasts for this visit */ } updateNav(); }

  // ---------- pickers ----------
  function picker(items, placeholder, onPick, id) {
    const input = h('input', { type: 'text', id, placeholder, autocomplete: 'off', role: 'combobox', 'aria-expanded': 'false', 'aria-label': placeholder });
    const ul = h('ul', { hidden: true, role: 'listbox' });
    let cur = [], sel = 0;
    const choose = it => { input.value = ''; ul.hidden = true; onPick(it.value); };
    function draw() {
      const q = input.value.trim().toLowerCase();
      cur = [];
      if (q) {
        for (const it of items) {
          const lab = it.label.toLowerCase();
          const sc = lab === q || it.value === q ? 0 : lab.startsWith(q) || String(it.value).startsWith(q) ? 1 : it.hay.includes(' ' + q) ? 2 : it.hay.includes(q) ? 3 : 9;
          if (sc < 9) cur.push([sc, -(it.w || 0), it]);
        }
        cur = cur.sort((a, b) => a[0] - b[0] || a[1] - b[1]).slice(0, 12).map(x => x[2]);
      }
      sel = Math.min(sel, Math.max(cur.length - 1, 0));
      ul.replaceChildren(...cur.map((it, i) => h('li', { role: 'option', 'aria-selected': String(i === sel), onmousedown: e => { e.preventDefault(); choose(it); } },
        h('span', null, it.label), h('span', { class: 'faint small' }, it.sub || ''))));
      ul.hidden = !cur.length;
      input.setAttribute('aria-expanded', String(!!cur.length));
    }
    input.addEventListener('input', () => { sel = 0; draw(); });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, cur.length - 1); draw(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
      else if (e.key === 'Enter' && cur[sel]) { choose(cur[sel]); e.preventDefault(); }
      else if (e.key === 'Escape') ul.hidden = true;
    });
    input.addEventListener('blur', () => { ul.hidden = true; });
    return h('span', { class: 'picker' }, input, ul);
  }
  let langItems, conceptItems;
  const langPicker = (placeholder, onPick, id) => picker(langItems || (langItems = L.map(l => ({ label: l.name, sub: l.year || '', value: l.id, w: l.res.length, hay: ' ' + [l.id, l.name, ...l.aka].join(' ').toLowerCase() }))), placeholder, onPick, id);
  const conceptPicker = (placeholder, onPick, id) => picker(conceptItems || (conceptItems = C.map(c => ({ label: c.name, sub: c.id, value: c.id, w: c.res.length, hay: ' ' + [c.id, c.name, ...c.aka].join(' ').toLowerCase() }))), placeholder, onPick, id);
  const go = hash => { location.hash = hash; };

  // ---------- resource rows and panels ----------
  function resRow(r, showOwner) {
    const meta = [];
    if (showOwner) meta.push(r.o >= 0 ? langLink(L[r.o].id) : h('span', null, COLLS[-1 - r.o].title));
    meta.push(r.kind.replace(/-/g, ' '));
    meta.push(h('a', { class: 'site', href: '#site-' + r.site.slug, title: 'Everything catalogued on this site' }, r.site.name));
    if (r.x.a) meta.push(r.x.a.slice(0, 4).map((a, i) => [i ? ', ' : '', h('a', { href: '#person-' + PEOPLE.get(a).slug }, a)]).concat(r.x.a.length > 4 ? ' et al.' : ''));
    if (r.x.y) meta.push(String(r.x.y));
    if (r.x.v) meta.push('version ' + r.x.v);
    if (r.x.i) meta.push('implementation: ' + r.x.i);
    const flags = [];
    if (r.st !== 'ok') flags.push(h('span', { class: 'chip warn' }, STATUS_TEXT[r.st] || r.st));
    if (r.acc !== 'open') flags.push(h('span', { class: 'chip warn' }, r.acc.replace('-', ' ')));
    const others = r.o >= 0 ? [...(sharedDocs.get(r.u.split('#')[0]) || [])].filter(i => i !== r.o) : [];
    const key = r.key;
    const star = h('button', { class: 'star', 'aria-pressed': String(saved.has(key)), 'aria-label': 'Save to reading list', title: 'Save to reading list',
      onclick: () => { saved.has(key) ? saved.delete(key) : saved.add(key); star.setAttribute('aria-pressed', String(saved.has(key))); star.textContent = saved.has(key) ? '★' : '☆'; persist(); } }, saved.has(key) ? '★' : '☆');
    return h('div', { class: 'res' }, lv(r.lv),
      h('div', null,
        ext(r.u, r.t, 'res-title'),
        h('div', { class: 'res-meta' }, meta.map((m, i) => [i ? ' · ' : '', m])),
        r.c.length || flags.length ? h('div', { class: 'chips' }, flags, r.c.map(i => conceptChip(i))) : null,
        r.x.n ? h('div', { class: 'note' }, r.x.n) : null,
        others.length ? h('div', { class: 'res-meta' }, 'Same document also filed under: ', others.slice(0, 8).map((i, k) => [k ? ', ' : '', langLink(L[i].id)]), others.length > 8 ? ` and ${others.length - 8} more` : '') : null),
      star);
  }

  function groupRows(rows, mode) {
    const map = new Map();
    const add = (k, r) => (map.get(k) || map.set(k, []).get(k)).push(r);
    if (mode === 'level') rows.forEach(r => add(r.lv, r));
    else if (mode === 'language') rows.forEach(r => add(r.o, r));
    else if (mode === 'concept') rows.forEach(r => (r.c.length ? r.c : [-1]).forEach(c => add(c, r)));
    else if (mode === 'site') rows.forEach(r => add(r.site.i, r));
    else if (mode === 'kind') rows.forEach(r => add(r.kind, r));
    else if (mode === 'year') rows.forEach(r => add(r.x.y ? Math.floor(r.x.y / 10) * 10 : 0, r));
    let groups = [...map].map(([k, items]) => ({ k, items }));
    const size = (a, b) => b.items.length - a.items.length;
    if (mode === 'level') { groups.sort((a, b) => a.k - b.k); groups.forEach(g => { g.head = [lv(g.k), D.meta.levels[g.k].name]; }); }
    else if (mode === 'language') {
      const nm = g => g.k >= 0 ? '0' + L[g.k].name.toLowerCase() : '1' + COLLS[-1 - g.k].title.toLowerCase();
      groups.sort((a, b) => nm(a).localeCompare(nm(b)));
      groups.forEach(g => { g.head = g.k >= 0 ? [langLink(L[g.k].id, true)] : [COLLS[-1 - g.k].title, h('span', { class: 'chip' }, 'cross-language collection')]; });
    } else if (mode === 'concept') {
      groups.sort((a, b) => (a.k < 0 ? 1e9 : a.k) - (b.k < 0 ? 1e9 : b.k));
      groups.forEach(g => { g.head = g.k < 0 ? ['No concept tag (covers the language as a whole)'] : [h('a', { href: '#concept-' + C[g.k].id }, C[g.k].name), h('span', { class: 'faint small' }, C[g.k].cat)]; });
    } else if (mode === 'site') { groups.sort(size); groups.forEach(g => { g.head = [h('a', { href: '#site-' + SITES[g.k].slug, class: 'mono' }, SITES[g.k].name)]; }); }
    else if (mode === 'kind') { groups.sort(size); groups.forEach(g => { g.head = [g.k.replace(/-/g, ' ')]; }); }
    else if (mode === 'year') { groups.sort((a, b) => (a.k || 9999) - (b.k || 9999)); groups.forEach(g => { g.head = [g.k ? g.k + 's' : 'Undated']; }); }
    else groups = [{ k: 0, items: rows, head: null }];
    groups.forEach(g => g.items.sort((a, b) => a.lv - b.lv || a.i - b.i));
    return groups;
  }

  function markdown(rows) {
    const out = [];
    for (const g of groupRows(rows, 'language')) {
      out.push(`\n## ${g.k >= 0 ? L[g.k].name : COLLS[-1 - g.k].title}\n`);
      for (const r of g.items) out.push(`- **L${r.lv}** ${r.kind}: [${r.t.replace(/[[\]]/g, '')}](${r.u})${r.c.length ? ' — ' + r.c.map(i => '`' + C[i].id + '`').join(', ') : ''}`);
    }
    return out.join('\n').trim() + '\n';
  }

  /* A filterable, groupable list of links. o: {key, group, groups, multi, page, filters:[{id,label,options:[[value,label]],test(r,value)}]} */
  function resPanel(all, o) {
    const st = ui.panels[o.key] || (ui.panels[o.key] = { lv: [1, 1, 1, 1], kind: '', q: '', group: o.group || 'level', extra: {}, shown: o.page || PAGE });
    const groups = o.groups || ['level', 'concept', 'site', 'kind'];
    const lvCount = [0, 0, 0, 0], kindCount = {};
    all.forEach(r => { lvCount[r.lv]++; kindCount[r.kind] = (kindCount[r.kind] || 0) + 1; });
    const id = 'p-' + slug(o.key);
    const list = h('div', { class: 'stack' }), info = h('span', { class: 'muted small num' });
    const root = h('div', { class: 'stack' });
    const reset = () => { st.shown = o.page || PAGE; draw(); };
    const lvBtns = [0, 1, 2, 3].map(i => h('button', { class: 'lv lv' + i, id: `${id}-l${i}`, title: `${D.meta.levels[i].name}: show or hide`, 'aria-pressed': String(!!st.lv[i]),
      onclick: e => { st.lv[i] = st.lv[i] ? 0 : 1; e.currentTarget.setAttribute('aria-pressed', String(!!st.lv[i])); e.currentTarget.classList.toggle('off', !st.lv[i]); reset(); } }, `L${i} ${LEVEL_SHORT[i]} `, num(lvCount[i])));
    lvBtns.forEach((b, i) => b.classList.toggle('off', !st.lv[i]));
    const select = (sid, label, options, value, onchange) => h('select', { id: sid, 'aria-label': label, onchange: e => onchange(e.target.value) },
      options.map(([v, t]) => h('option', { value: v, selected: v === value }, t)));
    const kinds = Object.entries(kindCount).sort((a, b) => b[1] - a[1]);
    const current = () => {
      const ts = terms(st.q);
      return all.filter(r => st.lv[r.lv] && (!st.kind || r.kind === st.kind) && (o.filters || []).every(f => !st.extra[f.id] || f.test(r, st.extra[f.id])) && ts.every(t => hay(r).includes(t)));
    };
    function draw() {
      const rows = current();
      info.textContent = rows.length === all.length ? plural(all.length, 'link') : `${num(rows.length)} of ${plural(all.length, 'link')}`;
      const gs = groupRows(rows, st.group);
      let budget = st.shown, total = 0;
      list.replaceChildren();
      for (const g of gs) {
        total += g.items.length;
        if (budget <= 0) continue;
        const items = g.items.slice(0, budget);
        budget -= items.length;
        list.append(h('section', { class: 'group' }, g.head ? h('h3', null, g.head, h('span', { class: 'faint small num' }, num(g.items.length))) : null,
          items.map(r => resRow(r, o.multi && st.group !== 'language'))));
      }
      if (total > st.shown) list.append(h('div', null, h('button', { onclick: () => { st.shown += PAGE; draw(); } }, `Show ${num(Math.min(PAGE, total - st.shown))} more`)));
      if (!rows.length) list.append(empty(all.length ? 'No links match these filters. Turn a level back on or clear the search.' : 'Nothing here yet.'));
    }
    const search = h('input', { type: 'search', id: id + '-q', placeholder: 'Filter these links…', 'aria-label': 'Filter these links', value: st.q, oninput: e => { st.q = e.target.value; reset(); } });
    root.append(h('div', { class: 'toolbar' }, h('span', { class: 'row' }, lvBtns), search,
      kinds.length > 1 ? select(id + '-kind', 'Kind of source', [['', 'Any kind']].concat(kinds.map(([k, n]) => [k, `${k.replace(/-/g, ' ')} (${n})`])), st.kind, v => { st.kind = v; reset(); }) : null,
      (o.filters || []).map(f => select(`${id}-${f.id}`, f.label, f.options, st.extra[f.id] || '', v => { st.extra[f.id] = v; reset(); })),
      h('label', { class: 'small muted', for: id + '-group' }, 'Group by'),
      select(id + '-group', 'Group by', groups.map(g => [g, g]), st.group, v => { st.group = v; reset(); }),
      h('button', { onclick: () => { const rows = current(); copy(markdown(rows), `${plural(rows.length, 'link')} as Markdown`, root); } }, 'Copy as Markdown'),
      h('button', { onclick: () => { const rows = current(); let n = 0; rows.forEach(r => { if (!saved.has(r.key)) { saved.add(r.key); n++; } }); persist(); draw(); toast(`Saved ${plural(n, 'link')} to the reading list`); } }, 'Save all'),
      info), list);
    draw();
    return root;
  }
  const conceptFilter = rows => {
    const n = {};
    rows.forEach(r => r.c.forEach(c => { n[c] = (n[c] || 0) + 1; }));
    const opts = Object.keys(n).map(Number).sort((a, b) => C[a].name.localeCompare(C[b].name)).map(c => [String(c), `${C[c].name} (${n[c]})`]);
    return { id: 'concept', label: 'Concept', options: [['', 'Any concept']].concat(opts), test: (r, v) => r.c.includes(Number(v)) };
  };

  // ---------- views ----------
  const head = (label, title, ...rest) => h('header', { class: 'stack' }, label ? h('div', { class: 'label' }, label) : null, h('h1', null, title), rest);
  const section = (title, ...kids) => h('section', { class: 'stack' }, h('h2', null, title), kids);

  function viewHome() {
    const m = D.meta, n = m.counts;
    const counts = [0, 1, 2, 3].map(i => n['level_' + i] || 0);
    const cats = {};
    L.forEach(l => l.cats.forEach(c => { cats[c] = (cats[c] || 0) + 1; }));
    const ex = (hash, text) => h('li', null, h('a', { href: hash }, text));
    return [
      head(null, 'Literature for comparing computer languages',
        h('p', { class: 'summary muted' }, `${num(n.languages)} languages, ${num(n.resources)} links and ${num(n.concepts)} concepts. Every link is filed by how close it sits to the language itself, and tagged with the concepts it covers, so the same idea can be followed across languages.`)),
      h('section', { class: 'panel stack' },
        h('h2', null, 'Four levels of source'), mix(counts, true),
        h('div', { class: 'legend' }, m.levels.map((x, i) => h('div', null, lv(i), h('strong', null, x.name, ' ', h('span', { class: 'faint num' }, num(counts[i]))), h('span', { class: 'what' }, x.description))))),
      h('div', { class: 'cols' },
        h('section', { class: 'panel stack' }, h('h2', null, 'Start from a language'), langPicker('Type a language name…', id => go('lang-' + id), 'home-lang'),
          h('div', { class: 'chips' }, ['c', 'rust', 'haskell', 'python', 'sql', 'lambda-calculus', 'prolog', 'apl', 'webassembly', 'yaml'].filter(lang).map(id => h('a', { class: 'chip', href: '#lang-' + id }, lang(id).name)))),
        h('section', { class: 'panel stack' }, h('h2', null, 'Start from a concept'), conceptPicker('Type a concept, e.g. closures…', id => go('concept-' + id), 'home-concept'),
          h('div', { class: 'chips' }, ['pattern-matching', 'garbage-collection', 'type-inference', 'concurrency', 'macros', 'joins', 'formal-semantics', 'parser'].filter(c => c in conceptIdx).map(c => conceptChip(conceptIdx[c])))),
        h('section', { class: 'panel stack' }, h('h2', null, 'Follow a connection'),
          h('ul', { class: 'stack', style: 'margin:0;padding-left:1.1em;gap:4px' },
            ex('#compare-rust--go--zig', 'Compare Rust, Go and Zig concept by concept'),
            ex('#lineage-standard-ml', 'See what Standard ML came from and led to'),
            ex('#sites', 'Find the websites that hold the most specifications'),
            ex('#person-niklaus-wirth', 'Everything Niklaus Wirth designed and wrote'),
            ex('#concept-tail-calls', 'How dozens of languages treat tail calls')))),
      section('Languages by kind', h('div', { class: 'tiles' }, Object.entries(cats).sort((a, b) => b[1] - a[1]).map(([c, k]) =>
        h('a', { class: 'tile', href: '#languages', onclick: () => { Object.assign(ui.langs, { q: '', cat: c, status: '', def: '', typ: '', par: '', from: '', to: '' }); } }, h('span', null, c.replace(/-/g, ' ')), h('span', { class: 'num' }, num(k)))))),
      h('footer', null, `Catalog generated ${m.generated}. Link check: ` + Object.entries(m.linkSummary).map(([k, v]) => `${num(v)} ${k}`).join(', ') + '. Links marked “not verified” point at sites that refuse automated checks.'),
    ];
  }

  function viewLanguages() {
    const st = ui.langs;
    const tally = key => { const n = {}; L.forEach(l => (Array.isArray(l[key]) ? l[key] : [l[key]]).forEach(v => { if (v) n[v] = (n[v] || 0) + 1; })); return Object.entries(n).sort((a, b) => b[1] - a[1]); };
    const sel = (key, label, src, min) => h('select', { id: 'lf-' + key, 'aria-label': label, onchange: e => { st[key] = e.target.value; draw(); } },
      h('option', { value: '' }, label), tally(src).filter(x => x[1] >= (min || 1)).map(([v, n]) => h('option', { value: v, selected: st[key] === v }, `${v.replace(/-/g, ' ')} (${n})`)));
    const body = h('tbody'), info = h('span', { class: 'muted small num' });
    const cmp = h('button', { class: 'primary', onclick: () => go('compare-' + [...st.sel].slice(0, 6).join('--')) });
    const syncCmp = () => { cmp.hidden = st.sel.size < 2; cmp.textContent = `Compare ${Math.min(st.sel.size, 6)} selected`; };
    function draw() {
      const ts = terms(st.q), from = Number(st.from) || -1e9, to = Number(st.to) || 1e9;
      let rows = L.filter(l => (!st.cat || l.cats.includes(st.cat)) && (!st.status || l.status === st.status) && (!st.def || l.def.includes(st.def)) && (!st.typ || l.typ.includes(st.typ)) && (!st.par || l.par.includes(st.par)) &&
        ((!st.from && !st.to) || (l.year && l.year >= from && l.year <= to)) && ts.every(t => (l.hay || (l.hay = [l.id, l.name, l.sum, ...l.aka, ...l.des].join(' ').toLowerCase())).includes(t)));
      const key = { name: l => l.name.toLowerCase(), year: l => l.year || 9999, links: l => l.res.length }[st.sort];
      rows.sort((a, b) => { const x = key(a), y = key(b); return (x < y ? -1 : x > y ? 1 : 0) * st.dir; });
      info.textContent = `${num(rows.length)} of ${num(L.length)} languages`;
      body.replaceChildren(...rows.map(l => h('tr', null,
        h('td', null, h('input', { type: 'checkbox', 'aria-label': `Select ${l.name} for comparison`, checked: st.sel.has(l.id), onchange: e => { e.target.checked ? st.sel.add(l.id) : st.sel.delete(l.id); syncCmp(); } })),
        h('td', null, h('a', { href: '#lang-' + l.id }, l.name), ' ', h('span', { class: 'faint mono' }, l.id)),
        h('td', { class: 'n' }, l.year || '—'),
        h('td', { class: 'small muted' }, l.cats.join(', ').replace(/-/g, ' ')),
        h('td', { class: 'small muted' }, l.typ.slice(0, 4).join(', ')),
        h('td', { class: 'n' }, mix(l.lc), ' ', num(l.res.length)))));
      if (!rows.length) body.append(h('tr', null, h('td', { colspan: 6 }, empty('No language matches. Remove a filter or shorten the search.'))));
    }
    const th = (key, label, cls) => h('th', { class: cls }, h('button', { title: 'Sort by ' + label.toLowerCase(), onclick: () => { st.dir = st.sort === key ? -st.dir : (key === 'links' ? -1 : 1); st.sort = key; draw(); } }, label + ' ↕'));
    syncCmp();
    draw();
    return [
      head(null, 'Languages'),
      h('div', { class: 'toolbar' },
        h('input', { type: 'search', id: 'lf-q', placeholder: 'Name, designer or word in the summary…', 'aria-label': 'Filter languages', value: st.q, oninput: e => { st.q = e.target.value; draw(); } }),
        sel('cat', 'Any kind of language', 'cats'), sel('status', 'Any status', 'status'), sel('def', 'Defined by anything', 'def'), sel('typ', 'Any typing', 'typ', 4), sel('par', 'Any paradigm', 'par', 5),
        h('label', { class: 'small muted', for: 'lf-from' }, 'First appeared'),
        h('input', { type: 'number', id: 'lf-from', placeholder: 'from', 'aria-label': 'First appeared from year', value: st.from, oninput: e => { st.from = e.target.value; draw(); } }),
        h('input', { type: 'number', id: 'lf-to', placeholder: 'to', 'aria-label': 'First appeared up to year', value: st.to, oninput: e => { st.to = e.target.value; draw(); } }),
        h('button', { onclick: () => { Object.assign(st, { q: '', cat: '', status: '', def: '', typ: '', par: '', from: '', to: '' }); render(); } }, 'Clear filters'), cmp, info),
      h('div', { class: 'tablewrap' }, h('table', null, h('thead', null, h('tr', null, h('th', null, ''), th('name', 'Language'), th('year', 'Year', 'n'), h('th', null, 'Kind'), h('th', null, 'Typing'), th('links', 'Links by level', 'n'))), body)),
    ];
  }

  function unknown(what, id, back) {
    return [head(null, `No ${what} called “${id}”`), h('p', null, 'It may have been renamed in a newer build of the catalog. ', h('a', { href: back }, `Browse all ${what}s`), '.')];
  }

  function viewLang(id) {
    const l = lang(id);
    if (!l) return unknown('language', id, '#languages');
    const fact = (k, v) => v && (!Array.isArray(v) || v.length) ? [h('dt', null, k), h('dd', null, v)] : null;
    const list = ids => ids.map((x, i) => [i ? ', ' : '', langLink(x, true)]);
    const rels = new Map();
    l.rels.forEach(([o, rel]) => { (rels.get(rel) || rels.set(rel, []).get(rel)).push(o); });
    const catChip = c => h('a', { class: 'chip', href: '#languages', onclick: () => { Object.assign(ui.langs, { q: '', cat: c, status: '', def: '', typ: '', par: '', from: '', to: '' }); } }, c.replace(/-/g, ' '));
    return [
      head([l.status, l.year ? 'first appeared ' + l.year : null].filter(Boolean).join(' · '), l.name,
        l.aka.length ? h('p', { class: 'muted small' }, 'Also known as ' + l.aka.join(', ')) : null,
        h('p', { class: 'summary' }, l.sum),
        h('div', { class: 'row' }, l.home ? ext(l.home, 'Homepage ↗') : null, h('a', { href: '#lineage-' + l.id }, 'Lineage graph'),
          langPicker('Compare with…', o => go(`compare-${l.id}--${o}`), 'lang-compare'))),
      h('div', { class: 'cols' },
        h('section', { class: 'panel stack' }, h('h2', null, 'Profile'), h('dl', { class: 'facts' },
          fact('Kind', h('span', { class: 'chips' }, l.cats.map(catChip))), fact('Paradigms', l.par.join(', ')), fact('Typing', l.typ.join(', ')),
          fact('Designers', l.des.map((d, i) => [i ? ', ' : '', h('a', { href: '#person-' + PEOPLE.get(d).slug }, d)])),
          fact('Defined by', l.def.join(', ').replace(/-/g, ' ')), fact('Standards', l.std.join(', ')), fact('File extensions', l.ext.length ? h('span', { class: 'mono' }, l.ext.join(' ')) : null))),
        h('section', { class: 'panel stack' }, h('h2', null, 'Connections'), h('dl', { class: 'facts' },
          fact('Influenced by', l.inf.length ? list(l.inf) : null), fact('Influenced', l.influenced.length ? list([...l.influenced].sort(byYear)) : null),
          [...rels].map(([rel, ids]) => fact(rel.replace(/-/g, ' ').replace(/^./, c => c.toUpperCase()), list([...new Set(ids)]))),
          fact('Closest in the catalog', h('span', { class: 'stack', style: 'gap:2px' }, l.sim.slice(0, 6).map(([i, sc, why]) => h('span', null, langLink(L[i].id), ' ', h('span', { class: 'faint small' }, `${sc}% · ${why || 'concept coverage'}`))))))),
      ),
      Object.keys(l.notes).length ? h('section', { class: 'panel stack' }, h('h2', null, 'How the levels apply here'), Object.entries(l.notes).sort().map(([k, v]) => h('div', { class: 'res', style: 'border:0;padding:2px 0' }, lv(Number(k)), h('div', { class: 'small' }, v), h('span')))) : null,
      section(`Links for ${l.name}`, resPanel(l.res, { key: 'lang:' + l.id, group: 'level', filters: [conceptFilter(l.res)] })),
      l.mentions.length ? section(`Cross-language material that covers ${l.name}`, h('p', { class: 'muted small' }, 'Comparison tables, textbooks, courses and encyclopedias that treat this language alongside others.'),
        resPanel(l.mentions, { key: 'mentions:' + l.id, group: 'language', groups: ['language', 'level', 'concept', 'site', 'kind'], multi: true, page: 30, filters: [conceptFilter(l.mentions)] })) : null,
    ];
  }

  function viewConcepts() {
    const st = ui.concepts, body = h('tbody');
    function draw() {
      const ts = terms(st.q);
      const rows = [];
      for (const cat of D.conceptCats) {
        const cs = C.filter(c => c.cat === cat.id && ts.every(t => [c.id, c.name, c.desc, ...c.aka].join(' ').toLowerCase().includes(t)));
        if (!cs.length) continue;
        rows.push(h('tr', { class: 'cat' }, h('td', { colspan: 4 }, `${cat.id} — ${cat.description}`)));
        cs.forEach(c => rows.push(h('tr', null, h('td', null, h('a', { href: '#concept-' + c.id }, c.name), ' ', h('span', { class: 'faint mono' }, c.id)),
          h('td', { class: 'small muted' }, c.desc, c.aka.length ? h('span', { class: 'faint' }, ' Also: ' + c.aka.join(', ') + '.') : null),
          h('td', { class: 'n' }, num(c.langs.size)), h('td', { class: 'n' }, num(c.res.length)))));
      }
      body.replaceChildren(...rows);
      if (!rows.length) body.append(h('tr', null, h('td', { colspan: 4 }, empty('No concept matches that word. Try a synonym, e.g. “lambda” for closures.'))));
    }
    draw();
    return [
      head(null, 'Concepts', h('p', { class: 'summary muted' }, 'The fixed vocabulary every link is tagged with. Open one to read how each language defines, teaches and implements it.')),
      h('div', { class: 'toolbar' }, h('input', { type: 'search', id: 'cf-q', placeholder: 'Find a concept…', 'aria-label': 'Find a concept', value: st.q, oninput: e => { st.q = e.target.value; draw(); } })),
      h('div', { class: 'tablewrap' }, h('table', { class: 'matrix' }, h('thead', null, h('tr', null, h('th', null, 'Concept'), h('th', null, 'What it covers'), h('th', { class: 'n' }, 'Languages'), h('th', { class: 'n' }, 'Links'))), body)),
    ];
  }

  function viewConcept(id) {
    const c = C[conceptIdx[id]];
    if (!c) return unknown('concept', id, '#concepts');
    const cats = {};
    c.langs.forEach(i => L[i].cats.forEach(k => { cats[k] = (cats[k] || 0) + 1; }));
    const catFilter = { id: 'lcat', label: 'Kind of language', options: [['', 'Any kind of language']].concat(Object.entries(cats).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, `${k.replace(/-/g, ' ')} (${n})`])),
      test: (r, v) => r.o >= 0 ? L[r.o].cats.includes(v) : (r.x.l || []).some(i => L[i].cats.includes(v)) };
    const lc = [0, 0, 0, 0];
    c.res.forEach(r => lc[r.lv]++);
    return [
      head('Concept · ' + c.cat, c.name, h('p', { class: 'summary' }, c.desc),
        c.aka.length ? h('p', { class: 'muted small' }, 'Also called: ' + c.aka.join(', ')) : null,
        h('p', { class: 'muted small row' }, `${plural(c.langs.size, 'language')} · ${plural(c.res.length, 'link')}`, mix(lc)),
        c.rel.length ? h('div', { class: 'row' }, h('span', { class: 'label' }, 'Often tagged together'), h('span', { class: 'chips' }, c.rel.map(([i, n]) => conceptChip(i, h('span', { class: 'faint' }, ' ' + n))))) : null),
      resPanel(c.res, { key: 'concept:' + c.id, group: 'language', groups: ['language', 'level', 'site', 'kind'], multi: true, filters: [catFilter] }),
    ];
  }

  // ---- lineage helpers ----
  function walk(start, dir, depth) {
    const seen = new Map([[start, 0]]);
    let frontier = [start];
    for (let d = 1; d <= depth; d++) {
      const next = [];
      for (const a of frontier) for (const b of (lang(a) ? (dir === 'up' ? lang(a).inf : lang(a).influenced) : [])) if (!seen.has(b)) { seen.set(b, d); next.push(b); }
      frontier = next;
    }
    seen.delete(start);
    return seen;
  }
  function neighbours(id) {
    const l = lang(id);
    return l ? [...new Set([...l.inf, ...l.influenced, ...l.rels.map(r => r[0])])].filter(x => lang(x)).sort() : [];
  }
  function findPath(a, b) {
    const prev = new Map([[a, null]]), queue = [a];
    while (queue.length) {
      const x = queue.shift();
      if (x === b) { const out = []; for (let y = x; y != null; y = prev.get(y)) out.push(y); return out.reverse(); }
      for (const y of neighbours(x)) if (!prev.has(y)) { prev.set(y, x); queue.push(y); }
    }
    return null;
  }
  function hop(a, b) {
    const la = lang(a), lb = lang(b);
    if (la.inf.includes(b)) return 'influenced by';
    if (lb.inf.includes(a)) return 'influenced';
    const r = la.rels.find(x => x[0] === b);
    return r ? r[1].replace(/-/g, ' ') : 'linked to';
  }
  const chain = p => h('div', { class: 'chain' }, p.map((id, i) => [i ? h('span', { class: 'hop' }, `— ${hop(p[i - 1], id)} →`) : null, h('span', { class: 'chip' }, langLink(id, true))]));

  function lineageGraph(focus, depth) {
    const CAP = 22, COLW = 196, W = 160, ROW = 27, TOP = 34;
    const up = walk(focus, 'up', depth), down = walk(focus, 'down', depth);
    const cols = [];
    for (let d = depth; d >= 1; d--) cols.push({ title: d === 1 ? 'Influenced by' : `${d} steps back`, ids: [...up].filter(x => x[1] === d).map(x => x[0]) });
    cols.push({ title: '', ids: [focus] });
    for (let d = 1; d <= depth; d++) cols.push({ title: d === 1 ? 'Influenced' : `${d} steps on`, ids: [...down].filter(x => x[1] === d).map(x => x[0]) });
    const live = cols.filter(c => c.ids.length);
    live.forEach(c => { c.ids.sort(byYear); c.more = Math.max(0, c.ids.length - CAP); c.ids = c.ids.slice(0, CAP); });
    const rows = Math.max(...live.map(c => c.ids.length + (c.more ? 1 : 0)));
    const width = live.length * COLW + 16, height = TOP + rows * ROW + 12;
    const svg = s('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `Influence graph around ${lang(focus).name}. The same connections are listed as text below.` });
    const edges = s('g'), nodes = s('g');
    const pos = new Map(), touching = new Map();
    live.forEach((c, ci) => c.ids.forEach((id, ri) => pos.set(id, { x: 8 + ci * COLW, y: TOP + ri * ROW + (rows - c.ids.length - (c.more ? 1 : 0)) * ROW / 2 })));
    for (let ci = 1; ci < live.length; ci++) for (const b of live[ci].ids) for (const a of live[ci - 1].ids) {
      if (!(lang(b) && lang(b).inf.includes(a))) continue;
      const p = pos.get(a), q = pos.get(b), x1 = p.x + W, y1 = p.y + 10, x2 = q.x, y2 = q.y + 10, mx = (x1 + x2) / 2;
      const path = s('path', { class: 'edge', d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}` });
      edges.append(path);
      [a, b].forEach(k => (touching.get(k) || touching.set(k, []).get(k)).push(path));
    }
    live.forEach((c, ci) => {
      if (c.title) nodes.append(s('text', { class: 'colhead', x: 8 + ci * COLW, y: 18 }, c.title + (c.more ? ` (${c.ids.length + c.more})` : '')));
      c.ids.forEach(id => {
        const l = lang(id), p = pos.get(id), name = l ? l.name : id, max = l && l.year ? 17 : 22, short = name.length > max ? name.slice(0, max - 1) + '…' : name;
        const g = s('g', { class: 'node' + (id === focus ? ' focus' : l ? ' link' : ' ghost'), transform: `translate(${p.x},${p.y})` },
          s('title', null, l ? `${l.name}${l.year ? ' (' + l.year + ')' : ''}` : `${id}: not in the catalog`),
          s('rect', { width: W, height: 20, rx: 4 }), s('text', { x: 7, y: 14 }, short), l && l.year ? s('text', { class: 'yr', x: W - 6, y: 14, 'text-anchor': 'end' }, String(l.year)) : null);
        if (l && id !== focus) {
          g.setAttribute('tabindex', '0'); g.setAttribute('role', 'link');
          g.addEventListener('click', () => go('lineage-' + id));
          g.addEventListener('keydown', e => { if (e.key === 'Enter') go('lineage-' + id); });
        }
        const hot = on => { g.classList.toggle('hot', on); (touching.get(id) || []).forEach(e => e.classList.toggle('hot', on)); };
        g.addEventListener('mouseenter', () => hot(true)); g.addEventListener('mouseleave', () => hot(false));
        g.addEventListener('focus', () => hot(true)); g.addEventListener('blur', () => hot(false));
        nodes.append(g);
      });
      if (c.more) nodes.append(s('text', { class: 'colhead', x: 8 + ci * COLW, y: TOP + c.ids.length * ROW + 14 }, `+ ${c.more} more, listed below`));
    });
    svg.append(edges, nodes);
    return { el: h('div', { class: 'graph' }, svg), up, down };
  }

  function viewLineage(arg) {
    const st = ui.lineage;
    const l = lang(arg || 'c') || L[0];
    if (arg && !lang(arg)) return unknown('language', arg, '#languages');
    const g = lineageGraph(l.id, st.depth);
    const listed = (map, d) => [...map].filter(x => x[1] === d).map(x => x[0]).sort(byYear);
    const target = st.to && lang(st.to) && st.to !== l.id ? st.to : '';
    const p = target ? findPath(l.id, target) : null;
    const rels = new Map();
    l.rels.forEach(([o, rel]) => { (rels.get(rel) || rels.set(rel, []).get(rel)).push(o); });
    const steps = (map, label) => { const out = []; for (let d = 1; d <= st.depth; d++) { const ids = listed(map, d); if (ids.length) out.push(h('dt', null, d === 1 ? label : `${label}, ${d} steps`), h('dd', null, ids.map((x, i) => [i ? ', ' : '', langLink(x, true)]))); } return out; };
    return [
      head('Lineage', l.name, h('p', { class: 'muted' }, 'Influence runs left to right. Select a language to move the focus to it.')),
      h('div', { class: 'toolbar' }, langPicker('Focus on another language…', id => go('lineage-' + id), 'lin-focus'),
        h('span', { class: 'row' }, h('span', { class: 'small muted' }, 'Depth'), [1, 2, 3].map(d => h('button', { 'aria-pressed': String(st.depth === d), onclick: () => { st.depth = d; render(); } }, String(d)))),
        h('a', { href: '#lang-' + l.id }, `Open ${l.name}`)),
      g.up.size + g.down.size ? g.el : empty(`No influence links are recorded for ${l.name}.`),
      h('section', { class: 'panel stack' }, h('h2', null, 'The same connections as text'), h('dl', { class: 'facts' }, steps(g.up, 'Influenced by'), steps(g.down, 'Influenced'),
        [...rels].map(([rel, ids]) => [h('dt', null, rel.replace(/-/g, ' ').replace(/^./, c => c.toUpperCase())), h('dd', null, [...new Set(ids)].map((x, i) => [i ? ', ' : '', langLink(x, true)]))]))),
      h('section', { class: 'panel stack' }, h('h2', null, `How is ${l.name} connected to…`), langPicker('Another language…', id => { st.to = id; render(); }, 'lin-to'),
        target ? (p ? chain(p) : h('p', { class: 'muted' }, `No chain of influence or family links joins ${l.name} and ${lang(target).name}.`)) : h('p', { class: 'muted small' }, 'Pick a second language to see the shortest chain of influence and family links between the two.')),
    ];
  }

  function viewCompare(arg) {
    const st = ui.compare;
    const ids = [...new Set((arg || '').split('--').filter(lang))].slice(0, 6);
    const set = next => go(next.length ? 'compare-' + next.join('--') : 'compare');
    const top = [
      head(null, 'Compare languages'),
      h('div', { class: 'toolbar' }, ids.map(id => h('span', { class: 'chip' }, lang(id).name, ' ', h('button', { class: 'quiet', 'aria-label': `Remove ${lang(id).name}`, onclick: () => set(ids.filter(x => x !== id)) }, '×'))),
        ids.length < 6 ? langPicker(ids.length ? 'Add a language…' : 'Pick the first language…', id => set([...ids, id]), 'cmp-add') : h('span', { class: 'muted small' }, 'Six is the most that fits side by side.')),
    ];
    if (ids.length < 2) {
      return top.concat(empty('Pick at least two languages to see their concept coverage side by side.'),
        h('p', { class: 'muted' }, 'For example: ', [['rust--go--zig', 'Rust, Go, Zig'], ['haskell--ocaml--standard-ml', 'Haskell, OCaml, Standard ML'], ['json--yaml--toml', 'JSON, YAML, TOML'], ['sql--datalog--sparql', 'SQL, Datalog, SPARQL']]
          .filter(([k]) => k.split('--').every(lang)).map(([k, t], i) => [i ? ' · ' : '', h('a', { href: '#compare-' + k }, t)])));
    }
    const ls = ids.map(lang);
    const cov = ls.map(l => { const m = new Map(); l.res.forEach(r => r.c.forEach(c => (m.get(c) || m.set(c, []).get(c)).push(r))); return m; });
    const fact = (label, f) => h('tr', null, h('td', { class: 'faint' }, label), ls.map(l => h('td', null, f(l))));
    const facts = h('div', { class: 'tablewrap' }, h('table', { class: 'matrix' }, h('thead', null, h('tr', null, h('th', null, ''), ls.map(l => h('th', { class: 'lang' }, h('a', { href: '#lang-' + l.id }, l.name))))),
      h('tbody', null, fact('First appeared', l => l.year || '—'), fact('Status', l => l.status), fact('Kind', l => l.cats.join(', ').replace(/-/g, ' ')), fact('Paradigms', l => l.par.join(', ')),
        fact('Typing', l => l.typ.join(', ')), fact('Defined by', l => l.def.join(', ').replace(/-/g, ' ')), fact('Designers', l => l.des.join(', ')),
        fact('Links by level', l => [mix(l.lc), h('div', { class: 'small faint num' }, l.lc.map((n, i) => `L${i} ${n}`).join(' · '))]))));
    const paths = [];
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) { const p = findPath(ids[i], ids[j]); if (p) paths.push(chain(p)); }
    const anc = ids.map(id => walk(id, 'up', 2));
    const common = [...anc[0].keys()].filter(x => anc.every(m => m.has(x)) && lang(x)).sort(byYear);

    const body = h('tbody'), info = h('span', { class: 'muted small num' });
    function draw() {
      const rows = [];
      let shown = 0;
      for (const cat of D.conceptCats) {
        const part = [];
        for (const c of C) {
          if (c.cat !== cat.id) continue;
          const cells = cov.map(m => (m.get(c.i) || []).filter(r => st.lv[r.lv]));
          const have = cells.filter(x => x.length).length;
          if (!have || (st.mode === 'shared' && have < ids.length) || (st.mode === 'diff' && have === ids.length)) continue;
          const open = st.open.has(c.id);
          part.push(h('tr', { class: open ? 'open' : '' }, h('td', null, h('button', { class: 'rowbtn', 'aria-expanded': String(open), title: c.name + ' — show the links', onclick: () => { open ? st.open.delete(c.id) : st.open.add(c.id); draw(); } }, (open ? '▾ ' : '▸ ') + c.id)),
            cells.map(rs => h('td', { class: 'cell' }, rs.length ? [...new Set(rs.map(r => r.lv))].sort().map(i => lv(i)) : h('span', { class: 'faint' }, '—')))));
          if (open) part.push(h('tr', { class: 'detail' }, h('td', null, h('a', { href: '#concept-' + c.id }, 'All languages →'), h('div', { class: 'small muted' }, c.desc)),
            cells.map(rs => h('td', null, rs.length ? rs.slice().sort((a, b) => a.lv - b.lv).slice(0, 12).map(r => h('span', { style: 'display:flex;gap:6px;align-items:flex-start' }, lv(r.lv), ext(r.u, r.t))) : h('span', { class: 'faint small' }, 'Nothing tagged'),
              rs.length > 12 ? h('span', { class: 'faint small' }, `and ${rs.length - 12} more on the concept page`) : null))));
          shown++;
        }
        if (part.length) rows.push(h('tr', { class: 'cat' }, h('td', { colspan: ids.length + 1 }, `${cat.id} — ${cat.description}`)), ...part);
      }
      info.textContent = plural(shown, 'concept');
      body.replaceChildren(...rows);
      if (!rows.length) body.append(h('tr', null, h('td', { colspan: ids.length + 1 }, empty('No concept fits this filter. Switch back to “All concepts” or turn a level on.'))));
    }
    draw();
    const mode = (k, t) => h('button', { 'aria-pressed': String(st.mode === k), onclick: () => { st.mode = k; render(); } }, t);
    return top.concat(
      facts,
      paths.length || common.length ? h('section', { class: 'panel stack' }, h('h2', null, 'How they are connected'), paths,
        common.length ? h('div', { class: 'row' }, h('span', { class: 'label' }, 'Shared ancestry within two steps'), h('span', { class: 'chips' }, common.map(x => h('span', { class: 'chip' }, langLink(x, true))))) : null) : null,
      section('Concept coverage', h('p', { class: 'muted small' }, 'A badge means that language has at least one link at that level tagged with the concept. Open a row to read the links next to each other.'),
        h('div', { class: 'toolbar' }, mode('all', 'All concepts'), mode('shared', 'Covered by all'), mode('diff', 'Missing somewhere'),
          h('span', { class: 'row' }, [0, 1, 2, 3].map(i => h('button', { class: `lv lv${i} ${st.lv[i] ? '' : 'off'}`, 'aria-pressed': String(!!st.lv[i]), title: D.meta.levels[i].name, onclick: () => { st.lv[i] = st.lv[i] ? 0 : 1; render(); } }, `L${i} ${LEVEL_SHORT[i]}`))),
          h('button', { onclick: () => { st.open.clear(); draw(); } }, 'Close all rows'), info),
        h('div', { class: 'tablewrap' }, h('table', { class: 'matrix' }, h('thead', null, h('tr', null, h('th', null, 'Concept'), ls.map(l => h('th', { class: 'lang' }, l.name)))), body))));
  }

  function pagedTable(st, rows, headers, toRow, placeholder, id) {
    const body = h('tbody'), info = h('span', { class: 'muted small num' }), more = h('button', { onclick: () => { st.shown += PAGE; draw(); } }, `Show ${PAGE} more`);
    function draw() {
      const ts = terms(st.q), hit = rows.filter(r => ts.every(t => r.name.toLowerCase().includes(t)));
      info.textContent = `${num(hit.length)} of ${num(rows.length)}`;
      body.replaceChildren(...hit.slice(0, st.shown).map(toRow));
      if (!hit.length) body.append(h('tr', null, h('td', { colspan: headers.length }, empty('Nothing matches that search.'))));
      more.hidden = hit.length <= st.shown;
    }
    draw();
    return [h('div', { class: 'toolbar' }, h('input', { type: 'search', id, placeholder, 'aria-label': placeholder, value: st.q, oninput: e => { st.q = e.target.value; st.shown = PAGE; draw(); } }), info),
      h('div', { class: 'tablewrap' }, h('table', null, h('thead', null, h('tr', null, headers.map(([t, cls]) => h('th', { class: cls }, t)))), body)), h('div', null, more)];
  }

  function viewSites() {
    return [head(null, 'Sites', h('p', { class: 'summary muted' }, 'Where the material lives. Open a site to see every catalogued page on it, or follow the arrow to go there.')),
      pagedTable(ui.sites, SITES, [['Site'], ['Links', 'n'], ['Languages', 'n'], ['L0', 'n'], ['L1', 'n'], ['L2', 'n'], ['L3', 'n'], ['Mix']], x => h('tr', null,
        h('td', null, h('a', { href: '#site-' + x.slug, class: 'mono' }, x.name), ' ', ext('https://' + x.name + '/', '↗', 'faint')),
        h('td', { class: 'n' }, num(x.res.length)), h('td', { class: 'n' }, num(x.langs.size)), x.lc.map(n => h('td', { class: 'n' }, n ? num(n) : h('span', { class: 'faint' }, '·'))), h('td', null, mix(x.lc))), 'Filter by domain, e.g. w3.org…', 'sf-q')];
  }

  function viewSite(sl) {
    const x = siteBySlug[sl];
    if (!x) return unknown('site', sl, '#sites');
    const n = {};
    x.res.forEach(r => { if (r.o >= 0) n[r.o] = (n[r.o] || 0) + 1; });
    const topLangs = Object.entries(n).sort((a, b) => b[1] - a[1]).slice(0, 14);
    return [
      head('Site', x.name, h('div', { class: 'row' }, ext('https://' + x.name + '/', `Open ${x.name} ↗`), h('span', { class: 'muted small num' }, `${plural(x.res.length, 'link')} · ${plural(x.langs.size, 'language')}`), mix(x.lc)),
        topLangs.length > 1 ? h('div', { class: 'row' }, h('span', { class: 'label' }, 'Most links'), h('span', { class: 'chips' }, topLangs.map(([i, k]) => h('a', { class: 'chip', href: '#lang-' + L[i].id }, L[i].name, h('span', { class: 'faint' }, ' ' + k))))) : null),
      resPanel(x.res, { key: 'site:' + sl, group: 'language', groups: ['language', 'level', 'concept', 'kind'], multi: true, filters: [conceptFilter(x.res)] }),
    ];
  }

  function viewPeople() {
    const rows = [...PEOPLE.values()].sort((a, b) => (b.designed.length * 3 + b.authored.length) - (a.designed.length * 3 + a.authored.length) || a.name.localeCompare(b.name));
    return [head(null, 'People', h('p', { class: 'summary muted' }, 'Designers of languages and authors of catalogued papers, books and specifications. A person links the languages they worked on.')),
      pagedTable(ui.people, rows, [['Name'], ['Designed'], ['Links authored', 'n']], p => h('tr', null, h('td', null, h('a', { href: '#person-' + p.slug }, p.name)),
        h('td', { class: 'small' }, p.designed.slice().sort(byYear).slice(0, 10).map((id, i) => [i ? ', ' : '', langLink(id)]), p.designed.length > 10 ? ` and ${p.designed.length - 10} more` : ''),
        h('td', { class: 'n' }, p.authored.length ? num(p.authored.length) : h('span', { class: 'faint' }, '·'))), 'Find a person or organisation…', 'pf-q')];
  }

  function viewPerson(sl) {
    const p = personBySlug[sl];
    if (!p) return unknown('person', sl, '#people');
    const wrote = new Set(p.authored.filter(r => r.o >= 0).map(r => L[r.o].id));
    return [
      head('Person', p.name, h('p', { class: 'muted small num' }, [p.designed.length ? plural(p.designed.length, 'language') + ' designed' : null, p.authored.length ? plural(p.authored.length, 'link') + ' authored' : null].filter(Boolean).join(' · '))),
      p.designed.length ? section('Designed', h('div', { class: 'tablewrap' }, h('table', null, h('tbody', null, p.designed.slice().sort(byYear).map(id => h('tr', null, h('td', { class: 'n faint' }, yearOf(id) || '—'), h('td', null, langLink(id)), h('td', { class: 'small muted' }, lang(id).sum))))))) : null,
      wrote.size > 1 ? h('p', { class: 'muted small' }, 'Wrote about: ', [...wrote].sort(byYear).map((id, i) => [i ? ', ' : '', langLink(id)])) : null,
      p.authored.length ? section('Authored', resPanel(p.authored, { key: 'person:' + sl, group: 'year', groups: ['year', 'language', 'level', 'concept', 'kind'], multi: true })) : null,
    ];
  }

  function viewSaved() {
    const rows = [...saved].map(k => byKey.get(k)).filter(Boolean);
    const host = h('div', { class: 'stack' });
    let armed = false;
    const clear = h('button', { onclick: () => { if (!armed) { armed = true; clear.textContent = `Remove all ${rows.length}? Select again to confirm`; return; } saved.clear(); persist(); render(); } }, 'Clear the list');
    host.append(h('div', { class: 'toolbar' },
      h('button', { onclick: () => copy([...new Set(rows.map(r => r.u))].join('\n') + '\n', `${plural(rows.length, 'URL')}`, host) }, 'Copy URLs only'),
      h('button', { onclick: () => copy(JSON.stringify(rows.map(r => ({ owner: r.o >= 0 ? L[r.o].id : 'general/' + COLLS[-1 - r.o].id, level: r.lv, kind: r.kind, title: r.t, url: r.u, concepts: r.c.map(i => C[i].id) })), null, 1), `${plural(rows.length, 'link')} as JSON`, host) }, 'Copy as JSON'), clear));
    return [head(null, 'Reading list', h('p', { class: 'summary muted' }, 'Links you saved with ☆, kept in this browser. Copy the list as Markdown, URLs or JSON to hand it to a follow-up research task.')),
      rows.length ? [host, resPanel(rows, { key: 'saved', group: 'language', groups: ['language', 'level', 'concept', 'site', 'kind'], multi: true })] : empty('Nothing saved yet. Select ☆ next to any link, or “Save all” above a filtered list.')];
  }

  function viewSearch() {
    const q = ui.q.trim(), ts = terms(q);
    if (!ts.length) return [head(null, 'Search'), empty('Type in the search box above: a language, a concept, a person, a site or any words from a title.')];
    const all = (text, t = text.toLowerCase()) => ts.every(x => t.includes(x));
    const langs = L.filter(l => all([l.id, l.name, ...l.aka].join(' '))).sort((a, b) => (a.name.toLowerCase() === q.toLowerCase() ? -1 : 0) - (b.name.toLowerCase() === q.toLowerCase() ? -1 : 0) || b.res.length - a.res.length);
    const concepts = C.filter(c => all([c.id, c.name, ...c.aka].join(' ')));
    const people = [...PEOPLE.values()].filter(p => all(p.name)).sort((a, b) => b.designed.length + b.authored.length - a.designed.length - a.authored.length);
    const sites = SITES.filter(x => all(x.name));
    const links = R.filter(r => ts.every(t => hay(r).includes(t)));
    const group = (label, items, f, max) => items.length ? h('div', { class: 'row' }, h('span', { class: 'label' }, label), h('span', { class: 'chips' }, items.slice(0, max).map(f), items.length > max ? h('span', { class: 'faint small' }, `+${items.length - max} more`) : null)) : null;
    if (ui.panels.search && ui.panels.search.for !== q) delete ui.panels.search;
    const out = [head('Search', `“${q}”`),
      h('div', { class: 'stack' }, group('Languages', langs, l => h('a', { class: 'chip', href: '#lang-' + l.id }, l.name), 16), group('Concepts', concepts, c => conceptChip(c.i), 12),
        group('People', people, p => h('a', { class: 'chip', href: '#person-' + p.slug }, p.name), 10), group('Sites', sites, x => h('a', { class: 'chip mono', href: '#site-' + x.slug }, x.name), 10)),
      links.length ? resPanel(links, { key: 'search', group: 'language', groups: ['language', 'level', 'concept', 'site', 'kind'], multi: true }) : empty('No link title, URL, author or tag contains all of those words.')];
    if (ui.panels.search) ui.panels.search.for = q;
    return out;
  }

  // ---------- shell ----------
  const NAV = [['home', 'Overview'], ['languages', 'Languages'], ['concepts', 'Concepts'], ['compare', 'Compare'], ['lineage', 'Lineage'], ['sites', 'Sites'], ['people', 'People'], ['saved', 'Saved']];
  const SECTION = { lang: 'languages', concept: 'concepts', site: 'sites', person: 'people' };
  const VIEWS = { home: viewHome, languages: viewLanguages, lang: viewLang, concepts: viewConcepts, concept: viewConcept, compare: viewCompare, lineage: viewLineage, sites: viewSites, site: viewSite, people: viewPeople, person: viewPerson, saved: viewSaved, search: viewSearch };
  let main, nav, searchBox;
  function route() {
    let hsh = '';
    try { hsh = decodeURIComponent(location.hash.slice(1)); } catch (e) { hsh = ''; }
    const m = hsh.match(/^(lang|concept|compare|lineage|site|person)-(.+)$/);
    if (m) return { view: m[1], arg: m[2] };
    return { view: VIEWS[hsh] ? hsh : 'home', arg: '' };
  }
  function updateNav() {
    const r = route(), cur = SECTION[r.view] || r.view;
    nav.replaceChildren(...NAV.map(([k, t]) => h('a', { href: '#' + k, 'aria-current': k === cur ? 'page' : null }, k === 'saved' && saved.size ? `${t} (${saved.size})` : t)));
  }
  function render() {
    const r = route();
    main.replaceChildren(...[VIEWS[r.view](r.arg)].flat(Infinity).filter(Boolean));
    updateNav();
  }
  function start(data) {
    prepare(data);
    const root = document.getElementById('app');
    let timer;
    searchBox = h('input', { type: 'search', id: 'global-search', placeholder: 'Search languages, concepts, links…', 'aria-label': 'Search the whole catalog', oninput: e => {
      ui.q = e.target.value;
      clearTimeout(timer);
      timer = setTimeout(() => { if (route().view === 'search') render(); else go('search'); }, 220);
    } });
    nav = h('nav', { class: 'nav', 'aria-label': 'Sections' });
    main = h('main', { class: 'wrap' });
    root.replaceChildren(h('div', { class: 'bar' }, h('div', { class: 'bar-in' }, h('a', { class: 'brand', href: '#home' }, 'Language Literature Explorer'), nav, h('div', { class: 'search' }, searchBox))), main);
    window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
    render();
  }
  fetch('data.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(start).catch(err => {
    document.getElementById('app').replaceChildren(h('div', { class: 'wrap' }, h('h1', null, 'The catalog data did not load'),
      h('p', null, 'This page reads data.json from the same folder. Build it with “python3 tools/build_explorer.py”, then serve the explorer folder over HTTP (“python3 tools/q.py serve”); opening index.html straight from disk does not work.'),
      h('p', { class: 'muted small' }, String(err))));
  });
})();
