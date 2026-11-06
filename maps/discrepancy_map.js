/**
 * discrepancy_map.js - the shared delta-R2 map.
 *
 * All four single_pixel_r2_map_*.html pages draw the same thing: every SWOT
 * coastline point coloured by
 *
 *   delta = R2(FES) - R2(GOT)
 *
 * on a diverging ramp - blue where GOT fits better, red where FES does,
 * neutral grey at a tie - scaled to the largest |delta| in the payload.
 *
 * The pages differ only in their payload layout, map view, dot size, coordinate
 * precision and which spread rows the tooltip shows, so each one is a short
 * config passed to `TideDiscrepancyMap.build()`.
 *
 * Load after map_common.js. The classification map (multivariate_r2_map_*)
 * does not use this file.
 */
var TideDiscrepancyMap = (function () {
  "use strict";

  var T = TideMap;

  /** Gamma on the colour ramp; < 1 lifts the mid-range out of the pale end. */
  var RAMP_GAMMA = 0.7;
  /** Colour stops used to paint the legend gradient. */
  var LEGEND_STOPS = 20;

  /* ------------------------------------------------------------------ *
   * Spread-row presets - the one part of the tooltip that varies
   * ------------------------------------------------------------------ */
  var ROWS = {
    /** STD_7 payloads: three standard deviations, stored ready to print. */
    standardDeviations: function (r) {
      return T.row("STD(SSH)", T.fmt4(r.ssh_s)) +
        T.row("STD(FES)", T.fmt4(r.fes_s)) +
        T.row("STD(GOT)", T.fmt4(r.got_s));
    },

    /** VAR_6 payloads: the signed delta, then SDs derived from variances. */
    deltaAndVariances: function (r) {
      return T.row("Δ (FES−GOT)", T.signed4(r.d)) +
        T.row("SD(FES + corrected SSH)", T.fmt4(Math.sqrt(r.fv))) +
        T.row("SD(GOT + corrected SSH)", T.fmt4(Math.sqrt(r.gv)));
    }
  };

  /* ------------------------------------------------------------------ *
   * Diverging colour ramp
   * ------------------------------------------------------------------ */

  /**
   * Colour for a signed delta, saturating at +/- maxAbs.
   * @param {number} value  - delta R2 (FES - GOT)
   * @param {number} maxAbs - delta magnitude that reaches full saturation
   * @returns {string} an rgb() colour
   */
  function divergingColor(value, maxAbs) {
    var t = Math.max(-1, Math.min(1, value / maxAbs));
    var mid = T.hexToRgb(T.css("--mid-color"));
    var pole = T.hexToRgb(T.css(t < 0 ? "--got-pole" : "--fes-pole"));
    var s = Math.pow(Math.abs(t), RAMP_GAMMA);

    var channels = mid.map(function (m, i) {
      return Math.round(m + (pole[i] - m) * s);
    });
    return "rgb(" + channels.join(",") + ")";
  }

  /* ------------------------------------------------------------------ *
   * Build
   * ------------------------------------------------------------------ */

  /**
   * @param {Object} cfg
   * @param {number[][]} cfg.payload   - payload arrays, e.g. [D1, D2, D3]
   * @param {Object} cfg.layout        - a TideMap.LAYOUTS entry
   * @param {Object} cfg.view          - TideMap.VIEW_GLOBAL or VIEW_TROPICS
   * @param {number[]} [cfg.radii]     - TideMap.RADII_DEFAULT or RADII_LARGE
   * @param {number} [cfg.coordDigits] - decimals on printed lat/lon (default 2)
   * @param {function(Object):string} cfg.detailRows - a ROWS preset
   * @param {function():void} [cfg.release] - called once the payload is decoded,
   *                                          to drop the raw arrays
   */
  function build(cfg) {
    var digits = cfg.coordDigits || 2;
    var records = T.decodeRecords(cfg.payload, cfg.layout);
    var NPTS = records.length;

    // Drop the raw payload now that it is decoded. cfg outlives this call
    // (the tooltip builders close over it), so clear its reference too or the
    // arrays - tens of MB of them - stay reachable for the life of the page.
    cfg.payload = null;
    if (cfg.release) cfg.release();

    // The ramp saturates at the largest discrepancy actually present.
    var MAX_ABS = 0;
    for (var i = 0; i < NPTS; i++) {
      var a = Math.abs(records[i].d);
      if (a > MAX_ABS) MAX_ABS = a;
    }
    for (i = 0; i < NPTS; i++) {
      records[i].c = divergingColor(records[i].d, MAX_ABS);
    }

    var created = T.createMap("map", cfg.view);
    var map = created.map;

    /* ---------------- tooltips and popups ---------------- */

    function coords(r) {
      return r.lat.toFixed(digits) + "°, " + r.lon.toFixed(digits) + "°";
    }

    function better(r) {
      return r.d >= 0 ? "FES" : "GOT";
    }

    function r2Rows(r) {
      return T.row("R² FES", T.fmt4(r.fes)) +
        T.row("R² GOT", T.fmt4(r.got));
    }

    function tipHTML(r) {
      return '<div class="tt-head">' + coords(r) + "</div>" +
        r2Rows(r) + cfg.detailRows(r) +
        '<div class="tt-win"><span class="dot" style="background:' + r.c +
          '"></span>' + better(r) + " fits better</div>";
    }

    function popHTML(r) {
      return '<div class="pop-coord">' + coords(r) + "</div>" +
        '<div class="pop-sub">' + better(r) + " better by " +
          Math.abs(r.d).toFixed(4) + " R²</div>" +
        '<div class="pop-rows">' + r2Rows(r) + cfg.detailRows(r) + "</div>" +
        '<button class="btn copy" type="button" data-coord="' +
          r.lat.toFixed(digits) + "," + r.lon.toFixed(digits) +
          '">Copy coordinates</button>';
    }

    var built = T.buildMarkers(map, records, {
      tipHTML: tipHTML,
      popHTML: popHTML,
      radii: cfg.radii
    });
    var markers = built.markers;
    var tooltip = built.tooltip;
    var layer = L.layerGroup().addTo(map);

    /* ---------------- header stats ---------------- */

    function statCell(label, swatchVar, pct, count) {
      return '<div class="stat"><span class="k">' + label +
        '</span><span class="v"><span class="swatch" style="background:' +
        T.css(swatchVar) + '"></span>' + pct +
        "%<small>(" + T.num(count) + " pts)</small></span></div>";
    }

    function updateStats(fesWins, gotWins, ties) {
      var tot = fesWins + gotWins;
      var fesPct = tot > 0 ? (fesWins / tot * 100).toFixed(1) : "0.0";
      var gotPct = tot > 0 ? (gotWins / tot * 100).toFixed(1) : "0.0";

      T.byId("stats").innerHTML =
        statCell("FES fits better", "--fes-pole", fesPct, fesWins) +
        statCell("GOT fits better", "--got-pole", gotPct, gotWins) +
        '<div class="stat"><span class="k">Tied</span><span class="v">' +
          T.num(ties) + "</span></div>";

      T.byId("dot-fes").style.background = T.css("--fes-pole");
      T.byId("dot-got").style.background = T.css("--got-pole");
    }

    /* ---------------- filtering and redraw ---------------- */

    function render() {
      var minDelta = parseFloat(T.byId("thresh").value);
      var dir = T.radioValue("dir", "all");

      T.byId("thresh-val").textContent = minDelta.toFixed(2);
      layer.clearLayers();
      map.closeTooltip(tooltip);
      map.closePopup();

      var visible = 0, fesWins = 0, gotWins = 0, ties = 0;
      for (var k = 0; k < markers.length; k++) {
        var d = markers[k].rec.d;
        if (Math.abs(d) < minDelta) continue;
        if (dir === "fes" && d < 0) continue;
        if (dir === "got" && d > 0) continue;

        layer.addLayer(markers[k]);
        visible++;
        if (d > 0) fesWins++;
        else if (d < 0) gotWins++;
        else ties++;
      }

      T.byId("shown").innerHTML =
        "<b>" + T.num(visible) + "</b> of " + T.num(NPTS) + " points shown";
      updateStats(fesWins, gotWins, ties);
    }

    T.wireControls({
      radioName: "dir",
      defaultRadioId: "dir-all",
      render: render,
      map: map,
      home: created.home
    });

    render();

    /* ---------------- legend ---------------- */

    T.addLegend(map,
      '<div class="t">Δ R² (FES − GOT)</div>' +
      '<div class="lg-ramp" id="lg-ramp"></div>' +
      '<div class="lg-scale">' +
        "<span>−" + MAX_ABS.toFixed(2) + "</span>" +
        "<span>0</span>" +
        "<span>+" + MAX_ABS.toFixed(2) + "</span>" +
      "</div>" +
      '<div class="lg-ends"><span>GOT better</span><span>FES better</span></div>' +
      '<div class="lg-note">' + T.num(NPTS) +
        " single-pixel SWOT coastline points.</div>");

    // The ramp is a CSS gradient sampled off the same function as the markers.
    var ramp = T.byId("lg-ramp");
    if (ramp) {
      var stops = [];
      for (var s = 0; s <= LEGEND_STOPS; s++) {
        var t = -1 + 2 * s / LEGEND_STOPS;
        stops.push(divergingColor(t * MAX_ABS, MAX_ABS) + " " +
          (s / LEGEND_STOPS * 100).toFixed(1) + "%");
      }
      ramp.style.background = "linear-gradient(to right," + stops.join(",") + ")";
    }

    return { map: map, records: records, markers: markers, maxAbs: MAX_ABS };
  }

  return {
    ROWS: ROWS,
    divergingColor: divergingColor,
    build: build
  };
})();
