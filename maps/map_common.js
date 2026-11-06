/**
 * map_common.js - shared plumbing for the SWOT / tide-model R2 maps.
 *
 * Expects, already loaded, in this order:
 *   1. leaflet.min.js  -> window.L
 *   2. basemap_geo.js  -> LAND_HI, LAND_LO, BORDERS
 *   3. the page's point payload (d1_ice.js + d2_ice.js + d3_ice.js,
 *      d1.js + d2.js + d3.js, or d_5km.js / d_10km.js)
 *
 * Exposes a single global, `TideMap`, used by discrepancy_map.js and by the
 * per-page map scripts.
 */
var TideMap = (function () {
  "use strict";

  /* ------------------------------------------------------------------ *
   * Point-record layouts
   *
   * Every payload is one flat array of numbers. They disagree on how many
   * values each point takes, on whether lat/lon/R2 are scaled to integers,
   * and on which spread columns follow:
   *
   *   STD_7  d{1,2,3}_ice.js  7/pt, scaled   lat lon R2f R2g sdSSH sdFES sdGOT
   *   VAR_6  d{1,2,3}.js      6/pt, scaled   lat lon R2f R2g varFES varGOT
   *   VAR_6_RAW  d_5km.js,    6/pt, raw      lat lon R2f R2g varFES varGOT
   *              d_10km.js
   *
   * "scaled" means lat/lon are x100 and the two R2 values x10000; the spread
   * columns are never scaled. The STD_* payloads carry standard deviations
   * directly, the VAR_* ones carry variances (so callers take a square root).
   * ------------------------------------------------------------------ */
  var LAYOUTS = {
    STD_7: {
      stride: 7,
      coordScale: 100,
      r2Scale: 10000,
      extra: ["ssh_s", "fes_s", "got_s"]
    },
    VAR_6: {
      stride: 6,
      coordScale: 100,
      r2Scale: 10000,
      extra: ["fv", "gv"]
    },
    VAR_6_RAW: {
      stride: 6,
      coordScale: 1,
      r2Scale: 1,
      extra: ["fv", "gv"]
    }
  };

  /**
   * Decode flat payload arrays into point records.
   *
   * @param {number[][]} chunks - payload arrays, e.g. [D1, D2, D3]
   * @param {Object} layout     - one of LAYOUTS
   * @returns {Array<Object>} records with lat, lon, fes, got, d (= fes - got)
   *                          and the layout's extra columns
   */
  function decodeRecords(chunks, layout) {
    var stride = layout.stride;
    var coord = layout.coordScale;
    var r2 = layout.r2Scale;
    var extra = layout.extra;

    var total = 0;
    for (var c = 0; c < chunks.length; c++) {
      total += chunks[c].length;
    }

    // Walk each chunk in place rather than concatenating them: the payloads
    // run to millions of numbers and the copies are not worth making.
    var out = new Array(total / stride);
    var j = 0;
    for (c = 0; c < chunks.length; c++) {
      var a = chunks[c];
      for (var i = 0; i < a.length; i += stride) {
        var rec = {
          lat: a[i] / coord,
          lon: a[i + 1] / coord,
          fes: a[i + 2] / r2,
          got: a[i + 3] / r2,
          d: (a[i + 2] - a[i + 3]) / r2
        };
        for (var e = 0; e < extra.length; e++) {
          rec[extra[e]] = a[i + 4 + e];
        }
        out[j++] = rec;
      }
    }
    return out;
  }

  /* ------------------------------------------------------------------ *
   * Small formatting / colour helpers
   * ------------------------------------------------------------------ */

  /** Read a CSS custom property off :root, e.g. css("--land"). */
  function css(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }

  /** Thousands-separated integer. */
  function num(n) {
    return n.toLocaleString("en-US");
  }

  /** Fixed 4-decimal value, the standard precision for these R2 tables. */
  function fmt4(v) {
    return v.toFixed(4);
  }

  /** Fixed 4-decimal value with an explicit +/- (true minus sign). */
  function signed4(v) {
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(4);
  }

  /** One key/value line, as used in both tooltips and popups. */
  function row(key, value) {
    return '<div class="tt-row"><span class="k">' + key +
      '</span><span class="v">' + value + "</span></div>";
  }

  function hexToRgb(hex) {
    var h = hex.replace("#", "");
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16)
    ];
  }

  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map(function (c) {
      var s = Math.round(c).toString(16);
      return s.length < 2 ? "0" + s : s;
    }).join("");
  }

  /** Linear interpolation between two hex colours; t in [0, 1]. */
  function lerpColor(hexA, hexB, t) {
    var a = hexToRgb(hexA);
    var b = hexToRgb(hexB);
    return rgbToHex(
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t
    );
  }

  /** Clamp to [0, 1]. */
  function clamp01(t) {
    return Math.min(1, Math.max(0, t));
  }

  /* ------------------------------------------------------------------ *
   * Map scaffolding
   * ------------------------------------------------------------------ */

  /** Global view: whole-world data, parallels every 10 deg from 60S to 70N. */
  var VIEW_GLOBAL = {
    center: [5, 60],
    zoom: 3,
    graticule: {
      latFrom: -60, latTo: 70, latStep: 10,
      lonStep: 20, meridianFrom: -70, meridianTo: 70
    }
  };

  /** Tropical view: the 25S-25N band maps sit lower and draw fewer lines. */
  var VIEW_TROPICS = {
    center: [0, 60],
    zoom: 3,
    graticule: {
      latFrom: -30, latTo: 30, latStep: 10,
      lonStep: 20, meridianFrom: -40, meridianTo: 40
    }
  };

  /** Dedicated panes so land/lines always sit under the data markers. */
  var PANES = [["landPane", 250], ["linesPane", 270]];

  /**
   * Create the Leaflet map and draw the static basemap (land, borders,
   * graticule).
   *
   * @param {string} elementId - id of the map container
   * @param {Object} view      - VIEW_GLOBAL, VIEW_TROPICS or the same shape
   * @returns {{map: L.Map, home: {center: L.LatLng, zoom: number}}}
   */
  function createMap(elementId, view) {
    var map = L.map(elementId, {
      center: view.center,
      zoom: view.zoom,
      minZoom: 2,
      maxZoom: 12,
      preferCanvas: true
    });

    map.attributionControl.addAttribution(
      'Land: <a href="https://www.naturalearthdata.com/">Natural Earth</a>'
    );

    for (var i = 0; i < PANES.length; i++) {
      map.createPane(PANES[i][0]);
      map.getPane(PANES[i][0]).style.zIndex = PANES[i][1];
    }

    drawLand(map);
    drawLines(map, view.graticule);

    return {
      map: map,
      home: { center: map.getCenter(), zoom: map.getZoom() }
    };
  }

  /** Flat [lat, lon, ...] -> [[lat, lon], ...] for Leaflet. */
  function toLatLngs(flat) {
    var out = new Array(flat.length / 2);
    for (var i = 0, j = 0; i < flat.length; i += 2, j++) {
      out[j] = [flat[i], flat[i + 1]];
    }
    return out;
  }

  /** Polygon (array of flat rings) -> array of Leaflet ring arrays. */
  function toPolygon(rings) {
    return rings.map(toLatLngs);
  }

  function drawLand(map) {
    var renderer = L.canvas({ pane: "landPane", padding: 0.3 });
    var style = {
      renderer: renderer,
      interactive: false,
      stroke: false,
      fillColor: css("--land"),
      fillOpacity: 1
    };

    var layer = L.layerGroup().addTo(map);
    L.polygon(LAND_LO.map(toPolygon), style).addTo(layer);
    L.polygon(LAND_HI.map(toPolygon), style).addTo(layer);
    return layer;
  }

  function drawLines(map, grat) {
    var renderer = L.canvas({ pane: "linesPane", padding: 0.3 });
    var layer = L.layerGroup().addTo(map);

    var borderStyle = {
      renderer: renderer,
      interactive: false,
      color: css("--border-line"),
      weight: 0.7,
      opacity: 0.85
    };
    L.polyline(BORDERS.map(toLatLngs), borderStyle).addTo(layer);

    var gratStyle = {
      renderer: renderer,
      interactive: false,
      color: css("--grat"),
      weight: 0.6,
      opacity: 0.5,
      dashArray: "3 5"
    };

    // Parallels, each labelled at the far west edge.
    for (var lat = grat.latFrom; lat <= grat.latTo; lat += grat.latStep) {
      L.polyline([[lat, -180], [lat, 180]], gratStyle).addTo(layer);
      L.marker([lat, -179], {
        pane: "linesPane",
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: "grat-label",
          iconSize: [34, 12],
          iconAnchor: [-3, 6],
          html: latLabel(lat)
        })
      }).addTo(layer);
    }

    // Meridians, clipped to the latitudes the page actually covers.
    for (var lon = -180; lon <= 180; lon += grat.lonStep) {
      L.polyline(
        [[grat.meridianFrom, lon], [grat.meridianTo, lon]],
        gratStyle
      ).addTo(layer);
    }

    return layer;
  }

  function latLabel(lat) {
    if (lat === 0) return "0°";
    return Math.abs(lat) + "°" + (lat > 0 ? "N" : "S");
  }

  /* ------------------------------------------------------------------ *
   * Data markers
   * ------------------------------------------------------------------ */

  /** Zoom levels at which the marker radius steps up. */
  var ZOOM_BREAKS = [3, 5, 7];

  /** Default marker radii, one per zoom band. */
  var RADII_DEFAULT = [2, 3, 4, 5];

  /** Slightly fatter dots, for the sparser tropical-band maps. */
  var RADII_LARGE = [2.5, 3.5, 4.5, 6];

  /**
   * Marker radius in px for a given zoom level.
   * @param {number} zoom
   * @param {number[]} radii - four radii, smallest first
   */
  function radiusFor(zoom, radii) {
    for (var i = 0; i < ZOOM_BREAKS.length; i++) {
      if (zoom <= ZOOM_BREAKS[i]) return radii[i];
    }
    return radii[ZOOM_BREAKS.length];
  }

  /**
   * Build one circle marker per record, wired to a shared tooltip and to a
   * click popup. The record is stashed on `marker.rec`.
   *
   * @param {L.Map} map
   * @param {Array<Object>} records - from decodeRecords()
   * @param {Object} opts
   * @param {function(Object):string} opts.tipHTML - hover tooltip body
   * @param {function(Object):string} opts.popHTML - click popup body
   * @param {number[]} opts.radii                  - RADII_DEFAULT or RADII_LARGE
   * @returns {{markers: Array<L.CircleMarker>, tooltip: L.Tooltip}}
   */
  function buildMarkers(map, records, opts) {
    var tooltip = L.tooltip({
      direction: "top",
      offset: [0, -7],
      className: "pt-tip",
      opacity: 1
    });

    var radii = opts.radii || RADII_DEFAULT;
    var radius = radiusFor(map.getZoom(), radii);
    var markers = new Array(records.length);

    for (var i = 0; i < records.length; i++) {
      var rec = records[i];
      var marker = L.circleMarker([rec.lat, rec.lon], {
        radius: radius,
        fillColor: rec.c,
        fillOpacity: 0.85,
        color: rec.c,
        weight: 0.5,
        opacity: 0.95
      });
      marker.rec = rec;

      marker.on("mouseover", function (e) {
        tooltip.setContent(opts.tipHTML(this.rec)).setLatLng(e.latlng);
        map.openTooltip(tooltip);
      });
      marker.on("mouseout", function () {
        map.closeTooltip(tooltip);
      });
      marker.on("click", function (e) {
        map.closeTooltip(tooltip);
        L.popup({ offset: [0, -4], autoPanPadding: [24, 24] })
          .setLatLng(e.latlng)
          .setContent(opts.popHTML(this.rec))
          .openOn(map);
      });

      markers[i] = marker;
    }

    // Keep dot size readable as the user zooms.
    map.on("zoomend", function () {
      var r = radiusFor(map.getZoom(), radii);
      for (var j = 0; j < markers.length; j++) {
        if (markers[j].options.radius !== r) markers[j].setRadius(r);
      }
    });

    wireCopyButton(map);

    return { markers: markers, tooltip: tooltip };
  }

  /** Make the "Copy coordinates" button inside popups work. */
  function wireCopyButton(map) {
    map.on("popupopen", function (e) {
      var el = e.popup.getElement();
      var btn = el && el.querySelector(".copy");
      if (!btn) return;

      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-coord");
        var mark = function (label) {
          btn.textContent = label;
          btn.classList.add("done");
        };
        var fallback = function () { mark(text); };

        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
              mark("Copied " + text);
            }, fallback);
          } else {
            fallback();
          }
        } catch (err) {
          fallback();
        }
      });
    });
  }

  /* ------------------------------------------------------------------ *
   * Controls
   * ------------------------------------------------------------------ */

  function byId(id) {
    return document.getElementById(id);
  }

  /** Value of the checked radio in a named group, or `fallback`. */
  function radioValue(name, fallback) {
    var el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : fallback;
  }

  /** Trailing-edge debounce, used to keep the slider responsive. */
  function debounce(fn, ms) {
    var timer = null;
    return function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(fn, ms);
    };
  }

  /**
   * Wire the shared control strip: category/direction radios, the |delta|
   * threshold slider (with live readout + debounced redraw) and Reset view.
   *
   * @param {Object} opts
   * @param {string} opts.radioName      - name of the radio group
   * @param {string} opts.defaultRadioId - radio to re-check on reset
   * @param {function():void} opts.render
   * @param {L.Map} opts.map
   * @param {{center: L.LatLng, zoom: number}} opts.home
   */
  function wireControls(opts) {
    var slider = byId("thresh");
    var readout = byId("thresh-val");
    var redraw = debounce(opts.render, 80);

    slider.addEventListener("input", function () {
      readout.textContent = parseFloat(slider.value).toFixed(2);
      redraw();
    });

    var radios = document.querySelectorAll(
      'input[name="' + opts.radioName + '"]'
    );
    for (var i = 0; i < radios.length; i++) {
      radios[i].addEventListener("change", opts.render);
    }

    byId("reset").addEventListener("click", function () {
      byId(opts.defaultRadioId).checked = true;
      slider.value = "0";
      opts.render();
      opts.map.setView(opts.home.center, opts.home.zoom);
    });
  }

  /** Add a bottom-right legend box whose body is `html`. */
  function addLegend(map, html) {
    var legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
      var div = L.DomUtil.create("div", "legend");
      div.innerHTML = html;
      L.DomEvent.disableClickPropagation(div);
      return div;
    };
    legend.addTo(map);
    return legend;
  }

  /* ------------------------------------------------------------------ */

  return {
    LAYOUTS: LAYOUTS,
    VIEW_GLOBAL: VIEW_GLOBAL,
    VIEW_TROPICS: VIEW_TROPICS,
    RADII_DEFAULT: RADII_DEFAULT,
    RADII_LARGE: RADII_LARGE,
    decodeRecords: decodeRecords,
    css: css,
    num: num,
    fmt4: fmt4,
    signed4: signed4,
    row: row,
    hexToRgb: hexToRgb,
    rgbToHex: rgbToHex,
    lerpColor: lerpColor,
    clamp01: clamp01,
    createMap: createMap,
    toLatLngs: toLatLngs,
    toPolygon: toPolygon,
    radiusFor: radiusFor,
    buildMarkers: buildMarkers,
    byId: byId,
    radioValue: radioValue,
    debounce: debounce,
    wireControls: wireControls,
    addLegend: addLegend
  };
})();
