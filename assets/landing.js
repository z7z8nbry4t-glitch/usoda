// Fills in the data stamp on the front page. The page reads fine without it.
(function () {
  var el = document.getElementById("stamp");
  if (!el || !window.fetch) return;
  fetch("data/meta.json", { cache: "no-cache" })
    .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
    .then(function (m) {
      var parts = String(m.latest_month || "").split("-");
      if (parts.length !== 2) return;
      var names = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"];
      var month = names[parseInt(parts[1], 10) - 1];
      if (!month) return;
      el.textContent = "Latest month of police data: " + month + " " + parts[0] +
        ". Rolling ten-year window.";
    })
    .catch(function () {});
})();
