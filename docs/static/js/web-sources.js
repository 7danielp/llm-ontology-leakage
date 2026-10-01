(function() {
  const box = document.getElementById('web-sources');
  if (!box) return;
  const fail = () => { box.querySelector('.ws-panel').textContent = 'The chart could not be loaded.'; };
  if (!window.d3) return fail();
  const TIERS = ['popular', 'medium', 'unpopular', 'synthetic'];
  const SIGNIFICANT = 0.03, TOP_PAGES = 6, TOP_OTHER = 25;

  function fromTable(rows) {
    const sites = new Map();
    rows.forEach(r => {
      const key = r.tier + '\t' + r.ontology + '\t' + r.domain;
      let s = sites.get(key);
      if (!s) sites.set(key, s = { tier: r.tier, ontology: r.ontology, domain: r.domain, count: 0, search: 0, opened: 0, pages: [] });
      s.count += +r.count; s.search += +r['search results']; s.opened += +r['opened pages'];
      s.pages.push([r.page, +r.count]);
    });
    const all = [...sites.values()];
    const children = TIERS.map(tier => ({
      name: tier[0].toUpperCase() + tier.slice(1),
      children: [...new Set(all.filter(s => s.tier === tier).map(s => s.ontology))].sort().map(onto => {
        const ws = all.filter(s => s.tier === tier && s.ontology === onto)
          .sort((a, b) => b.count - a.count || (a.domain < b.domain ? -1 : a.domain > b.domain ? 1 : 0));
        const total = d3.sum(ws, s => s.count);
        const big = ws.filter(s => s.count / total >= SIGNIFICANT), small = ws.filter(s => s.count / total < SIGNIFICANT);
        const kids = big.map(s => ({ name: s.domain, value: s.count, search: s.search, opened: s.opened, pages: s.pages.slice(0, TOP_PAGES) }));
        if (small.length) kids.push({ name: `${small.length} other websites`, other: true, value: d3.sum(small, s => s.count),
          search: d3.sum(small, s => s.search), opened: d3.sum(small, s => s.opened), websites: small.slice(0, TOP_OTHER).map(s => [s.domain, s.count]) });
        return { name: onto, websites: ws.length, children: kids };
      }),
    }));
    return { name: 'All 12 ontologies', children, significant: SIGNIFICANT,
             documents: d3.sum(all, s => s.count), websites: new Set(all.map(s => s.domain)).size };
  }

  d3.csv(box.dataset.table).then(rows => draw(fromTable(rows)), fail);

  function draw(DATA) {
  const SHORT = { 'Dublin Core Terms': 'DC Terms', 'NEPOMUK File Ontology': 'NFO', 'W3C Organization Ontology': 'W3C Org',
                  'Urban IoT Electric Mobility': 'Urban IoT', 'Waste Management': 'Waste Mgmt.', 'Weather Patterns': 'Weather', 'Coffee Brewing': 'Coffee' };
  const TIER_KEY = { Popular: 'popular', Medium: 'medium', Unpopular: 'unpopular', Synthetic: 'synthetic' };
  const fmt = d3.format(',');
  const share = v => v > 0 && v < 0.005 ? '<0.01' : v.toFixed(2);
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const q = sel => box.querySelector(sel);

  DATA.children.forEach((t, i) => { t._i = i; });
  const root = d3.hierarchy(DATA).sum(d => d.children ? 0 : d.value)
    .sort((a, b) => a.depth === 1 ? a.data._i - b.data._i : ((a.data.other ? 1 : 0) - (b.data.other ? 1 : 0)) || (b.value - a.value));
  d3.partition().size([1, root.height + 1])(root);
  const nodes = root.descendants().slice(1);

  const R = 300, R0 = 74;
  let M = 165, W = 2 * (R + M), narrow = false;
  const svg = d3.select(q('svg'));
  function layout() {
    narrow = box.clientWidth < 600;
    M = narrow ? 14 : 165; W = 2 * (R + M);
    svg.attr('viewBox', [-W / 2, -W / 2, W, W]);
  }
  layout();
  const gArcs = svg.append('g'), gIn = svg.append('g'), gOut = svg.append('g'), center = svg.append('g');
  const centerCircle = center.append('circle').attr('r', R0 - 4).attr('class', 'center-hit');
  const cName = center.append('text').attr('text-anchor', 'middle').style('font-weight', 700);
  const cNum = center.append('text').attr('text-anchor', 'middle');
  const cHint = center.append('text').attr('text-anchor', 'middle');
  let focus = root, selected = null, moving = false;

  const token = name => getComputedStyle(box).getPropertyValue(name).trim();
  const tierOf = d => d.ancestors().find(a => a.depth === 1);
  function colour(d) {
    const bg = token('--ws-bg');
    if (d.data.other) return d3.interpolateRgb(token('--ws-other'), bg)(0.35);
    const base = token('--ws-' + TIER_KEY[tierOf(d).data.name]);
    return d.depth === 1 ? base : d3.interpolateRgb(base, bg)(d.depth === 2 ? 0.3 : 0.56);
  }
  const label = d => d.depth === 2 ? (SHORT[d.data.name] || d.data.name) : d.data.name;
  const pathOf = d => d.ancestors().reverse().slice(1).map(a => a.data.name);
  const textSize = () => Math.max(11, Math.min(narrow ? 26 : 18, 11 * W / Math.max(300, svg.node().getBoundingClientRect().width)));

  function geometry(d, f) {
    const rings = root.height - f.depth, w = (R - R0) / rings, rel = d.depth - f.depth;
    if (!(rel > 0 && d.ancestors().includes(f))) {
      const a = d.x0 < f.x0 ? 0 : 2 * Math.PI, r = R0 + Math.max(0, Math.min(rings, rel) - 1) * w;
      return { a0: a, a1: a, r0: r, r1: r, show: false, outer: false };
    }
    const span = f.x1 - f.x0;
    return { a0: (d.x0 - f.x0) / span * 2 * Math.PI, a1: (d.x1 - f.x0) / span * 2 * Math.PI,
             r0: R0 + (rel - 1) * w, r1: R0 + rel * w, show: true, outer: rel === rings };
  }
  nodes.forEach(d => { d.current = geometry(d, root); });

  const arc = d3.arc().startAngle(g => g.a0).endAngle(g => g.a1)
    .padAngle(g => Math.min((g.a1 - g.a0) / 2, 0.003)).padRadius(R)
    .innerRadius(g => g.r0).outerRadius(g => Math.max(g.r0, g.r1 - 1.5));

  const segs = gArcs.selectAll('path').data(nodes).join('path')
    .attr('class', 'seg').attr('d', d => arc(d.current)).attr('role', 'button')
    .attr('aria-label', d => `${fmt(d.value)} documents in ${pathOf(d).join(', ')}`)
    .on('click', (e, d) => activate(d, false))
    .on('keydown', (e, d) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(d, true); } })
    .on('pointermove', (e, d) => showTip(e, d)).on('pointerleave', hideTip);
  function access(geo) {
    segs.attr('tabindex', d => geo(d).show && d.children ? 0 : -1)
      .attr('aria-hidden', d => geo(d).show ? null : 'true')
      .style('pointer-events', d => geo(d).show ? null : 'none');
  }
  access(d => d.current);
  centerCircle.on('click', () => { if (focus.parent) { selected = null; zoom(focus.parent, false); } });

  function focusPanel() { const h = q('.ws-panel h4'); if (h) h.focus({ preventScroll: true }); }

  function activate(d, fromKeyboard) {
    if (!d.current.show) return;
    if (d.children) { selected = null; zoom(d, fromKeyboard); return; }
    selected = d; segs.classed('sel', s => s === selected); renderPanel(d);
    if (fromKeyboard) focusPanel();
  }

  function zoom(f, fromKeyboard) {
    focus = f; hideTip();
    nodes.forEach(d => { d.target = geometry(d, f); });
    gIn.selectAll('*').remove(); gOut.selectAll('*').remove();
    access(d => d.target);
    moving = true;
    segs.classed('sel', s => s === selected)
      .transition().duration(reduce.matches ? 0 : 650)
      .attrTween('d', d => { const i = d3.interpolate(d.current, d.target); return u => arc(d.current = i(u)); })
      .end().then(() => { moving = false; drawLabels(); }, () => {});
    drawCenter(); renderCrumbs(); renderPanel(selected || focus);
    if (fromKeyboard) focusPanel();
  }

  function drawCenter() {
    const k = narrow ? Math.min(1.8, textSize() / 11) : 1;
    cName.text(focus === root ? 'All 12' : label(focus)).attr('fill', token('--ws-fg')).attr('y', -6 * k).style('font-size', 15 * k + 'px');
    cNum.text(fmt(focus.value) + (narrow ? '' : ' documents')).attr('fill', token('--ws-muted')).attr('y', 13 * k).style('font-size', 13 * k + 'px');
    cHint.text(focus.parent && !narrow ? 'click to zoom out' : '').attr('fill', token('--ws-muted')).attr('y', 30 * k).style('font-size', 11 * k + 'px');
    centerCircle.classed('up', !!focus.parent);
  }

  function variants(name) {
    const out = [[name]];
    const m = name.match(/^(\S+) (.+)$/) || name.match(/^(.+?)(\.[^.]+)$/) || name.match(/^([A-Z]?[a-z]+)([A-Z].*)$/);
    if (m) out.push([m[1], m[2]]);
    if (name.length > 8) out.push([name.slice(0, 7).replace(/[. ]+$/, '') + '.']);
    return out;
  }

  function innerLabel(d, size, fg, onTier) {
    const g = d.current, mid = (g.a0 + g.a1) / 2, r = (g.r0 + g.r1) / 2, deg = mid * 180 / Math.PI;
    const ring = g.r1 - g.r0 - 8, arcLen = (g.a1 - g.a0) * r - 8, name = label(d);
    const tries = variants(name).map(lines => [lines, false]);
    for (const [lines, along] of tries) {
      const t = gIn.append('text').attr('text-anchor', 'middle').attr('fill', d.depth === 1 ? onTier : fg)
        .style('font-size', size + 'px').style('font-weight', d.depth === 1 ? 700 : 600)
        .attr('transform', along ? `rotate(${deg}) translate(0,${-r}) rotate(${deg > 90 && deg < 270 ? 180 : 0})`
                                 : `rotate(${deg - 90}) translate(${r},0) rotate(${deg < 180 ? 0 : 180})`);
      lines.forEach((ln, i) => t.append('tspan').attr('x', 0).attr('dy', i ? '1.2em' : `${0.35 - 0.6 * (lines.length - 1)}em`).text(ln));
      const w = Math.max(...t.selectAll('tspan').nodes().map(n => n.getComputedTextLength())), h = lines.length * size * 1.2;
      if (along ? (w <= arcLen && h <= ring) : (w <= ring && h <= arcLen)) return;
      t.remove();
    }
  }

  function drawLabels() {
    gIn.selectAll('*').remove(); gOut.selectAll('*').remove();
    const fg = token('--ws-fg'), onTier = token('--ws-on-tier'), size = textSize();
    nodes.filter(d => d.current.show && !d.current.outer).forEach(d => innerLabel(d, size, fg, onTier));
    if (narrow) return;
    nodes.filter(d => d.current.show && d.current.outer).forEach(d => {
      const g = d.current, deg = (g.a0 + g.a1) / 2 * 180 / Math.PI;
      if ((g.a1 - g.a0) * R < size * 0.95) return;
      const right = deg < 180;
      gOut.append('text').text(d.data.other ? d.data.name.replace(' other websites', ' others') : d.data.name)
        .attr('fill', d.data.other ? token('--ws-muted') : fg).style('font-size', size + 'px')
        .attr('text-anchor', right ? 'start' : 'end').attr('dy', '0.35em')
        .attr('transform', `rotate(${deg - 90}) translate(${R + 7},0) rotate(${right ? 0 : 180})`);
    });
  }

  const tip = q('.ws-tip'), wrap = q('.ws-chart');
  function showTip(e, d) {
    const parent = d.parent;
    tip.innerHTML = '';
    const b = document.createElement('b'); b.textContent = d.data.name;
    const p = document.createElement('span'); p.textContent = pathOf(d).slice(0, -1).join(' › ') || 'All ontologies';
    tip.append(b, p, document.createElement('br'), `${fmt(d.value)} documents, ${share(d.value / parent.value)} of ${parent === root ? 'all' : label(parent)}`);
    if (parent !== root) tip.append(`, ${share(d.value / root.value)} of all`);
    tip.hidden = false;
    const rect = wrap.getBoundingClientRect();
    let x = e.clientX - rect.left + 14;
    if (x + tip.offsetWidth > rect.width) x = e.clientX - rect.left - tip.offsetWidth - 10;
    tip.style.left = Math.max(0, x) + 'px'; tip.style.top = (e.clientY - rect.top + 14) + 'px';
  }
  function hideTip() { tip.hidden = true; }

  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function link(text, href) { const a = el('a', null, text); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
  function stats(pairs) {
    const dl = el('dl', 'ws-stats');
    pairs.forEach(([k, v]) => { const div = el('div'); div.append(el('dt', null, k), el('dd', null, v)); dl.append(div); });
    return dl;
  }
  function onKey(node, fn) {
    node.tabIndex = 0; node.setAttribute('role', 'button');
    node.addEventListener('click', () => fn(false));
    node.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(true); } });
  }

  function renderCrumbs() {
    const nav = q('.ws-crumbs'); nav.innerHTML = '';
    focus.ancestors().reverse().forEach((a, i, all) => {
      if (i) nav.append(el('span', 'sep', '›'));
      const btn = el('button', null, a === root ? 'All ontologies' : a.data.name); btn.type = 'button';
      if (i === all.length - 1) btn.setAttribute('aria-current', 'true');
      else btn.addEventListener('click', e => { selected = null; zoom(a, e.detail === 0); });
      nav.append(btn);
    });
  }

  function renderPanel(d) {
    const panel = q('.ws-panel'); panel.innerHTML = '';
    const heading = el('h4'); heading.tabIndex = -1;
    if (d.children) {
      heading.textContent = d === root ? 'All 12 ontologies' : d.data.name;
      panel.append(heading);
      if (d !== root) panel.append(el('p', 'ws-path', pathOf(d).slice(0, -1).join(' › ')));
      const third = d === root ? ['websites', fmt(DATA.websites)] : d.depth === 1 ? ['ontologies', fmt(d.children.length)] : ['websites', fmt(d.data.websites)];
      panel.append(stats([['documents', fmt(d.value)], ['share of all', share(d.value / root.value)], third]));
      panel.append(el('h5', null, d.depth === 0 ? 'Tiers' : d.depth === 1 ? 'Ontologies' : 'Websites'));
      const ul = el('ul', 'ws-rows');
      d.children.forEach(c => {
        const li = el('li'), sw = el('span', 'ws-sw'); sw.style.background = colour(c);
        const bar = el('span', 'bar'), fill = el('i'); fill.style.width = (100 * c.value / d.value) + '%'; fill.style.background = colour(c); bar.append(fill);
        li.append(sw, el('span', 'name', c.data.name), el('span', 'num', `${fmt(c.value)} · ${share(c.value / d.value)}`), el('span'), bar);
        onKey(li, kb => activate(c, kb));
        ul.append(li);
      });
      panel.append(ul);
      return;
    }
    const onto = d.parent;
    const back = el('button', 'ws-back', '‹ Back to ' + label(onto)); back.type = 'button';
    back.addEventListener('click', e => {
      selected = null; segs.classed('sel', false);
      if (focus === onto) { renderPanel(onto); if (e.detail === 0) focusPanel(); } else zoom(onto, e.detail === 0);
    });
    const pages = d.data.pages || [];
    if (d.data.other || !pages.length) heading.textContent = d.data.name;
    else { const first = pages.find(([u]) => /^https?:\/\//.test(u)); heading.append(first ? link(d.data.name, new URL(first[0]).origin) : document.createTextNode(d.data.name)); }
    panel.append(back, heading, el('p', 'ws-path', pathOf(d).slice(0, -1).join(' › ')));
    panel.append(stats([['documents', fmt(d.value)], ['share of ' + label(onto), share(d.value / onto.value)], ['opened pages', fmt(d.data.opened)]]));
    const ul = el('ul', 'ws-urls');
    if (d.data.other) {
      panel.append(el('h5', null, `Largest of the ${d.data.name}`));
      d.data.websites.forEach(([name, n]) => { const li = el('li'); li.append(el('span', null, name), el('span', 'num', fmt(n))); ul.append(li); });
      panel.append(ul);
      const total = parseInt(d.data.name, 10);
      if (d.data.websites.length < total) panel.append(el('p', 'ws-path', `and ${total - d.data.websites.length} smaller websites`));
    } else {
      panel.append(el('h5', null, 'Most returned pages'));
      pages.forEach(([url, n]) => {
        const li = el('li');
        if (/^https?:\/\//.test(url)) { const a = link(url.replace(/^https?:\/\/(www\.)?/, ''), url); a.title = url; li.append(a); }
        else li.append(el('span', null, url));
        li.append(el('span', 'num', fmt(n))); ul.append(li);
      });
      panel.append(ul);
    }
  }

  function renderLegend() {
    const legend = q('.ws-legend'); legend.innerHTML = '';
    root.children.forEach(t => {
      const li = el('li'), sw = el('span', 'ws-sw'); sw.style.background = colour(t);
      li.append(sw, document.createTextNode(`${t.data.name} (${share(t.value / root.value)})`)); legend.append(li);
    });
    const li = el('li'), sw = el('span', 'ws-sw'); sw.style.background = colour(nodes.find(n => n.data.other));
    li.append(sw, document.createTextNode('grouped small websites')); legend.append(li);
  }

  segs.attr('fill', colour);
  renderLegend(); drawCenter(); drawLabels(); renderCrumbs(); renderPanel(root);
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const was = narrow; layout();
      if (was !== narrow) drawCenter();
      if (!moving) { drawCenter(); drawLabels(); }
    }, 150);
  });
  }
})();
