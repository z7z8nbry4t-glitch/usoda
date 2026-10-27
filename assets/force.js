/* USODA force page. Reads the same pre-aggregated files as the map; no individual records. */
(function () {
  'use strict';
  var C = window.UsodaCharts, fmt = C.fmt;
  var AGREE = {
    agree: 'police.uk and the Home Office agree within 5% for that year',
    minor_difference: 'police.uk and the Home Office differ by 5 to 10% for that year',
    differs: 'police.uk and the Home Office differ by more than 10% for that year',
    incomplete_months: 'police.uk has fewer than 12 months for that year, so no like-for-like check is possible',
    no_street_data: 'police.uk published no street-level rows for that year'
  };
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function get(f) { return fetch('data/' + f).then(function (r) { if (!r.ok) throw new Error(f + ' ' + r.status); return r.json(); }); }
  function opt(f) { return get(f).catch(function () { return null; }); }
  function pretty(s) { return s.split('-').map(function (w) { return w === 'and' ? w : w.charAt(0).toUpperCase() + w.slice(1); }).join(' '); }

  Promise.all([get('meta.json'), get('force_totals.json'), get('pfa.geojson'), opt('crossref.json'), opt('population.json'), opt('annotations.json'), opt('ni_validation.json')])
    .then(function (r) { render({ meta: r[0], ft: r[1], pfa: r[2], xref: r[3], pop: r[4], notes: r[5], ni: r[6] }); })
    .catch(function (e) { $('title').textContent = 'This page could not load'; $('body').textContent = e.message; });

  function names(d) {
    var n = {};
    d.pfa.features.forEach(function (f) { n[f.properties.slug] = f.properties.name; });
    n.btp = 'British Transport Police'; n['northern-ireland'] = 'Police Service of Northern Ireland';
    Object.keys(d.ft.monthly).forEach(function (s) { if (!n[s]) n[s] = pretty(s); });
    return n;
  }

  function render(d) {
    var nm = names(d), slug = new URLSearchParams(location.search).get('f');
    if (!slug || !d.ft.monthly[slug]) return list(d, nm);
    var fm = d.ft.monthly[slug], months = d.meta.months_available.map(function (m) { return m.month; }).sort();
    var name = nm[slug];
    document.title = name + ' | USODA';
    $('title').textContent = name;
    $('crumb').innerHTML = '<a href="force.html">Police force pages</a>';
    var h = '<p class="lead">Reported violence and sexual offences for this force. These are counts of reports, not the number of offences that happen, and they are not a measure of how safe a place is.</p>';

    // facts
    var facts = [], x = d.xref && d.xref.forces[slug], fy = x && Object.keys(x).sort().pop(), hx = fy && x[fy];
    if (hx) {
      facts.push([fmt(hx.home_office_sexual), 'sexual offences recorded in ' + fy + ' (Home Office), ' + fmt(hx.home_office_rape) + ' of them rape']);
      facts.push([hx.sexual_share_pct + '%', 'of violence and sexual offences in ' + fy + ' were sexual offences (force-wide)']);
      var p = d.pop && d.pop.forces[slug];
      if (slug === 'city-of-london') facts.push(['No rate', 'about 4,400 people live in the City of London, but many more work and visit, so a rate per resident would mislead']);
      else if (p && p.residents) facts.push([(hx.home_office_sexual / p.residents * 1000).toFixed(1), 'sexual offences per 1,000 residents in ' + fy + ' (Census 2021: ' + fmt(p.residents) + ' people; growing areas read slightly high)']);
    }
    var have = months.filter(function (m) { return fm[m] !== undefined; });
    var last12 = months.slice(-12).reduce(function (a, m) { return a + (fm[m] || 0); }, 0);
    var miss12 = months.slice(-12).filter(function (m) { return fm[m] === undefined; }).length;
    if (miss12 === 12) facts.push(['None', 'police.uk published no records for this force in the latest 12 months']);
    else facts.push([fmt(last12), 'police.uk records in the latest 12 months (' + (12 - miss12) + ' of 12 months published)']);
    facts.push([have.length + ' of ' + months.length, 'months of police.uk data published by this force since ' + months[0]]);
    h += '<ul class="facts-list">' + facts.map(function (f) { return '<li><strong>' + esc(f[0]) + '</strong><span>' + esc(f[1]) + '</span></li>'; }).join('') + '</ul>';

    // notes
    var n = d.notes && d.notes.forces[slug];
    if (n) h += '<p class="notice"><strong>Known issue.</strong> ' + esc(n.note) + ' <a href="' + esc(n.source) + '">Source</a>.</p>';
    if (hx) h += '<p class="small">Cross-check for ' + esc(fy) + ': ' + esc(AGREE[hx.agreement] || '') + '.</p>';
    var ls = d.meta.quality.force_location_share_pct;
    if (ls && ls[slug] !== undefined && ls[slug] < 96) h += '<p class="small">' + (100 - ls[slug]).toFixed(1) + '% of this force\'s records in the ten-year window have no location, so they are in its totals but in no map cell.</p>';
    if (slug === 'northern-ireland' && d.ni) {
      var ni = d.ni;
      h += '<p class="notice"><strong>Official check.</strong> The Police Service of Northern Ireland recorded ' + fmt(ni.psni.sexual_offences) + ' sexual offences (' + fmt(ni.psni.rape) + ' of them rape) and ' + fmt(ni.psni.violence_against_the_person) +
        ' violence against the person in ' + esc(ni.period) + '. police.uk holds ' + (100 * ni.ratio).toFixed(1) + '% of that violence-plus-sexual total. <a href="' + esc(ni.source_url) + '">Source</a>.</p>';
    }

    // charts
    var pts = months.map(function (m) { return { l: C.monthLabel(m), v: fm[m] === undefined ? null : fm[m], gap: true, tick: m.slice(5) === '01' ? m.slice(0, 4) : null }; });
    h += '<div class="chart">' + C.trendChart(pts, { colour: '#2171b5', title: 'Reported records by month', unit: 'Monthly count (police.uk, violence and sexual offences)', alt: C.trendAlt('monthly reported records for ' + name, pts), note: 'Red mark: no data published that month.' }) + '</div>';
    if (x) {
      var yrs = Object.keys(x).filter(function (k) { return /^\d{4}\/\d{2}$/.test(k) && x[k].home_office_sexual !== undefined; }).sort();
      var yp = yrs.map(function (y) { return { l: y, v: x[y].home_office_sexual, tick: y.slice(2, 4) + '-' + y.slice(5) }; });
      if (yp.length > 1) h += '<div class="chart">' + C.trendChart(yp, { colour: '#08306b', title: 'Home Office sexual offences by financial year', unit: 'Annual count (Home Office; sexual offences only; a different measure from the monthly chart)', alt: C.trendAlt('annual Home Office sexual offences for ' + name, yp), note: 'Earliest year available to this atlas: ' + yrs[0] + '.' }) + '</div>';
    }
    h += '<p class="cta"><a class="btn" href="atlas.html#f=' + encodeURIComponent(slug) + '">Show on the map</a> <a class="btn ghost" href="data/downloads/force_monthly_police_uk.csv">Download monthly figures (CSV)</a></p>';
    h += '<section class="important"><h2>Read this before using these figures</h2><p>Counts reflect recording practice and willingness to report as well as what happened, and the two sources have different definitions: police.uk combines sexual offences with all other violence, while the Home Office separates them. The sources are shown side by side and are never added together. Do not use this page to rank forces or to judge how safe an area is.</p></section>';
    $('body').innerHTML = h;
  }

  function list(d, nm) {
    document.title = 'Police force pages | USODA';
    $('title').textContent = 'Police force pages';
    var slugs = Object.keys(nm).filter(function (s) { return d.ft.monthly[s]; }).sort(function (a, b) { return nm[a].localeCompare(nm[b]); });
    $('body').innerHTML = '<p class="lead">One page for each force that publishes to police.uk, with monthly records, Home Office sexual offences by year, data gaps and notes. Pages are in alphabetical order, not ranked.</p><ul class="forcelist">' +
      slugs.map(function (s) { return '<li><a href="force.html?f=' + encodeURIComponent(s) + '">' + esc(nm[s]) + '</a></li>'; }).join('') + '</ul>';
  }
})();
