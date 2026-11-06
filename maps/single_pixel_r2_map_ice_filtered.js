/**
 * single_pixel_r2_map_ice_filtered.js
 *
 * 864,752 ice-filtered single-pixel SWOT coastline points (every cycle must
 * have dynamic_ice_flag = 0), 55S-65N, within 10 km of land.
 *
 * Payload d{1,2,3}_ice.js carries three standard deviations per point, so the
 * tooltip prints them directly.
 */
(function () {
  "use strict";

  TideDiscrepancyMap.build({
    payload: [D1, D2, D3],
    layout: TideMap.LAYOUTS.STD_7,
    view: TideMap.VIEW_GLOBAL,
    radii: TideMap.RADII_DEFAULT,
    coordDigits: 2,
    detailRows: TideDiscrepancyMap.ROWS.standardDeviations,
    release: function () { D1 = null; D2 = null; D3 = null; }
  });
})();
