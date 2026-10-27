/* USODA inline SVG bar charts, shared by the map and the force pages. No libraries, no inline script. */
(function () {
  'use strict';
  var fmt = function (n) { return Number(n).toLocaleString('en-GB'); };

  function niceMax(m) {
    if (m <= 4) return 4;
    var p = Math.pow(10, Math.floor(Math.log(m) / Math.LN10)), f = m / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  }
  function trendChart(pts, o) {
    var W = 320, H = 150, L = 40, R = 6, T = 8, B = 22, iw = W - L - R, ih = H - T - B;
    var vals = pts.filter(function (p) { return p.v !== null; });
    if (vals.length < 2) return '<div class="small">Not enough history to draw a trend.</div>';
    var max = niceMax(Math.max.apply(null, vals.map(function (p) { return p.v; })));
    var step = iw / pts.length, bw = Math.max(1, step * 0.8);
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="' + o.alt + '" focusable="false">';
    [0, 0.5, 1].forEach(function (f) {
      var y = T + ih - ih * f;
      svg += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#ccc" stroke-width="0.6"/>' +
        '<text x="' + (L - 4) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end" font-size="9" fill="#555">' + fmt(Math.round(max * f)) + '</text>';
    });
    var every = Math.max(1, Math.ceil(pts.filter(function (p) { return p.tick; }).length / 6)), n = 0;
    pts.forEach(function (p, i) {
      var x = L + i * step + (step - bw) / 2;
      if (p.v === null) {
        svg += '<rect x="' + x.toFixed(1) + '" y="' + (T + ih - 2) + '" width="' + bw.toFixed(1) + '" height="2" fill="' + (p.gap ? '#c0392b' : '#9a9a9a') + '"/>';
      } else {
        var h = Math.max(0.5, ih * p.v / max);
        svg += '<rect x="' + x.toFixed(1) + '" y="' + (T + ih - h).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + h.toFixed(1) + '" fill="' + o.colour + '"><title>' + p.l + ': ' + fmt(p.v) + '</title></rect>';
      }
      if (p.tick) {
        if (n % every === 0) svg += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="9" fill="#555">' + p.tick + '</text>';
        n++;
      }
    });
    svg += '</svg>';
    var peak = vals.reduce(function (a, b) { return b.v > a.v ? b : a; });
    var last = vals[vals.length - 1];
    return '<div class="trend-box"><strong>' + o.title + '</strong>' + svg +
      '<div class="small">' + o.unit + '. ' + pts[0].l + ' to ' + pts[pts.length - 1].l + '. Highest: ' + fmt(peak.v) + ' (' + peak.l + '). Latest shown: ' + fmt(last.v) + ' (' + last.l + ').' +
      (o.note ? ' ' + o.note : '') + '</div></div>';
  }
  function trendAlt(what, pts) {
    return 'Bar chart of ' + what + ' from ' + pts[0].l + ' to ' + pts[pts.length - 1].l + '. Values are in the text beneath the chart.';
  }
  var MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function monthLabel(m) { return MONTH_NAMES[+m.slice(5) - 1] + ' ' + m.slice(0, 4); }


  window.UsodaCharts = { fmt: fmt, niceMax: niceMax, trendChart: trendChart, trendAlt: trendAlt, monthLabel: monthLabel };
})();
