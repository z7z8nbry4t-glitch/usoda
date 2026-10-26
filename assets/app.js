/* USODA front end. Pre-aggregated static data only; no individual records. */
(function () {
  'use strict';

  var DATA = 'data/';
  var CLASS_COLOURS = ['#ffffb2', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#b10026'];
  var CLASS_QUANTILES = [0.5, 0.7, 0.85, 0.93, 0.97, 0.99];
  var SCOT_COLOURS = ['#f2f0f7', '#dadaeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486'];
  var PFA_COLOURS = ['#eff3ff', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594'];
  var HOTSPOT_Q = 0.97;
  var INCOMPLETE = 0.9; // a force with < 90% of window months is flagged as incomplete

  var S = {
    meta: null, forceTotals: null, pfa: null, pfaIndex: [], scotData: null, scotGeo: null, xref: null,
    win: '10y', month: null,
    cells: [], breaks: [], sortedCounts: [], rangeIds: [],
    cache: {}
  };

  var $ = function (id) { return document.getElementById(id); };
  var fmt = function (n) { return Number(n).toLocaleString('en-GB'); };

  // ---------------------------------------------------------------- map
  var map = L.map('map', { center: [54.4, -2.6], zoom: 6, minZoom: 5, zoomSnap: 0.5, worldCopyJump: false });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Crime data: data.police.uk (OGL v3.0)'
  }).addTo(map);
  map.createPane('scot');
  map.getPane('scot').style.zIndex = 375;
  map.createPane('pfa');
  map.getPane('pfa').style.zIndex = 380;
  var canvas = L.canvas({ padding: 0.5 });
  var heat = null, hexGroup = L.layerGroup(), pfaGroup = L.layerGroup(), scotGroup = L.layerGroup();

  // ---------------------------------------------------------------- hex geometry (mirrors scripts/usoda_common.py)
  var G = { R: 0.02, K: Math.cos(54.5 * Math.PI / 180) };
  var SQ3 = Math.sqrt(3);
  function hexCenter(q, r) {
    var x = G.R * SQ3 * (q + r / 2), y = G.R * 1.5 * r;
    return [y, x / G.K]; // lat, lng
  }
  function hexRing(q, r) {
    var c = hexCenter(q, r), x0 = c[1] * G.K, y0 = c[0], ring = [];
    for (var i = 0; i < 6; i++) {
      var a = (60 * i + 30) * Math.PI / 180;
      ring.push([y0 + G.R * Math.sin(a), (x0 + G.R * Math.cos(a)) / G.K]);
    }
    return ring;
  }

  // ---------------------------------------------------------------- helpers
  function monthRange(from, to) {
    var out = [], y = +from.slice(0, 4), m = +from.slice(5, 7), ey = +to.slice(0, 4), em = +to.slice(5, 7);
    while (y < ey || (y === ey && m <= em)) {
      out.push(y + '-' + (m < 10 ? '0' : '') + m);
      m++; if (m > 12) { m = 1; y++; }
    }
    return out;
  }
  function getJSON(path) {
    if (S.cache[path]) return Promise.resolve(S.cache[path]);
    return fetch(DATA + path, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(path + ' ' + r.status);
      return r.json();
    }).then(function (j) { S.cache[path] = j; return j; });
  }
  function quantile(sorted, p) {
    if (!sorted.length) return 0;
    return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  }
  function classOf(n) {
    var i = 0;
    while (i < S.breaks.length && n >= S.breaks[i]) i++;
    return i;
  }
  function prettySlug(s) {
    return s.replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }
  function forceName(slug) {
    for (var i = 0; i < S.pfaIndex.length; i++) if (S.pfaIndex[i].slug === slug) return S.pfaIndex[i].name;
    if (slug === 'btp') return 'British Transport Police';
    if (slug === 'northern-ireland') return 'Police Service of Northern Ireland';
    return prettySlug(slug);
  }

  // ---------------------------------------------------------------- force-area lookup (point in polygon)
  function buildPfaIndex(gj) {
    S.pfaIndex = gj.features.map(function (f) {
      var polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
      var minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
      polys.forEach(function (p) { p[0].forEach(function (c) {
        if (c[0] < minx) minx = c[0]; if (c[0] > maxx) maxx = c[0];
        if (c[1] < miny) miny = c[1]; if (c[1] > maxy) maxy = c[1];
      }); });
      return { slug: f.properties.slug, name: f.properties.name, code: f.properties.code, polys: polys, bbox: [minx, miny, maxx, maxy] };
    });
  }
  function inRing(x, y, ring) {
    var inside = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }
  function forceAt(lat, lng) {
    for (var i = 0; i < S.pfaIndex.length; i++) {
      var f = S.pfaIndex[i], b = f.bbox;
      if (lng < b[0] || lng > b[2] || lat < b[1] || lat > b[3]) continue;
      for (var p = 0; p < f.polys.length; p++) {
        if (!inRing(lng, lat, f.polys[p][0])) continue;
        var hole = false;
        for (var h = 1; h < f.polys[p].length; h++) if (inRing(lng, lat, f.polys[p][h])) { hole = true; break; }
        if (!hole) return f.slug;
      }
    }
    if (lat > 53.9 && lat < 55.5 && lng > -8.3 && lng < -5.3) return 'northern-ireland';
    return null;
  }

  // ---------------------------------------------------------------- per-force coverage for the current range
  function forceCoverage(slug) {
    var m = S.forceTotals && S.forceTotals.monthly[slug];
    if (!m) return { present: 0, total: S.rangeIds.length, sum: 0 };
    var present = 0, sum = 0;
    S.rangeIds.forEach(function (id) { if (m[id] !== undefined) { present++; sum += m[id]; } });
    return { present: present, total: S.rangeIds.length, sum: sum };
  }

  // ---------------------------------------------------------------- rendering
  function windowLabel() {
    if (S.win === 'month') return S.month + ' (single month)';
    var w = S.meta.windows[S.win];
    return w.from + ' to ' + w.to + ' (' + w.months + ' months)';
  }


  // Home Office cross-check (England and Wales, official, per force and financial year).
  function xrefLatest(slug) {
    var f = S.xref && S.xref.forces[slug];
    if (!f) return null;
    var ks = Object.keys(f).sort(), k = ks[ks.length - 1];
    return k ? { fy: k, d: f[k] } : null;
  }
  var AGREE_TEXT = {
    agree: 'police.uk and the Home Office agree within 5% for that year',
    minor_difference: 'police.uk and the Home Office differ by 5 to 10% for that year',
    differs: 'police.uk and the Home Office differ by more than 10% for that year',
    incomplete_months: 'police.uk has fewer than 12 months for that year, so no like-for-like check is possible',
    no_street_data: 'police.uk published no street-level rows for that year'
  };
  function xrefHtml(slug, withTotal) {
    var x = xrefLatest(slug);
    if (!x) return '';
    var d = x.d;
    var h = '<br><span class="small">Home Office (official, whole force, ' + x.fy + '): ' + (withTotal ? fmt(d.home_office_total) + ' violence and sexual offences, of which ' : '') +
      d.sexual_share_pct + '% (' + fmt(d.home_office_sexual) + ') were sexual offences, ' + fmt(d.home_office_rape) + ' of them rape. ' +
      'This is a force-wide share; it is not known for this cell. Cross-check: ' + (AGREE_TEXT[d.agreement] || '') + '.</span>';
    return h;
  }

  function cellPopup(q, r, n) {
    var c = hexCenter(q, r), slug = forceAt(c[0], c[1]);
    var rank = S.sortedCounts.length ? Math.round(100 * (S.sortedCounts.filter(function (x) { return x < n; }).length) / S.sortedCounts.length) : 0;
    var html = '<div class="big">' + fmt(n) + '</div>reported records (violence and sexual offences, combined category)' +
      '<br><span class="small">Window: ' + windowLabel() + '</span>' +
      '<br>Area: cell ' + q + ',' + r + ' (hexagon about 4&nbsp;km across, centre near ' + c[0].toFixed(2) + ', ' + c[1].toFixed(2) + ')';
    if (slug) {
      html += '<br>Force area: ' + forceName(slug);
      var cov = forceCoverage(slug);
      if (cov.present < cov.total * INCOMPLETE) {
        html += '<br><span class="warn">This force published data for only ' + cov.present + ' of ' + cov.total +
          ' months in this window, so this count is incomplete.</span>';
      }
    }
    if (slug) html += xrefHtml(slug, false);
    var maxN = S.sortedCounts[S.sortedCounts.length - 1];
    html += '<br><span class="small">' + (n === maxN ? 'The highest-count cell in this window.' : 'Higher than ' + rank + '% of plotted cells.') + '</span>' +
      '<br><span class="small">Source: data.police.uk, Open Government Licence v3.0. Locations anonymised by the police; may include British Transport Police records; reported offences only, not prevalence.</span>';
    return html;
  }

  function computeBreaks() {
    var counts = S.cells.map(function (c) { return c[2]; }).sort(function (a, b) { return a - b; });
    S.sortedCounts = counts;
    var br = [];
    CLASS_QUANTILES.forEach(function (p) {
      var v = quantile(counts, p), last = br.length ? br[br.length - 1] : 0;
      br.push(Math.max(v, last + 1));
    });
    S.breaks = br;
  }

  function renderCells() {
    hexGroup.clearLayers();
    if (heat) { map.removeLayer(heat); heat = null; }
    var hot = quantile(S.sortedCounts, HOTSPOT_Q);
    S.cells.forEach(function (c) {
      var cls = classOf(c[2]), isHot = c[2] >= hot;
      var poly = L.polygon(hexRing(c[0], c[1]), {
        renderer: canvas, stroke: isHot,
        color: '#5c0010', weight: 2, opacity: 0.95,
        fillColor: CLASS_COLOURS[cls], fillOpacity: cls < 2 ? 0.12 : 0.3 + 0.07 * cls
      });
      poly.bindPopup(function () { return cellPopup(c[0], c[1], c[2]); });
      poly._usoda = c;
      hexGroup.addLayer(poly);
    });
    var p99 = Math.max(1, quantile(S.sortedCounts, 0.99));
    var pts = S.cells.map(function (c) {
      var ll = hexCenter(c[0], c[1]);
      return [ll[0], ll[1], Math.min(1, Math.sqrt(c[2] / p99))];
    });
    heat = L.heatLayer(pts, {
      radius: heatRadius(), blur: heatRadius() * 0.8, max: 1.0, minOpacity: 0.15,
      gradient: { 0.2: '#ffffb2', 0.4: '#fecc5c', 0.6: '#fd8d3c', 0.8: '#e31a1c', 1.0: '#800026' }
    });
    applyLayerToggles();
  }

  function heatRadius() {
    var mpp = 156543.03 * Math.cos(54.5 * Math.PI / 180) / Math.pow(2, map.getZoom());
    return Math.max(6, Math.min(60, 2400 / mpp));
  }
  map.on('zoomend', function () {
    if (heat) { var r = heatRadius(); heat.setOptions({ radius: r, blur: r * 0.8 }); }
  });

  function applyLayerToggles() {
    function set(layer, on) { if (!layer) return; if (on && !map.hasLayer(layer)) layer.addTo(map); if (!on && map.hasLayer(layer)) map.removeLayer(layer); }
    set(scotGroup, $('lScot').checked);
    set(pfaGroup, $('lPfa').checked);
    set(heat, $('lHeat').checked);
    set(hexGroup, $('lHex').checked);
  }


  // Scotland: annual council-area totals for the Scottish definition of sexual crimes.
  function scotYears() {
    var ys = S.scotData.years, n = S.win === '10y' ? 10 : S.win === '5y' ? 5 : S.win === '3y' ? 3 : 1;
    return ys.slice(-n);
  }
  function renderScot() {
    scotGroup.clearLayers();
    if (!S.scotGeo || !S.scotData) return;
    var ys = scotYears(), rows = [];
    S.scotGeo.features.forEach(function (f) {
      var a = S.scotData.areas[f.properties.code]; if (!a) return;
      var t = { sexual: 0, rape: 0, assault: 0, rateSum: 0 };
      ys.forEach(function (y) {
        var d = a.years[y] || {};
        t.sexual += (d.sexual && d.sexual.count) || 0;
        t.rape += (d.rape && d.rape.count) || 0;
        t.assault += (d.assault && d.assault.count) || 0;
        t.rateSum += (d.sexual && d.sexual.rate_per_10k) || 0;
      });
      t.rate = t.rateSum / ys.length;
      rows.push({ f: f, t: t });
    });
    var rates = rows.map(function (r) { return r.t.rate; }).sort(function (a, b) { return a - b; });
    var br = [0.15, 0.3, 0.5, 0.7, 0.85, 0.95].map(function (p) { return quantile(rates, p); });
    S.scotBreaks = br;
    var label = ys.length === 1 ? ys[0] : ys[0] + ' to ' + ys[ys.length - 1];
    rows.forEach(function (row) {
      var cls = 0; while (cls < br.length && row.t.rate >= br[cls]) cls++;
      var layer = L.geoJSON(row.f, {
        pane: 'scot',
        style: { color: '#4a1486', weight: 1, fillColor: SCOT_COLOURS[cls], fillOpacity: 0.6 }
      });
      layer.bindPopup(function () {
        return '<strong>' + row.f.properties.name + '</strong> (Scotland)<br><span class="big">' + fmt(row.t.sexual) +
          '</span> recorded sexual crimes<br><span class="small">Financial years ' + label + ' (April to March). Of these: ' +
          fmt(row.t.rape) + ' rape and attempted rape, ' + fmt(row.t.assault) + ' sexual assault. Average published rate ' +
          row.t.rate.toFixed(1) + ' per 10,000 residents a year (rounded in the source).</span>' +
          '<br><span class="small">Scottish definition (Group 2 sexual crimes). Not comparable with the hexagon counts. ' +
          'Source: Scottish Government / Police Scotland, OGL v3.0. Areas are council-wide, so rural areas average over large empty land.</span>';
      });
      scotGroup.addLayer(layer);
    });
  }

  function renderPfa() {
    pfaGroup.clearLayers();
    if (!S.pfa) return;
    var sums = [];
    var rows = S.pfa.features.map(function (f) {
      var cov = forceCoverage(f.properties.slug);
      var incomplete = cov.present < cov.total * INCOMPLETE;
      if (!incomplete) sums.push(cov.sum);
      return { f: f, cov: cov, incomplete: incomplete };
    });
    sums.sort(function (a, b) { return a - b; });
    var br = [0.15, 0.3, 0.5, 0.7, 0.85, 0.95].map(function (p) { return quantile(sums, p); });
    rows.forEach(function (row) {
      var cls = 0; while (cls < br.length && row.cov.sum >= br[cls]) cls++;
      var layer = L.geoJSON(row.f, {
        pane: 'pfa',
        style: row.incomplete
          ? { color: '#555', weight: 1.5, dashArray: '5 4', fillColor: '#cfcfcf', fillOpacity: 0.55 }
          : { color: '#1a3d6b', weight: 1, fillColor: PFA_COLOURS[cls], fillOpacity: 0.5 }
      });
      layer.bindPopup(function () {
        var h = '<strong>' + row.f.properties.name + '</strong><br><span class="big">' + fmt(row.cov.sum) + '</span> reported records' +
          '<br><span class="small">Window: ' + windowLabel() + '. Months with data: ' + row.cov.present + ' of ' + row.cov.total + '.</span>';
        if (row.incomplete) h += '<br><span class="warn">Incomplete: this total understates the force area and must not be compared with other areas.</span>';
        h += xrefHtml(row.f.properties.slug, true);
        h += '<br><span class="small">Raw counts, not rates: larger populations record more. Sources: data.police.uk and Home Office police recorded crime, OGL v3.0.</span>';
        return h;
      });
      pfaGroup.addLayer(layer);
    });
  }

  function renderLegend() {
    var el = $('legend'), b = S.breaks;
    var ramp = CLASS_COLOURS.map(function (c) { return '<span style="background:' + c + '" title="' + c + '"></span>'; }).join('');
    var max = S.sortedCounts.length ? S.sortedCounts[S.sortedCounts.length - 1] : 0;
    var html = '<strong>Reported records per cell</strong><div class="ramp" aria-hidden="true">' + ramp + '</div>' +
      '<div class="ends"><span>fewer (' + (b.length ? '&lt;' + fmt(b[0]) : '') + ')</span><span>more (up to ' + fmt(max) + ')</span></div>' +
      '<div class="key"><span class="sw" aria-hidden="true"></span> Dark outline: hotspot (top 3% of cells in this window)</div>';
    if ($('lPfa').checked) html += '<div class="key"><span class="sw gap" aria-hidden="true"></span> Dashed grey (force areas): incomplete data</div>';
    if ($('lScot').checked && S.scotBreaks) html += '<div class="key"><span class="sw" style="background:#6a51a3" aria-hidden="true"></span> Purple (Scotland): sexual crimes per 10,000 residents, council areas, Scottish definition. Not comparable with the orange cells.</div>';
    html += '<div class="key" style="color:#555">Colour classes are quantile-based, recalculated for each window.</div>';
    el.innerHTML = html;
  }

  function renderTop() {
    var top = S.cells.slice().sort(function (a, b) { return b[2] - a[2]; }).slice(0, 15);
    var ol = $('topList'); ol.innerHTML = '';
    top.forEach(function (c) {
      var ll = hexCenter(c[0], c[1]), slug = forceAt(ll[0], ll[1]);
      var li = document.createElement('li'), b = document.createElement('button');
      b.type = 'button';
      b.textContent = fmt(c[2]) + ' records' + (slug ? ' - ' + forceName(slug) : '') + ' (' + ll[0].toFixed(2) + ', ' + ll[1].toFixed(2) + ')';
      b.addEventListener('click', function () {
        map.setView(ll, 11);
        L.popup().setLatLng(ll).setContent(cellPopup(c[0], c[1], c[2])).openOn(map);
      });
      li.appendChild(b); ol.appendChild(li);
    });
  }

  function renderBannerAndStatus(upstream) {
    var m = S.meta, rows = [];
    function add(k, v, warn) { rows.push('<dt>' + k + '</dt><dd' + (warn ? ' class="warn"' : '') + '>' + v + '</dd>'); }
    add('Window shown', windowLabel());
    add('Latest month in atlas', m.latest_month);
    if (upstream) {
      var newer = upstream > m.latest_month;
      add('Newest month published upstream', upstream + (newer ? ' (newer than atlas; next scheduled build will add it)' : ' (atlas is up to date)'), newer);
    } else {
      add('Newest month published upstream', 'not checked (offline or blocked)');
    }
    add('Records in 10-year window', fmt(m.quality.records_in_window));
    add('Records with a location', m.quality.location_share_pct + '%');
    add('Force-month coverage', m.quality.force_month_coverage_pct + '%');
    if (m.quality.duplicate_rows_dropped !== undefined) add('Exact duplicate rows removed', fmt(m.quality.duplicate_rows_dropped) + ' (same crime ID and place in one file)');
    if (m.quality.btp_scotland_records_excluded) add('BTP rail points in Scotland left out of cells', fmt(m.quality.btp_scotland_records_excluded) + ' (Scotland is shown by council area)');
    if (S.xref) {
      var bc = S.xref.band_counts, tot = 0, k; for (k in bc) tot += bc[k];
      add('Home Office cross-check', fmt(bc.agree || 0) + ' of ' + fmt(tot) + ' force-years within 5%; ' + fmt(bc.minor_difference || 0) + ' within 10%; ' + fmt((bc.differs || 0)) + ' differ more; ' + fmt((bc.incomplete_months || 0) + (bc.no_street_data || 0)) + ' cannot be checked (gaps)');
    }
    add('Last successful ingest', m.last_successful_ingest.replace('T', ' ').replace('Z', ' UTC'));
    if (S.win !== 'month') {
      var w = m.windows[S.win];
      add('Cells hidden (fewer than ' + m.hex.min_cell + ' records)', fmt(w.records_suppressed) + ' records');
    }
    $('statusList').innerHTML = rows.join('');
    $('footStamp').textContent = 'Data updated: ' + m.last_successful_ingest.slice(0, 10) + ' | latest month ' + m.latest_month;

    var inc = [], single = S.win === 'month';
    Object.keys(S.forceTotals.monthly).forEach(function (slug) {
      var c = forceCoverage(slug);
      if (c.present < c.total * INCOMPLETE) inc.push(single ? forceName(slug) : forceName(slug) + ' (' + c.present + '/' + c.total + ' months)');
    });
    var msg;
    if (inc.length) {
      msg = (single ? 'No data published this month for: ' : 'Incomplete data in this window: ') + inc.join('; ') +
        '. Areas these forces cover look quieter than they are.';
    } else {
      msg = 'Orange cells: reported records, not rates or prevalence. Scotland (purple) is annual council-area data on a different definition and is not comparable.';
    }
    showBanner(msg);
  }

  function showBanner(msg) {
    var b = $('banner');
    b.innerHTML = '<span></span> <button type="button" class="x" aria-label="Dismiss notice">&times;</button>';
    b.firstChild.textContent = msg;
    b.querySelector('.x').addEventListener('click', function () { b.hidden = true; });
    b.hidden = false;
  }

  // ---------------------------------------------------------------- loading
  var upstreamLatest = null;
  function load() {
    var file = S.win === 'month' ? 'months/' + S.month + '.json' : 'windows/' + S.win + '.json';
    $('statusList').setAttribute('aria-busy', 'true');
    return getJSON(file).then(function (d) {
      S.cells = d.cells;
      S.rangeIds = S.win === 'month' ? [S.month] : monthRange(S.meta.windows[S.win].from, S.meta.windows[S.win].to);
      computeBreaks(); renderCells(); renderScot(); renderPfa(); renderLegend(); renderTop(); renderBannerAndStatus(upstreamLatest);
      $('statusList').removeAttribute('aria-busy');
    }).catch(function (e) {
      showBanner('Could not load data (' + e.message + '). Please retry later.');
    });
  }

  function pollUpstream() {
    function pick(j) { return j.map(function (d) { return d.date; }).sort().pop(); }
    var tryUrls = ['api/crimes-street-dates', 'https://data.police.uk/api/crimes-street-dates'];
    (function next(i) {
      if (i >= tryUrls.length) return;
      fetch(tryUrls[i]).then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (j) {
        upstreamLatest = pick(j);
        if (S.meta) renderBannerAndStatus(upstreamLatest);
      }).catch(function () { next(i + 1); });
    })(0);
  }

  // ---------------------------------------------------------------- controls
  Array.prototype.forEach.call(document.querySelectorAll('input[name=win]'), function (r) {
    r.addEventListener('change', function () {
      S.win = r.value;
      $('monthSelect').disabled = S.win !== 'month';
      load();
    });
  });
  $('monthSelect').addEventListener('change', function () { S.month = this.value; if (S.win === 'month') load(); });
  ['lHeat', 'lHex', 'lPfa', 'lScot'].forEach(function (id) {
    $(id).addEventListener('change', function () { applyLayerToggles(); renderLegend(); });
  });
  $('aboutBtn').addEventListener('click', function () { $('about').showModal(); });

  // ---------------------------------------------------------------- boot
  Promise.all([getJSON('meta.json'), getJSON('force_totals.json'), getJSON('pfa.geojson'),
    getJSON('scotland_la.json').catch(function () { return null; }), getJSON('scotland_la.geojson').catch(function () { return null; }),
    getJSON('crossref.json').catch(function () { return null; })]).then(function (r) {
    S.meta = r[0]; S.forceTotals = r[1]; S.pfa = r[2]; S.scotData = r[3]; S.scotGeo = r[4]; S.xref = r[5];
    G.R = S.meta.hex.R; G.K = S.meta.hex.K;
    buildPfaIndex(S.pfa);
    var sel = $('monthSelect');
    S.meta.months_available.slice().reverse().forEach(function (m) {
      var o = document.createElement('option'); o.value = m.month; o.textContent = m.month; sel.appendChild(o);
    });
    S.month = S.meta.latest_month; sel.value = S.month;
    return load();
  }).then(function () {
    pollUpstream();
    setInterval(pollUpstream, 3600000);
  }).catch(function (e) {
    showBanner('Could not load the atlas data (' + e.message + ').');
  });
})();
