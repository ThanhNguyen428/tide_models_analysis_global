/**
 * multivariate_r2_map_ice_filtered.js
 *
 * Classifies every ice-filtered single-pixel SWOT coastline point by which
 * tide model wins, and how well it does (see map_logic.txt):
 *
 *   green  - FES >= GOT and R2(FES) >= 0.35    darker = higher R2(FES)
 *   yellow - GOT beats FES by >= 0.05 and R2(GOT) >= 0.35
 *                                              darker = higher R2(GOT)
 *   red    - both R2 < 0.35                    darker = lower min(R2)
 *
 * Loaded after leaflet.min.js, basemap_geo.js, d{1,2,3}_ice.js and
 * map_common.js by multivariate_r2_map_ice_filtered.html.
 */
(function () {
  "use strict";

  var T = TideMap;

  /** R2 at or above which a model counts as usable. */
  var GOOD_R2 = 0.35;
  /** How far GOT must beat FES before the point is called GOT-dominant. */
  var GOT_MARGIN = 0.05;
  /** Gamma on the colour ramp; < 1 lifts the mid-range out of the pale end. */
  var RAMP_GAMMA = 0.7;

  var records = T.decodeRecords([D1, D2, D3], T.LAYOUTS.STD_7);
  var NPTS = records.length;

  // Raw payload is decoded; let it go (tens of MB).
  D1 = null;
  D2 = null;
  D3 = null;

  /* ------------------------------------------------------------------ *
   * Classification
   * ------------------------------------------------------------------ */

  var CATEGORIES = {
    green: { label: "FES dominant", lo: "--green-lo", hi: "--green-hi" },
    yellow: { label: "GOT dominant", lo: "--yellow-lo", hi: "--yellow-hi" },
    red: { label: "Both poor", lo: "--red-lo", hi: "--red-hi" }
  };

  function shade(cat, t) {
    var c = CATEGORIES[cat];
    return {
      cat: cat,
      label: c.label,
      color: T.lerpColor(T.css(c.lo), T.css(c.hi), Math.pow(T.clamp01(t), RAMP_GAMMA))
    };
  }

  /**
   * @param {number} fes - R2 of SSH vs the FES correction
   * @param {number} got - R2 of SSH vs the GOT correction
   * @returns {{cat: string, label: string, color: string}}
   */
  function classify(fes, got) {
    // FES wins outright (ties go to FES) and is good enough to trust.
    if (fes >= got && fes >= GOOD_R2) {
      return shade("green", (fes - GOOD_R2) / (1 - GOOD_R2));
    }

    // GOT wins by a clear margin and is good enough to trust.
    if (got - fes >= GOT_MARGIN && got >= GOOD_R2) {
      return shade("yellow", (got - GOOD_R2) / (1 - GOOD_R2));
    }

    // Neither model explains the signal; darker the worse the better one is.
    if (fes < GOOD_R2 && got < GOOD_R2) {
      return shade("red", 1 - Math.min(fes, got) / GOOD_R2);
    }

    // Leftovers: GOT ahead but by less than the margin, with one model good.
    // Shown as FES-dominant, shaded by whichever R2 is higher.
    return shade("green", (Math.max(fes, got) - GOOD_R2) / (1 - GOOD_R2));
  }

  for (var i = 0; i < NPTS; i++) {
    var rec = records[i];
    var cls = classify(rec.fes, rec.got);
    rec.cat = cls.cat;
    rec.label = cls.label;
    rec.c = cls.color;
  }

  /* ------------------------------------------------------------------ *
   * Map + markers
   * ------------------------------------------------------------------ */

  var created = T.createMap("map", T.VIEW_GLOBAL);
  var map = created.map;
  var home = created.home;

  function tipHTML(r) {
    return '<div class="tt-head">' +
        r.lat.toFixed(2) + "°, " + r.lon.toFixed(2) + "°</div>" +
      T.row("R² FES", T.fmt4(r.fes)) +
      T.row("R² GOT", T.fmt4(r.got)) +
      T.row("ΔR² (FES−GOT)", T.signed4(r.d)) +
      T.row("STD(SSH)", T.fmt4(r.ssh_s)) +
      '<div class="tt-cat"><span class="dot" style="background:' + r.c +
        '"></span>' + r.label + "</div>";
  }

  function popHTML(r) {
    return '<div class="pop-coord">' +
        r.lat.toFixed(2) + "°, " + r.lon.toFixed(2) + "°</div>" +
      '<div class="pop-sub">' + r.label +
        " — ΔR² " + T.signed4(r.d) + "</div>" +
      '<div class="pop-rows">' +
        T.row("R² FES", T.fmt4(r.fes)) +
        T.row("R² GOT", T.fmt4(r.got)) +
        T.row("STD(SSH)", T.fmt4(r.ssh_s)) +
        T.row("STD(FES)", T.fmt4(r.fes_s)) +
        T.row("STD(GOT)", T.fmt4(r.got_s)) +
      "</div>" +
      '<button class="btn copy" type="button" data-coord="' +
        r.lat.toFixed(2) + "," + r.lon.toFixed(2) +
        '">Copy coordinates</button>';
  }

  var built = T.buildMarkers(map, records, {
    tipHTML: tipHTML,
    popHTML: popHTML,
    radii: T.RADII_DEFAULT
  });
  var markers = built.markers;
  var tooltip = built.tooltip;
  var layer = L.layerGroup().addTo(map);

  /* ------------------------------------------------------------------ *
   * Header stats, filtering and redraw
   * ------------------------------------------------------------------ */

  // Category totals never change, so count them once up front.
  var TOTALS = { green: 0, yellow: 0, red: 0 };
  for (i = 0; i < NPTS; i++) {
    TOTALS[records[i].cat]++;
  }

  function statCell(label, swatchVar, count) {
    var pct = NPTS > 0 ? (count / NPTS * 100).toFixed(1) : "0.0";
    return '<div class="stat"><span class="k">' + label +
      '</span><span class="v"><span class="swatch" style="background:' +
      T.css(swatchVar) + '"></span>' + T.num(count) +
      "<small>" + pct + "%</small></span></div>";
  }

  function updateStats(visible) {
    T.byId("stats").innerHTML =
      '<div class="stat"><span class="k">Points</span><span class="v">' +
        T.num(NPTS) + "</span></div>" +
      '<div class="stat"><span class="k">Visible</span><span class="v">' +
        T.num(visible) + "</span></div>" +
      statCell("FES dominant", "--green-hi", TOTALS.green) +
      statCell("GOT dominant", "--yellow-hi", TOTALS.yellow) +
      statCell("Both poor", "--red-hi", TOTALS.red);
  }

  function render() {
    var minDelta = parseFloat(T.byId("thresh").value);
    var cat = T.radioValue("cat", "all");

    T.byId("thresh-val").textContent = minDelta.toFixed(2);
    layer.clearLayers();
    map.closeTooltip(tooltip);
    map.closePopup();

    var visible = 0;
    for (var k = 0; k < markers.length; k++) {
      var r = markers[k].rec;
      if (cat !== "all" && r.cat !== cat) continue;
      if (Math.abs(r.d) < minDelta) continue;
      layer.addLayer(markers[k]);
      visible++;
    }

    T.byId("shown").innerHTML =
      "<b>" + T.num(visible) + "</b> of " + T.num(NPTS) + " points shown";
    updateStats(visible);
  }

  T.wireControls({
    radioName: "cat",
    defaultRadioId: "cat-all",
    render: render,
    map: map,
    home: home
  });

  // Colour the swatches in the category switcher to match the ramps.
  T.byId("dot-green").style.background = T.css("--green-hi");
  T.byId("dot-yellow").style.background = T.css("--yellow-hi");
  T.byId("dot-red").style.background = T.css("--red-hi");

  render();

  /* ------------------------------------------------------------------ *
   * Legend
   * ------------------------------------------------------------------ */

  function legendRow(lo, hi, label) {
    return '<div class="lg-row"><div class="lg-swatch" ' +
      'style="background:linear-gradient(90deg,' + T.css(lo) + "," +
      T.css(hi) + ')"></div><div class="lg-label">' + label + "</div></div>";
  }

  T.addLegend(map,
    '<div class="t">Classification</div>' +
    legendRow("--green-lo", "--green-hi",
      "FES dominant<br>(FES ≥ GOT, R²≥0.35)") +
    legendRow("--yellow-lo", "--yellow-hi",
      "GOT dominant<br>(GOT−FES ≥ 0.05, R²≥0.35)") +
    legendRow("--red-lo", "--red-hi",
      "Both poor<br>(FES &amp; GOT R² &lt; 0.35)") +
    '<div class="lg-note">Darker = stronger signal in dominant metric; ' +
      "for red, darker = lower min R².</div>");
})();
