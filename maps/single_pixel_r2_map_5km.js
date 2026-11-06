/**
 * single_pixel_r2_map_5km.js
 *
 * 212,580 single-pixel SWOT coastline points (no patch averaging, centre
 * within 5 km of land) across the tropical band, 25S-25N.
 *
 * Payload d_5km.js is unscaled, so lat/lon print to three decimals and the
 * dots are drawn a little larger than on the global maps.
 */
(function () {
  "use strict";

  TideDiscrepancyMap.build({
    payload: [D_5KM],
    layout: TideMap.LAYOUTS.VAR_6_RAW,
    view: TideMap.VIEW_TROPICS,
    radii: TideMap.RADII_LARGE,
    coordDigits: 3,
    detailRows: TideDiscrepancyMap.ROWS.deltaAndVariances,
    release: function () { D_5KM = null; }
  });
})();
